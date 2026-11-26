"""Freeze known exposure changes on a registered crop of the real owner TIFF."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from hashlib import file_digest
from pathlib import Path
from typing import Literal

import numpy as np
import tifffile
from numpy.typing import NDArray
from scipy.ndimage import maximum_filter

from astromosaic.io.atomic import atomic_binary_file
from tools.phase8c_color_reference import Codes, FloatRGB, decode_srgb

type Mask = NDArray[np.bool_]
type ReferenceArray = Codes | Mask
type ExposureMode = Literal["off", "manual_ev", "sky_offset", "standard", "offset_only"]

_OWNER_HASHES = (
    "c3d7f1bd6264ea489ed62220ef051ffda2911cd9d7c5daef1ce00b9d9983d4db",
    "71aca62355bf0fb86c6ef8012ce98f729a7b90e5cc3d6de1bc4b2db66ed68171",
)
_CROP = (2048, 1408, 768, 512)
_BLOCK = 64
_LUMA = np.array([0.2126, 0.7152, 0.0722])
_APERTURES = ((48, 360), (142, 399), (739, 220))
_MAX_GAIN_FRACTION = 0.01
_MAX_OFFSET_ERROR = 2e-4
_MAX_HELD_OUT_RGB_P95 = 3e-5
_MAX_APERTURE_FRACTION = 0.01
_MIN_TRAINING_SAMPLES = 128
_MIN_GAIN_SPREAD = 0.003


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    mode: ExposureMode
    gain: float
    offset: float


_CASES = (
    Case("identity", "off", 1.0, 0.0),
    Case("one_stop", "manual_ev", 2.0, 0.0),
    Case("sky_offset", "sky_offset", 1.0, -0.004),
    Case("gain_and_offset", "standard", 1.25, -0.003),
    Case("masked_contamination", "standard", 1.25, -0.003),
    Case("weak_gain", "offset_only", 1.0, -0.0025),
    Case("insufficient_overlap", "off", 1.25, -0.003),
)


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def _encode(linear: FloatRGB) -> Codes:
    unit = np.clip(linear, 0, 1)
    encoded = np.where(unit <= 0.0031308, 12.92 * unit, 1.055 * unit ** (1 / 2.4) - 0.055)
    return np.rint(encoded * 65535).astype(np.uint16)


def _metadata(path: Path) -> dict[str, float | int]:
    with tifffile.TiffFile(path) as image:
        page = image.pages[0]
        assert isinstance(page, tifffile.TiffPage)
        exif = page.tags.valueof("ExifTag", {})
        if not isinstance(exif, dict):
            raise ValueError(f"{path.name} lacks the frozen exposure metadata.")
        shutter = exif["ExposureTime"]
        aperture = exif["FNumber"]
        return {
            "seconds": float(shutter[0]) / shutter[1],
            "f_number": float(aperture[0]) / aperture[1],
            "iso": int(exif["ISOSpeedRatings"]),
        }


def _aperture_flux(image: FloatRGB, x: int, y: int) -> float:
    tile = image[y - 12 : y + 13, x - 12 : x + 13] @ _LUMA
    axis = np.arange(-12, 13)
    distance_squared = axis**2 + axis[:, None] ** 2
    sky = np.median(tile[(distance_squared >= 8**2) & (distance_squared <= 12**2)])
    return float((tile[distance_squared <= 6**2] - sky).sum())


def _oracle(
    case: Case, reference: FloatRGB, moving: FloatRGB, eligible: Mask, holdout: Mask
) -> dict[str, object]:
    training, validation = eligible & ~holdout, eligible & holdout
    a, b = reference[training] @ _LUMA, moving[training] @ _LUMA
    signal_span = float(np.diff(np.percentile(b, [5, 95]))[0]) if b.size else 0.0
    gain, offset = 1.0, 0.0
    if case.name == "insufficient_overlap":
        if b.size >= _MIN_TRAINING_SAMPLES:
            raise ValueError("The insufficient-overlap fixture gained usable support.")
    elif b.size < _MIN_TRAINING_SAMPLES or validation.sum() < _MIN_TRAINING_SAMPLES:
        raise ValueError(f"{case.name} lacks the frozen sample support.")
    elif case.mode == "manual_ev":
        gain = 2.0
    elif case.mode == "standard":
        if signal_span < _MIN_GAIN_SPREAD:
            raise ValueError(f"{case.name} cannot constrain the known gain.")
        centered = b - b.mean()
        gain = float(centered @ (a - a.mean()) / (centered @ centered))
        offset = float(a.mean() - gain * b.mean())
    elif case.mode in ("sky_offset", "offset_only"):
        if case.mode == "offset_only" and signal_span >= _MIN_GAIN_SPREAD:
            raise ValueError("The weak-gain fixture has a measurable gain range.")
        offset = float(np.median(a - b))

    actual, predicted = reference[validation], moving[validation]
    before = float(np.percentile(np.abs(actual - predicted), 95)) if actual.size else None
    after = (
        float(np.percentile(np.abs(actual - (gain * predicted + offset)), 95))
        if actual.size
        else None
    )
    flux_bias = None
    if case.name not in ("weak_gain", "insufficient_overlap"):
        biases = []
        for x, y in _APERTURES:
            region = np.s_[y - 12 : y + 13, x - 12 : x + 13]
            if not holdout[region].all():
                raise ValueError("A reference stellar aperture overlaps a training block.")
            truth = _aperture_flux(reference, x, y)
            measured = gain * _aperture_flux(moving, x, y)
            if truth <= 0:
                raise ValueError("A reference stellar aperture lacks positive flux.")
            biases.append(abs(measured / truth - 1))
        flux_bias = max(biases)
        if flux_bias > _MAX_APERTURE_FRACTION:
            raise ValueError(f"{case.name} exceeded the reference aperture-flux error limit.")
    if case.name != "insufficient_overlap" and (
        abs(gain / case.gain - 1) > _MAX_GAIN_FRACTION
        or abs(offset - case.offset) > _MAX_OFFSET_ERROR
        or after is None
        or after > _MAX_HELD_OUT_RGB_P95
    ):
        raise ValueError(f"{case.name} failed the independent exposure control.")
    return {
        "expected_effective_mode": case.mode,
        "known_affine_gain": case.gain,
        "known_affine_offset": case.offset,
        "reference_fit_gain": gain,
        "reference_fit_offset": offset,
        "training_samples": int(training.sum()),
        "held_out_samples": int(validation.sum()),
        "training_linear_luminance_5_to_95_span": signal_span,
        "held_out_off_rgb_p95": before,
        "held_out_corrected_rgb_p95": after,
        "aperture_flux_maximum_fractional_error": flux_bias,
    }


def measure(owner: Path, peer: Path) -> tuple[dict[str, object], dict[str, ReferenceArray]]:
    paths = (owner, peer)
    if tuple(_sha256(path) for path in paths) != _OWNER_HASHES:
        raise ValueError("Use the original, frozen 20.TIF and 21.TIF files.")
    x, y, width, height = _CROP
    mapped = tifffile.memmap(owner, mode="r")
    codes = mapped[y : y + height, x : x + width].copy()
    del mapped
    if codes.dtype != np.uint16 or codes.shape != (height, width, 3):
        raise ValueError("Expected the frozen UInt16 RGB TIFF crop.")
    base = decode_srgb(codes)
    luminance = base @ _LUMA
    yy, xx = np.indices((height, width))
    holdout = ((yy // _BLOCK + 2 * (xx // _BLOCK)) % 5) == 0
    quiet = ~maximum_filter((luminance > 0.075) | (codes == 65535).any(axis=2), size=11)
    covered = np.ones_like(holdout)
    covered[192:256, 384:448] = False
    empty_mask = np.zeros_like(covered)

    arrays: dict[str, ReferenceArray] = {"holdout": holdout}
    reports = {}
    for case in _CASES:
        reference_codes = codes
        if case.name == "weak_gain":
            reference_codes = _encode(0.008 + 0.004 * (base - np.median(luminance)))
        reference = decode_srgb(reference_codes)
        moving = (reference - case.offset) / case.gain
        exclusions = empty_mask.copy()
        valid = covered.copy()
        if case.name == "masked_contamination":
            exclusions[128:256, 256:512] = True
            moving[exclusions] += 0.06
        if case.name == "insufficient_overlap":
            valid.fill(False)
            valid[8:12, 8:12] = True
            valid[8:12, 72:76] = True
        moving_codes = _encode(moving)
        eligible = quiet & valid & ~exclusions & ~(moving_codes == 65535).any(axis=2)
        reports[case.name] = _oracle(case, reference, decode_srgb(moving_codes), eligible, holdout)
        arrays.update(
            {
                f"{case.name}_reference": reference_codes,
                f"{case.name}_moving": moving_codes,
                f"{case.name}_coverage": valid,
                f"{case.name}_photometry": eligible,
            }
        )
    metadata = [_metadata(path) for path in paths]
    if tuple(_sha256(path) for path in paths) != _OWNER_HASHES:
        raise ValueError("An original TIFF changed during reference preparation.")
    return {
        "original_sha256": dict(zip(("20.TIF", "21.TIF"), _OWNER_HASHES, strict=True)),
        "crop_xywh": _CROP,
        "holdout_block_size": _BLOCK,
        "stellar_aperture_centers_in_crop_xy": _APERTURES,
        "reference_limits": {
            "gain_fraction": _MAX_GAIN_FRACTION,
            "offset_linear": _MAX_OFFSET_ERROR,
            "held_out_rgb_p95_linear": _MAX_HELD_OUT_RGB_P95,
            "aperture_flux_fraction": _MAX_APERTURE_FRACTION,
        },
        "actual_owner_capture_metadata": metadata,
        "metadata_controls": {
            "reference": {"seconds": 10, "f_number": 4, "iso": 6400},
            "owner_equal_capture_gain": 1.0,
            "half_shutter_gain": 2.0,
            "half_shutter": {"seconds": 5, "f_number": 4, "iso": 6400},
            "double_f_number_gain": 4.0,
            "double_f_number": {"seconds": 10, "f_number": 8, "iso": 6400},
            "iso_without_response_gain": None,
            "iso_without_response": {"seconds": 10, "f_number": 4, "iso": 3200},
            "missing_aperture_gain": None,
            "missing_aperture": {"seconds": 10, "iso": 6400},
        },
        "cases": reports,
    }, arrays


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("owner", type=Path, help="Original 20.TIF used for the crop")
    parser.add_argument("peer", type=Path, help="Original 21.TIF for exposure metadata")
    parser.add_argument("--samples", type=Path, help="Write the reference arrays at a new NPZ path")
    options = parser.parse_args()
    try:
        report, samples = measure(options.owner, options.peer)
        if options.samples is not None:
            with atomic_binary_file(options.samples) as stream:
                np.savez_compressed(stream, allow_pickle=False, **samples)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
