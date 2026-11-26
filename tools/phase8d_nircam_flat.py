"""Replay NIRCam detector flats against separate MAST rate and cal products."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from hashlib import file_digest
from itertools import combinations
from pathlib import Path

import numpy as np
import sep
from astropy.coordinates import ICRS
from astropy.io import fits
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from astromosaic.core import Region
from astromosaic.geometry import PanelGeometry, read_panel_geometry, tan_output_wcs
from astromosaic.io.atomic import atomic_binary_file

type Samples = NDArray[np.float32]
type Mask = NDArray[np.bool_]
type Positions = NDArray[np.float64]
type Indices = NDArray[np.intp]

_SIZE = 2048
_TILE = 256
_HALO = 24
_MIN_RESPONSE = np.float32(0.2)
_VARIANCES = ("VAR_POISSON", "VAR_RNOISE")
_MODES = ("off", "flat_once", "flat_twice")
_RESPONSE_SUBSETS = (("one_percent_response_change", 0.01),)
_STEMS = tuple(f"jw01074001001_06101_{index:05d}_nrcb2" for index in range(1, 4))
_FLAT = "jwst_nircam_flat_0675.fits"
_HASHES = {
    _FLAT: "e13df403a4b4406323d9deb61c215e8dba164d0c60fbbfcf9bc09f5990206a9e",
    f"{_STEMS[0]}_rate.fits": "5fbac2675b55490fd89a668f57511cce7560ac1ee019e21c7b72a120fac382de",
    f"{_STEMS[0]}_cal.fits": "70897baf27ceacda5ba7cc5793f3d6e52499ca57e27dd1d99cb54276e28dea6a",
    f"{_STEMS[1]}_rate.fits": "52a11dd94b560c45f1c2749cabf4c75cbbf30e6784fc9d2630be4ca4a5dd54c1",
    f"{_STEMS[1]}_cal.fits": "460bea009de46bb070ee57991350300f00dbea07679aa3a3593bad4d8fc2d676",
    f"{_STEMS[2]}_rate.fits": "c2cf08d311b9768b30a8b386691a9e862a4278dda3943b06341cf1dec9257175",
    f"{_STEMS[2]}_cal.fits": "e5985c84527f097b9dc8f7e0852817c923f9ec98e60ad67ff9d442f0e3becd7c",
}


@dataclass(frozen=True)
class Reference:
    stems: tuple[str, ...]
    flat: str
    hashes: Mapping[str, str]
    sky_center: tuple[float, float]
    minimum_snr: float = 0.0
    response_subsets: tuple[tuple[str, float], ...] = _RESPONSE_SUBSETS


_BASELINE = Reference(_STEMS, _FLAT, _HASHES, (80.706, -69.470))

_NRCB4_STEMS = tuple(f"jw01476001012_02101_{index:05d}_nrcb4" for index in range(1, 7))
_NRCB4_FLAT = "jwst_nircam_flat_0720.fits"
_NRCB4_HASHES = {
    _NRCB4_FLAT: "c6b3170b6d8493e2cf340218f05e6d15eb2815ab3b48d4bf1361fda68ae03d39",
    f"{_NRCB4_STEMS[0]}_rate.fits": "b9e1a1bad31557a2b8138d915b8c0bd7b0129cca78b5399d35af3695f1c36fc5",
    f"{_NRCB4_STEMS[0]}_cal.fits": "81125da80aff6b551b4cd9aacf3bfbf40599ac06150b60a8489ebc97be1da16d",
    f"{_NRCB4_STEMS[1]}_rate.fits": "a014822c6932d7337a29e8d7fc094ea6474a4e1231e83323897f2ead11b9fbdd",
    f"{_NRCB4_STEMS[1]}_cal.fits": "312d765951aa2fd698675c197b49eca943331f448e27c4b9a92375f0409098be",
    f"{_NRCB4_STEMS[2]}_rate.fits": "796f2648ab841f88ab4c4d59868dff4d6fc4f5782f0c2b82fac497b4db3894f1",
    f"{_NRCB4_STEMS[2]}_cal.fits": "4474dc55f27400f1fbd4ca82c0cd52b6cff328ecf6e1904554f5b66ccb7a51bd",
    f"{_NRCB4_STEMS[3]}_rate.fits": "e1afaea6585a2e5153d82f674acd5b570e7e9540f5a9efa0e4b0ef8a2e5bf0ec",
    f"{_NRCB4_STEMS[3]}_cal.fits": "4bfe70dd6c827f26db0f01a76c9dc7b9a881b2e2e35d486d6a27bfe1aa81bf7c",
    f"{_NRCB4_STEMS[4]}_rate.fits": "1898693edbaee23402ff82beada1d74ab48ec3934f285eb5fec4c55046948b26",
    f"{_NRCB4_STEMS[4]}_cal.fits": "7bfc3adb503fff1de093909429057e5c64f9214da4eecd5105a07656b7402d05",
    f"{_NRCB4_STEMS[5]}_rate.fits": "66194f499bfd1d4e97eaa00f2a60b616aa48d39d7324190be0e5b74e6f724935",
    f"{_NRCB4_STEMS[5]}_cal.fits": "8ec769dbf0223e863e32c759ac631778b2f2b1981c1d4254762a18cb82dfa437",
}
_REFERENCES = {
    "nrcb2-f150w": _BASELINE,
    "nrcb4-f200w": Reference(
        _NRCB4_STEMS,
        _NRCB4_FLAT,
        _NRCB4_HASHES,
        (80.4864, -69.4913),
        minimum_snr=100.0,
        response_subsets=(*_RESPONSE_SUBSETS, ("two_percent_response_change", 0.02)),
    ),
}


@dataclass(frozen=True)
class DetectorTile:
    rate: Samples
    flat: Samples
    valid: Mask
    corrected: Samples


@dataclass(frozen=True)
class StarMeasurements:
    detector_xy: Positions
    sky_xy: Positions
    flux: Positions
    response: Positions


def _check_hashes(folder: Path, hashes: Mapping[str, str]) -> None:
    for name, expected in hashes.items():
        with (folder / name).open("rb") as stream:
            if file_digest(stream, "sha256").hexdigest() != expected:
                raise ValueError(f"Use the frozen reference file for {name}.")


def _divide(values: Samples, response: Samples, valid: Mask) -> Samples:
    output = np.full(values.shape, np.nan, dtype=np.float32)
    np.divide(values, response, out=output, where=valid)
    return output


def _read_tile(rate: fits.HDUList, flat: fits.HDUList, region: Region) -> DetectorTile:
    original = np.asarray(rate["SCI"].section[region.slices], dtype=np.float32)
    response = np.asarray(flat["SCI"].section[region.slices], dtype=np.float32)
    valid = (
        (rate["DQ"].section[region.slices] == 0)
        & (flat["DQ"].section[region.slices] == 0)
        & np.isfinite(original)
        & np.isfinite(response)
        & (response >= _MIN_RESPONSE)
    )
    return DetectorTile(original, response, valid, _divide(original, response, valid))


def _verify_pair(
    rate: fits.HDUList, flat: fits.HDUList, cal: fits.HDUList, flat_name: str
) -> np.float32:
    detector_keys = ("DETECTOR", "FILTER", "PUPIL", "SUBSTRT1", "SUBSTRT2", "SUBSIZE1", "SUBSIZE2")
    exposure_keys = ("TIME-OBS", "DATE-OBS", "EFFEXPTM", "READPATT", "R_DARK", "R_SUPERB")
    for key in detector_keys:
        if not rate[0].header[key] == flat[0].header[key] == cal[0].header[key]:
            raise ValueError(f"Detector coordinate or calibration mismatch for {key}.")
    for key in exposure_keys:
        if rate[0].header[key] != cal[0].header[key]:
            raise ValueError(f"The archive products do not share {key}.")
    if (
        any(rate[0].header[key] != "COMPLETE" for key in ("S_DARK", "S_SUPERB", "S_RAMP"))
        or rate[0].header.get("S_FLAT") == "COMPLETE"
        or any(cal[0].header[key] != "COMPLETE" for key in ("S_FLAT", "S_PHOTOM", "S_WCS"))
        or cal[0].header["R_FLAT"] != f"crds://{flat_name}"
        or rate["SCI"].header["BUNIT"] != "DN/s"
        or cal["SCI"].header["BUNIT"] != "MJy/sr"
        or any(hdus["SCI"].shape != (_SIZE, _SIZE) for hdus in (rate, flat, cal))
    ):
        raise ValueError("Expected matching detector-native rate, flat and cal products.")
    scale = np.float32(cal["SCI"].header["PHOTMJSR"])
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("Expected a positive finite archive photometric scale.")
    return scale


def _check_tile(
    rate: fits.HDUList,
    cal: fits.HDUList,
    tile: DetectorTile,
    scale: np.float32,
    owned: Region,
    window: Region,
    counts: dict[str, int],
) -> None:
    patch = Region(owned.x - window.x, owned.y - window.y, owned.width, owned.height).slices
    valid = tile.valid[patch]
    expected = cal["SCI"].section[owned.slices]
    archived_valid = (cal["DQ"].section[owned.slices] == 0) & np.isfinite(expected)
    if not np.array_equal(valid, archived_valid):
        raise ValueError(f"Replay coverage differs from the archive at {owned}.")
    values = tile.corrected[patch][valid] * scale
    if not np.array_equal(values, expected[valid]):
        raise ValueError(f"Flat-corrected samples differ from the archive at {owned}.")
    response_squared = tile.flat[patch][valid] ** 2
    for name in _VARIANCES:
        propagated = (rate[name].section[owned.slices][valid] / response_squared) * scale**2
        if not np.array_equal(propagated, cal[name].section[owned.slices][valid]):
            raise ValueError(f"{name} differs from the archive at {owned}.")
    counts["valid_samples"] += int(valid.sum())
    counts["negative_samples"] += int(np.count_nonzero(values < 0))
    counts["zero_samples"] += int(np.count_nonzero(values == 0))


def _aperture(
    tile: DetectorTile, x: float, y: float, error: Samples | None = None, minimum_snr: float = 0.0
) -> tuple[float, float, float, float]:
    # A one-pixel halo keeps fractional aperture samples off invalid detector pixels.
    left, top = int(x) - 10, int(y) - 10
    height, width = tile.rate.shape
    if not Region(0, 0, width, height).contains(Region(left, top, 22, 22)):
        return (np.nan,) * 4
    patch = Region(left, top, 22, 22).slices
    yy, xx = np.mgrid[patch]
    distances = (xx - x) ** 2 + (yy - y) ** 2
    annulus = (distances >= 7**2) & (distances <= 10**2)
    mask = tile.valid[patch]
    sky = mask & annulus
    support = distances <= 6**2
    sky_count = int(sky.sum())
    if not mask[support].all() or sky_count < 0.75 * annulus.sum():
        return (np.nan,) * 4

    response = tile.flat[patch]
    corrected = tile.corrected[patch]
    fluxes = []
    for mode, values in enumerate(
        (
            tile.rate[patch],
            corrected,
            _divide(corrected, response, mask),
        )
    ):
        background = np.median(values[sky])
        sigma = 1.4826 * np.median(np.abs(values[sky] - background))
        total = sep.sum_circle(
            np.where(mask, values, 0),
            np.array([x - left]),
            np.array([y - top]),
            5.0,
            subpix=7,
        )[0][0]
        flux = float(total - np.pi * 25 * background)
        if not np.isfinite(flux) or flux <= max(0.0, 25 * sigma * np.sqrt(np.pi * 25)):
            return (np.nan,) * 4
        if mode == 0 and error is not None:
            # Sum whole-pixel variances as a conservative aperture estimate.
            pixel_error = error[patch][support]
            if not (np.isfinite(pixel_error) & (pixel_error > 0)).all():
                return (np.nan,) * 4
            median_error = 1.2533 * sigma / np.sqrt(sky_count)
            flux_error = np.sqrt(
                np.square(pixel_error, dtype=np.float64).sum() + (np.pi * 25 * median_error) ** 2
            )
            if flux < minimum_snr * flux_error:
                return (np.nan,) * 4
        fluxes.append(flux)
    return fluxes[0], fluxes[1], fluxes[2], float(np.median(response[distances <= 5**2]))


def _stars_in_tile(
    tile: DetectorTile,
    owned: Region,
    window: Region,
    error: Samples | None,
    minimum_snr: float,
) -> Iterator[tuple[float, float, float, float, float, float]]:
    masked = ~tile.valid
    values = np.where(tile.valid, tile.corrected, 0)
    if tile.valid.sum() < 32:
        return
    background = sep.Background(values, mask=masked, bw=48, bh=48)
    signal = values - background.back()
    stars = sep.extract(signal, 5.0, err=background.rms(), mask=masked, minarea=4)
    if not len(stars):
        return
    xy = np.column_stack((stars["x"], stars["y"]))
    neighbor = cKDTree(xy).query(xy, k=2)[0][:, 1]
    width = np.sqrt(stars["a"] * stars["b"])
    keep = (
        (width >= 0.5)
        & (width <= 3.0)
        & (stars["flag"] == 0)
        & (stars["b"] >= 0.65 * stars["a"])
        & (neighbor >= 11.0)
    )
    if not keep.any():
        return
    x, y, flags = sep.winpos(signal, *xy[keep].T, width[keep], mask=masked, subpix=5)
    for col, row in zip(x[flags == 0], y[flags == 0], strict=True):
        sx, sy = float(col + window.x), float(row + window.y)
        if owned.x <= sx < owned.x + owned.width and owned.y <= sy < owned.y + owned.height:
            yield sx, sy, *_aperture(tile, float(col), float(row), error, minimum_snr)


def _measure_exposure(
    folder: Path, stem: str, flat: fits.HDUList, target: PanelGeometry, reference: Reference
) -> tuple[StarMeasurements, dict[str, object]]:
    counts = {"valid_samples": 0, "negative_samples": 0, "zero_samples": 0}
    stars: list[tuple[float, float, float, float, float, float]] = []
    with (
        fits.open(folder / f"{stem}_rate.fits", memmap=False) as rate,
        fits.open(folder / f"{stem}_cal.fits", memmap=False) as cal,
    ):
        scale = _verify_pair(rate, flat, cal, reference.flat)
        geometry = read_panel_geometry(cal["SCI"].header, _SIZE, _SIZE)
        for y in range(0, _SIZE, _TILE):
            for x in range(0, _SIZE, _TILE):
                owned = Region(x, y, _TILE, _TILE)
                window = owned.with_halo(_SIZE, _SIZE, _HALO)
                tile = _read_tile(rate, flat, window)
                _check_tile(rate, cal, tile, scale, owned, window, counts)
                error = (
                    np.asarray(rate["ERR"].section[window.slices], dtype=np.float32)
                    if reference.minimum_snr
                    else None
                )
                stars.extend(_stars_in_tile(tile, owned, window, error, reference.minimum_snr))

    catalog = np.asarray(stars, dtype=np.float64).reshape(-1, 6)
    xy = catalog[:, :2]
    mapped = target.inverse(geometry.forward(*xy.T))
    if len(xy) < 8 or not np.isfinite(mapped).all():
        raise ValueError(f"Insufficient projected stars in {stem}.")
    result = {
        **counts,
        "coverage_matches": True,
        "samples_match": True,
        "propagated_variances_match": list(_VARIANCES),
        "photometric_scale": float(scale),
        "detections": len(xy),
    }
    return StarMeasurements(xy, mapped, catalog[:, 2:5], catalog[:, 5]), result


def _matches(a: Positions, b: Positions) -> tuple[Indices, Indices]:
    distance, nearest = cKDTree(b).query(a, k=2, distance_upper_bound=1.0)
    _, reverse = cKDTree(a).query(b, distance_upper_bound=1.0)
    left = np.flatnonzero(np.isfinite(distance[:, 0]) & (distance[:, 0] <= 0.8 * distance[:, 1]))
    right = nearest[left, 0]
    keep = reverse[right] == left
    return left[keep], right[keep]


def _compare_pair(
    a: StarMeasurements,
    b: StarMeasurements,
    response_subsets: tuple[tuple[str, float], ...] = _RESPONSE_SUBSETS,
) -> dict[str, object]:
    i, j = _matches(a.sky_xy, b.sky_xy)
    xy = (a.sky_xy[i] + b.sky_xy[j]) / 2
    blocks = np.floor(xy / 64).astype(np.intp)
    folds = (blocks[:, 1] + 2 * blocks[:, 0]) % 5
    final = folds == 0
    geometry_matches = int(final.sum())
    separation = np.linalg.norm(a.sky_xy[i] - b.sky_xy[j], axis=1)
    displacement = np.linalg.norm(a.detector_xy[i] - b.detector_xy[j], axis=1)
    # Keep both native annuli in their assigned shared block, clear of the boundary.
    low = blocks * 64 + 12
    high = low + 40
    a_inside = ((a.sky_xy[i] >= low) & (a.sky_xy[i] < high)).all(axis=1)
    b_inside = ((b.sky_xy[j] >= low) & (b.sky_xy[j] < high)).all(axis=1)
    photometry = a_inside & b_inside & np.isfinite(a.flux[i] + b.flux[j]).all(axis=1)
    fit = photometry & (folds >= 2)
    training_count = int(fit.sum())
    residual = None
    training_ratios = None
    if training_count >= 8:
        log_ratios = np.full((len(i), len(_MODES)), np.nan)
        log_ratios[photometry] = np.log(b.flux[j[photometry]] / a.flux[i[photometry]])
        offset = np.median(log_ratios[fit], axis=0)
        residual = np.expm1(log_ratios - offset)
        training_ratios = dict(zip(_MODES, np.exp(offset).tolist(), strict=True))
    contrast = np.abs(np.log(b.response[j] / a.response[i]))

    subsets = {}
    for name, minimum in (("all", 0.0), *response_subsets):
        mask = photometry & final & (contrast >= np.log1p(minimum))
        stars = int(mask.sum())
        block_count = len(np.unique(blocks[mask], axis=0))
        metrics: dict[str, object] = {"stars": stars, "blocks": block_count}
        if stars and residual is not None:
            metrics.update(
                signed_median=dict(
                    zip(_MODES, np.median(residual[mask], axis=0).tolist(), strict=True)
                ),
                absolute_p95=dict(
                    zip(
                        _MODES, np.percentile(abs(residual[mask]), 95, axis=0).tolist(), strict=True
                    )
                ),
            )
        subsets[name] = metrics
    return {
        "held_out_geometry_matches": geometry_matches,
        "held_out_geometry_p95_px": (
            float(np.percentile(separation[final], 95)) if geometry_matches >= 8 else None
        ),
        "median_detector_displacement_px": (
            float(np.median(displacement[final])) if geometry_matches else None
        ),
        "training_apertures": training_count,
        "training_flux_ratios": training_ratios,
        "held_out_apertures": subsets,
    }


def measure(folder: Path, reference: Reference = _BASELINE) -> dict[str, object]:
    """Verify every native detector sample, then measure reserved stellar pairs."""
    _check_hashes(folder, reference.hashes)
    region = Region(0, 0, 4096, 4096)
    target = PanelGeometry(
        tan_output_wcs(reference.sky_center, (region.width, region.height), 0.031, 0.0, region),
        ICRS(),
    )
    fields, parity = {}, {}
    with fits.open(folder / reference.flat, memmap=False) as flat:
        for stem in reference.stems:
            fields[stem], parity[stem] = _measure_exposure(folder, stem, flat, target, reference)
    pairs = [
        {
            "panels": [left, right],
            **_compare_pair(fields[left], fields[right], reference.response_subsets),
        }
        for left, right in combinations(reference.stems, 2)
    ]
    _check_hashes(folder, reference.hashes)
    return {
        "schema_version": 1,
        "input_sha256": dict(reference.hashes),
        "max_read_shape": [_TILE + 2 * _HALO] * 2,
        **({"aperture_minimum_snr": reference.minimum_snr} if reference.minimum_snr else {}),
        "native_detector_replay": parity,
        "pairs": pairs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Local folder of the frozen MAST and CRDS files.")
    parser.add_argument("-o", "--output", type=Path, required=True, help="New JSON evidence file.")
    parser.add_argument(
        "--reference", choices=_REFERENCES, default="nrcb2-f150w", help="Frozen archive dataset."
    )
    args = parser.parse_args()
    with atomic_binary_file(args.output) as stream:
        report = measure(args.folder, _REFERENCES[args.reference])
        payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
        stream.write(payload.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
