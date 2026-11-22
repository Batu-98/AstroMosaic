"""Sample the shared sky grid and prepare bounded photo corrections."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from math import ceil, floor, isqrt
from os.path import normcase
from pathlib import Path
from threading import Lock
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import maximum_filter

from astromosaic.astrometry.registration import Bounds, overlap, projected_bounds
from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.geometry import PanelGeometry, TileSky, raster_pixels
from astromosaic.photometry import PanelCorrection
from astromosaic.photometry.photo_match import (
    LUMINANCE,
    BrightnessResult,
    fit_brightness,
    metadata_gain,
)
from astromosaic.photometry.photo_settings import BrightnessMode, PhotoSettings
from astromosaic.pipeline.photo_color import PhotoColor, PhotoTileSource
from astromosaic.resampling import sample, source_window

_CELLS = 8
_BLOCK_EDGE = 24
_STAR_HALO = 5
_FIXED_BYTES = 128 * 1024


@dataclass(frozen=True, slots=True)
class PhotoPanel:
    path: Path
    source: PhotoTileSource
    geometry: PanelGeometry
    color: PhotoColor
    ev: float


@dataclass(frozen=True, slots=True)
class PhotoPanelReport:
    panel: str
    color_method: str
    color_origin: str
    profile_sha256: str | None
    profile_preset: str | None
    exposure_method: Literal["off", "manual", "metadata"]
    exposure_gain: float
    exposure_detail: str
    brightness: BrightnessResult = BrightnessResult()
    overlap_reference: int | None = None
    overlap_sampled_pixels: int = 0


@dataclass(frozen=True, slots=True)
class PhotoReport:
    reference_panel: int | None
    panels: tuple[PhotoPanelReport, ...]
    requested_exposure: str
    requested_brightness: str
    peak_fit_bytes: int = 0

    def lines(self) -> list[str]:
        lines = []
        if self.reference_panel is not None:
            lines.append(f"Photo reference: {self.panels[self.reference_panel - 1].panel}")
        for panel in self.panels:
            fit = panel.brightness
            color = panel.profile_preset or panel.color_method
            line = (
                f"{panel.panel}: {color} ({panel.color_origin.replace('_', ' ')}), "
                f"exposure {panel.exposure_method}, ×{panel.exposure_gain:.5g}"
            )
            if panel.exposure_detail:
                line += f" ({panel.exposure_detail})"
            if self.requested_brightness != "off":
                line += f", brightness {fit.method}, ×{fit.gain:.5g}, offset {fit.offset:+.5g}"
                if fit.before_p95 is not None and fit.after_p95 is not None:
                    line += f", held-out RGB P95 {fit.before_p95:.5g} → {fit.after_p95:.5g}"
                if panel.overlap_reference is not None:
                    peer = self.panels[panel.overlap_reference - 1].panel
                    line += (
                        f", overlap with {peer}, {fit.training_samples:,} fit / "
                        f"{fit.held_out_samples:,} held out"
                    )
                if fit.detail:
                    line += f" ({fit.detail})"
            lines.append(line)
        return lines


def _sample_panel(
    panel: PhotoPanel, sky: TileSky, count: int, budget: int
) -> tuple[NDArray[np.float64], int] | None:
    x, y, usable = sky.in_panel(panel.geometry, (0, 0))
    source = panel.source
    width, height = source.descriptor.width, source.descriptor.height
    values = np.full((count, 3), np.nan)
    window = source_window(x, y, usable, width, height)
    if window is None:
        return values, 0
    region = window.region.with_halo(width, height, _STAR_HALO)
    reserved = source.tile_bytes(region, photometry=True)
    if reserved > budget:
        return None
    window.coordinates[0] += window.region.y - region.y
    window.coordinates[1] += window.region.x - region.x
    try:
        indices, samples = sample(
            source.read_photometry_tile(region), replace(window, region=region)
        )
    except (OSError, ValueError) as error:
        raise ValueError(f"{panel.path.name}: {error}") from error
    values[indices] = samples
    return values, reserved


def _quiet_pixels(values: NDArray[np.float64]) -> NDArray[np.bool_]:
    luma = values @ LUMINANCE
    finite = luma[np.isfinite(luma)]
    if not finite.size:
        return np.zeros(luma.shape, np.bool_)
    sky = np.median(finite)
    ceiling = max(0.075, sky + 8 * np.median(np.abs(finite - sky)))
    return np.asarray(
        np.isfinite(luma) & ~maximum_filter(luma > ceiling, size=2 * _STAR_HALO + 1),
        dtype=np.bool_,
    )


def _measure_pair(
    reference: PhotoPanel,
    moving: PhotoPanel,
    target: PanelGeometry,
    area: Bounds,
    reference_gain: float,
    reference_offset: float,
    moving_gain: float,
    mode: BrightnessMode,
    budget: int,
    context: JobContext,
) -> tuple[BrightnessResult, int, int]:
    left, top, right, bottom = ceil(area[0]), ceil(area[1]), floor(area[2]), floor(area[3])
    width, height = right - left + 1, bottom - top + 1
    if min(width, height) <= 0:
        return BrightnessResult(detail="No shared pixel centers."), 0, 0
    # Account for the paired rows, concatenation, robust regression, and the live WCS block.
    edge = min(_BLOCK_EDGE, isqrt(max(0, budget - _FIXED_BYTES) // (2 * _CELLS**2 * 256)))
    if not edge:
        return BrightnessResult(detail="The working budget cannot fit photo overlap samples."), 0, 0
    rows: tuple[list[NDArray[np.float64]], list[NDArray[np.float64]]] = ([], [])
    x_edges = np.linspace(left, right + 1, min(_CELLS, width) + 1, dtype=np.int64)
    y_edges = np.linspace(top, bottom + 1, min(_CELLS, height) + 1, dtype=np.int64)
    row_bytes = _CELLS**2 * edge**2 * 256
    block_bytes = _FIXED_BYTES + row_bytes + (edge + 2 * _STAR_HALO) ** 2 * 1200
    peak = row_bytes
    sampled = 0
    skipped = False
    for row, (y0, y1) in enumerate(zip(y_edges[:-1], y_edges[1:], strict=True)):
        for col, (x0, x1) in enumerate(zip(x_edges[:-1], x_edges[1:], strict=True)):
            context.check_cancelled()
            w, h = min(edge, int(x1 - x0)), min(edge, int(y1 - y0))
            x, y = int((x0 + x1 - w) // 2), int((y0 + y1 - h) // 2)
            block = Region(x, y, w, h).with_halo(right + 1, bottom + 1, _STAR_HALO)
            if block_bytes >= budget:
                skipped = True
                break
            sky = TileSky.from_pixels(target, *raster_pixels(block, (1, 1)))
            a = _sample_panel(reference, sky, block.width * block.height, budget - block_bytes)
            b = _sample_panel(moving, sky, block.width * block.height, budget - block_bytes)
            if a is None or b is None:
                skipped = True
                continue
            peak = max(peak, block_bytes + max(a[1], b[1]))
            av = a[0].reshape(block.height, block.width, 3)
            bv = b[0].reshape(block.height, block.width, 3)
            inner = np.s_[y - block.y : y - block.y + h, x - block.x : x - block.x + w]
            sampled += int(np.count_nonzero(np.isfinite(av[inner]) & np.isfinite(bv[inner])) // 3)
            quiet = (_quiet_pixels(av) & _quiet_pixels(bv))[inner]
            if quiet.any():
                rows[int((row + 2 * col) % 5 == 0)].append(
                    np.stack(
                        (
                            av[inner][quiet] * reference_gain + reference_offset,
                            bv[inner][quiet] * moving_gain,
                        ),
                        axis=1,
                    )
                )
    if not rows[0] or not rows[1]:
        detail = (
            "Some overlap blocks exceed the working budget."
            if skipped
            else "Insufficient spatially split overlap samples."
        )
        return (
            BrightnessResult(
                training_samples=sum(map(len, rows[0])),
                held_out_samples=sum(map(len, rows[1])),
                training_blocks=len(rows[0]),
                held_out_blocks=len(rows[1]),
                detail=detail,
            ),
            sampled,
            peak,
        )
    result = fit_brightness(
        np.concatenate(rows[0]), np.concatenate(rows[1]), len(rows[0]), len(rows[1]), mode
    )
    context.check_cancelled()
    return result, sampled, peak


def _fit_overlaps(
    panels: Sequence[PhotoPanel],
    order: Sequence[int],
    reports: list[PhotoPanelReport],
    target: PanelGeometry,
    size: tuple[int, int],
    mode: BrightnessMode,
    budget: int,
    context: JobContext,
) -> int:
    width, height = size
    full = (0.0, 0.0, float(width - 1), float(height - 1))
    bounds = []
    for panel in panels:
        context.check_cancelled()
        descriptor = panel.source.descriptor
        approximate = projected_bounds(panel.geometry, target, descriptor.width, descriptor.height)
        bounds.append(full if approximate is None else overlap(full, approximate))

    peers = [order[0]]
    pending = list(order[1:])
    peak = 0
    while pending and peers:
        linked: list[int] = []
        for index in pending:
            current = reports[index]
            for peer in peers:
                context.check_cancelled()
                area = overlap(bounds[index], bounds[peer])
                if area is None:
                    continue
                anchor = reports[peer]
                fit, sampled, reserved = _measure_pair(
                    panels[peer],
                    panels[index],
                    target,
                    area,
                    anchor.exposure_gain * anchor.brightness.gain,
                    anchor.brightness.offset,
                    current.exposure_gain,
                    mode,
                    budget,
                    context,
                )
                peak = max(peak, reserved)
                if (
                    fit.method != "off"
                    or current.overlap_reference is None
                    or fit.training_samples > current.brightness.training_samples
                ):
                    current = replace(
                        current,
                        brightness=fit,
                        overlap_reference=peer + 1,
                        overlap_sampled_pixels=sampled,
                    )
                    reports[index] = current
                if fit.method != "off" or (fit.before_p95 is not None and fit.before_p95 <= 2e-6):
                    linked.append(index)
                    break
        peers = linked
        accepted = set(linked)
        pending = [index for index in pending if index not in accepted]
    for index in pending:
        if reports[index].overlap_reference is None:
            reports[index] = replace(
                reports[index],
                brightness=BrightnessResult(detail="No overlap with the reference group."),
            )
    return peak


# Jobs can share a fitted model. The cache retains only diagnostics and scalar corrections.
_cache_lock = Lock()
_cached_fit: tuple[tuple[object, ...], PhotoReport] | None = None


def prepare_photo_fit(
    panels: Sequence[PhotoPanel],
    settings: PhotoSettings,
    target: PanelGeometry,
    size: tuple[int, int],
    budget: int,
    context: JobContext,
) -> tuple[list[PanelCorrection | None], PhotoReport]:
    global _cached_fit
    order = sorted(
        range(len(panels)), key=lambda index: normcase(str(panels[index].path.absolute()))
    )
    anchor = order[0]
    reports = []
    key = None
    report = None
    if settings.brightness != "off":
        key = (
            settings,
            target.wcs.to_header().tostring(),
            size,
            budget,
            tuple(
                (
                    panel.path,
                    panel.geometry.wcs.to_header(relax=True).tostring(),
                    panel.source.descriptor.fingerprint,
                    panel.source.sky_mask_fingerprint,
                    panel.color.method,
                    panel.color.origin,
                    panel.color.profile_sha256,
                    panel.color.preset,
                    panel.source.photo_metadata.exposure if panel.source.photo_metadata else None,
                    panel.ev,
                )
                for panel in panels
            ),
        )
        with _cache_lock:
            if _cached_fit is not None and _cached_fit[0] == key:
                report = _cached_fit[1]
    if report is None:
        reference = panels[anchor].source.photo_metadata
        assert reference is not None
        for panel in panels:
            context.check_cancelled()
            gain, detail = 1.0, ""
            method = settings.exposure
            if method == "manual":
                gain = 2**panel.ev
            elif method == "metadata":
                metadata = panel.source.photo_metadata
                assert metadata is not None
                gain, detail = metadata_gain(reference.exposure, metadata.exposure)
                if detail:
                    method = "off"
            reports.append(
                PhotoPanelReport(
                    panel.path.name,
                    panel.color.method,
                    panel.color.origin,
                    panel.color.profile_sha256,
                    panel.color.preset,
                    method,
                    gain,
                    detail,
                )
            )
        peak = 0
        if settings.brightness != "off" and len(panels) > 1:
            if context.on_stage is not None:
                context.on_stage("photo-overlap")
            peak = _fit_overlaps(
                panels, order, reports, target, size, settings.brightness, budget, context
            )
        reference_panel = (
            anchor + 1
            if (settings.exposure == "metadata" or settings.brightness != "off")
            else None
        )
        report = PhotoReport(
            reference_panel, tuple(reports), settings.exposure, settings.brightness, peak
        )
        if key is not None:
            context.check_cancelled()
            with _cache_lock:
                _cached_fit = (key, report)
    corrections = []
    for item in report.panels:
        gain = item.exposure_gain * item.brightness.gain
        offset = item.brightness.offset
        correction = PanelCorrection(gain=gain, background=(offset, 0.0, 0.0))
        corrections.append(correction if gain != 1 or offset != 0 else None)
    return corrections, report
