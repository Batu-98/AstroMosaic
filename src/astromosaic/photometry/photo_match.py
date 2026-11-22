"""Qualify linked sky offsets and gains on independent overlap samples."""

from dataclasses import dataclass, replace
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from astromosaic.astrometry.registration import robust_linear_fit
from astromosaic.io.tiff_metadata import CameraExposure
from astromosaic.photometry.photo_settings import BrightnessMode

LUMINANCE = (0.2126, 0.7152, 0.0722)
_MIN_SAMPLES = 128
_MIN_SPAN = 0.003
_MAX_OFFSET = 0.1
_MIN_IMPROVEMENT = 2e-6


def metadata_gain(reference: CameraExposure, other: CameraExposure) -> tuple[float, str]:
    if reference.conflicting or other.conflicting:
        return 1.0, "Conflicting camera exposure metadata."
    if not reference.camera or not other.camera:
        return 1.0, "Camera model is missing."
    if reference.camera != other.camera or reference.make != other.make:
        return 1.0, "Camera provenance differs from the reference."
    if (
        reference.seconds is None
        or other.seconds is None
        or reference.f_number is None
        or other.f_number is None
        or reference.iso is None
        or other.iso is None
    ):
        return 1.0, "Shutter time, aperture or ISO is missing."
    if reference.iso != other.iso:
        return 1.0, "ISO differs and no sensor gain model is available."
    # Use logarithms to retain a finite result for extreme metadata values.
    ev = (
        np.log2(reference.seconds)
        - np.log2(other.seconds)
        + 2 * (np.log2(other.f_number) - np.log2(reference.f_number))
    )
    if not -16 <= ev <= 16:
        return 1.0, "Metadata implies a gain outside the supported EV range."
    return float(2**ev), ""


@dataclass(frozen=True, slots=True)
class BrightnessResult:
    method: Literal["off", "sky-offset", "offset-only", "standard"] = "off"
    gain: float = 1.0
    offset: float = 0.0  # Affine intercept on the exposure-normalized samples.
    sky: float | None = None
    training_samples: int = 0
    held_out_samples: int = 0
    retained_samples: int = 0
    training_blocks: int = 0
    held_out_blocks: int = 0
    luminance_span: float | None = None
    before_p95: float | None = None
    after_p95: float | None = None
    detail: str = ""


def fit_brightness(
    training: NDArray[np.float64],
    held_out: NDArray[np.float64],
    training_blocks: int,
    held_out_blocks: int,
    method: BrightnessMode,
) -> BrightnessResult:
    """Fit paired RGB samples, with the reference at index zero of each pair."""
    stats = BrightnessResult(
        training_samples=len(training),
        held_out_samples=len(held_out),
        training_blocks=training_blocks,
        held_out_blocks=held_out_blocks,
    )
    if (
        min(len(training), len(held_out)) < _MIN_SAMPLES
        or min(training_blocks, held_out_blocks) < 2
    ):
        return replace(stats, detail="Insufficient spatially split overlap samples.")
    reference, moving = (training @ LUMINANCE).T
    sky, moving_sky = np.percentile(reference, 20), np.percentile(moving, 20)
    low, high = np.percentile(moving, [5, 95])
    span = float(high - low)
    valid_reference, valid_moving = np.moveaxis(held_out, 1, 0)

    def p95(gain: float = 1.0, offset: float = 0.0) -> float:
        return float(np.percentile(np.abs(valid_reference - (valid_moving * gain + offset)), 95))

    position = moving - moving_sky
    target = reference - sky
    sky_delta = float(sky - moving_sky)
    offset = sky_delta + float(np.median(target - position))
    before = p95()
    offset_p95 = p95(offset=offset)
    best = before
    measured = replace(stats, sky=float(sky), luminance_span=span, before_p95=before)
    effective = replace(
        measured,
        after_p95=before,
        detail="No qualified sky offset improved the held-out RGB residual.",
    )
    if abs(offset) <= _MAX_OFFSET and offset_p95 < before - _MIN_IMPROVEMENT:
        best = offset_p95
        effective = replace(
            measured,
            method="sky-offset" if method == "sky-offset" else "offset-only",
            offset=offset,
            retained_samples=len(training),
            after_p95=offset_p95,
        )
    if method != "standard":
        return effective

    def fallback(reason: str) -> BrightnessResult:
        return replace(effective, detail=f"{reason} {effective.detail}".strip())

    if span < _MIN_SPAN:
        return fallback("Luminance variation is too low to fit a gain.")
    design = np.column_stack((position, np.ones_like(position)))
    gain, residual = map(
        float, robust_linear_fit(design, target[:, None], np.ones_like(position)).ravel()
    )
    errors = np.abs(position * gain + residual - target)
    inliers = errors <= max(_MIN_IMPROVEMENT, 3.5 * float(np.median(errors)))
    kept = int(np.count_nonzero(inliers))
    if kept < _MIN_SAMPLES:
        return fallback("Too few overlap samples agree on a gain.")
    low, high = np.percentile(moving[inliers], [5, 95])
    if high - low < _MIN_SPAN:
        return fallback("Gain inliers have too little luminance variation.")
    gain, residual = map(float, np.linalg.lstsq(design[inliers], target[inliers], rcond=None)[0])
    offset = float(sky - gain * moving_sky + residual)
    if not 0.25 <= gain <= 4 or abs(offset) > _MAX_OFFSET:
        return fallback("Gain or offset is outside the supported fitting range.")
    after = p95(gain, offset)
    if after >= best - max(_MIN_IMPROVEMENT, 0.01 * best):
        return fallback("Gain did not improve the held-out RGB residual.")
    return replace(
        measured,
        method="standard",
        gain=gain,
        offset=offset,
        retained_samples=kept,
        after_p95=after,
    )
