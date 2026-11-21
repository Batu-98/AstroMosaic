"""Fit a bounded ICRS preview grid to the selected sky footprints."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from math import atan2, degrees, hypot, isqrt
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
from astropy import units as u
from astropy.coordinates import ICRS, SkyCoord
from numpy.typing import NDArray

from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.geometry import PanelGeometry, SkyProjection, sky_output_wcs
from astromosaic.geometry.footprint import MAX_FOOTPRINT_COORDINATE

if TYPE_CHECKING:
    from astromosaic.pipeline.mosaic import RenderSpec


type FrameLock = Literal["center", "projection", "size", "scale", "crop"]
FRAME_LOCKS: frozenset[FrameLock] = frozenset(("center", "projection", "size", "scale", "crop"))
_ROTATION_STEPS = tuple(range(-45, 46, 3))


@dataclass(frozen=True, slots=True)
class FramingFit:
    grid: RenderSpec
    suggested_crop: Region
    suggested_rotation: float | None


def _footprint(geometry: PanelGeometry, region: Region, edge: int) -> SkyCoord:
    x = np.linspace(region.x - 0.5, region.x + region.width - 0.5, edge)
    y = np.linspace(region.y - 0.5, region.y + region.height - 0.5, edge)
    grid_x, grid_y = np.meshgrid(x, y)
    sky = geometry.forward(grid_x.ravel(), grid_y.ravel()).icrs
    return sky[np.isfinite(sky.ra.deg) & np.isfinite(sky.dec.deg)]


def _rotation_extents(
    points: NDArray[np.float64], lower: NDArray[np.float64], upper: NDArray[np.float64]
) -> None:
    for index, delta in enumerate(_ROTATION_STEPS):
        theta = np.deg2rad(delta)
        cos, sin = np.cos(theta), np.sin(theta)
        rotated = points @ np.array([[cos, -sin], [sin, cos]])
        lower[index] = np.minimum(lower[index], rotated.min(axis=0))
        upper[index] = np.maximum(upper[index], rotated.max(axis=0))


def _coverage_crop(
    lower: NDArray[np.float64], upper: NDArray[np.float64], size: tuple[int, int]
) -> Region:
    width, height = size
    origin = (np.asarray(size, np.float64) - 1) / 2
    left, top = map(int, np.maximum(np.floor(lower + origin), 0))
    right, bottom = map(int, np.minimum(np.ceil(upper + origin) + 1, size))
    if right <= left or bottom <= top:
        return Region(0, 0, width, height)
    return Region(left, top, right - left, bottom - top)


def fit_preview_grid(
    spec: RenderSpec,
    panels: Sequence[tuple[Path, PanelGeometry, Region]],
    context: JobContext,
    *,
    locks: frozenset[FrameLock] = frozenset(),
) -> FramingFit:
    """Estimate the output framing without reading panel pixels or changing the saved grid."""
    edge = min(33, isqrt(spec.max_working_bytes // 1024))
    if edge < 3:
        raise ValueError("The working byte budget cannot fit the automatic framing samples.")

    direction = np.zeros(3, dtype=np.float64)
    fallback = direction.copy()
    scales: list[float] = []
    for path, geometry, region in panels:
        context.check_cancelled()
        sky = _footprint(geometry, region, edge)
        scale = [item.to_value(u.arcsec) for item in geometry.wcs.proj_plane_pixel_scales()]
        if sky.size == 0 or not all(np.isfinite(item) and item > 0 for item in scale):
            raise ValueError(
                f"{path.name} has no usable sky footprint or pixel scale. Plate solve it again."
            )
        unit_vectors = sky.cartesian.xyz.value
        direction += unit_vectors.mean(axis=1)
        if not scales:
            fallback = unit_vectors[:, sky.size // 2]
        scales.extend(scale)

    if np.linalg.norm(direction) <= 1e-6 * len(panels):
        direction = fallback
    x, y, z = direction
    center = (
        spec.center if "center" in locks
        else (degrees(atan2(y, x)) % 360, degrees(atan2(z, hypot(x, y))))
    )
    scale_arcsec = spec.scale_arcsec if "scale" in locks else float(np.median(scales))
    projection: SkyProjection = spec.projection
    pointing = SkyCoord(*center, unit="deg", frame="icrs")

    while True:
        retry_with_zea = False
        full_disk = False
        target = PanelGeometry(
            sky_output_wcs(
                center,
                (1, 1),
                scale_arcsec,
                spec.rotation_deg,
                Region(0, 0, 1, 1),
                projection=projection,
            ),
            ICRS(),
        )
        lower = np.full(2, np.inf)
        upper = -lower.copy()
        rotation_lower = np.full((len(_ROTATION_STEPS), 2), np.inf)
        rotation_upper = -rotation_lower.copy()
        for _, geometry, region in panels:
            context.check_cancelled()
            sky = _footprint(geometry, region, edge)
            separation = sky.separation(pointing).deg
            farthest = np.max(separation)
            if projection == "TAN" and farthest >= 75 and "projection" not in locks:
                retry_with_zea = True
                break
            if projection == "TAN" and farthest >= 90:
                if "size" not in locks:
                    raise ValueError("Unlock the TAN projection or choose ZEA to frame this field.")
                sky = sky[separation < 90]
                if not sky.size:
                    continue
            if projection == "ZEA" and farthest >= 170:
                # The azimuth at the antipode is indeterminate. Enclose the whole disk.
                radius = 2 * degrees(1) * 3600 / scale_arcsec
                lower, upper = np.full(2, -radius), np.full(2, radius)
                full_disk = True
                break
            pixels = target.inverse(sky)
            pixels = pixels[np.isfinite(pixels).all(axis=1)]
            if not pixels.size:
                continue
            _rotation_extents(pixels, rotation_lower, rotation_upper)
            lower = np.minimum(lower, pixels.min(axis=0))
            upper = np.maximum(upper, pixels.max(axis=0))
        if not retry_with_zea:
            break
        projection = "ZEA"

    if not np.isfinite(lower).all():
        if "size" in locks:
            return FramingFit(spec, spec.output_region(), None)
        raise ValueError("The selected projection has no usable sky footprint.")
    rotation = None
    if not full_disk:
        areas = np.prod(rotation_upper - rotation_lower, axis=1)
        best = int(np.argmin(areas))
        if areas[best] < 0.98 * areas[_ROTATION_STEPS.index(0)]:
            rotation = float((spec.rotation_deg + _ROTATION_STEPS[best] + 180) % 360 - 180)
    padding = 2 + 0.02 * (upper - lower)
    lower = np.floor(lower - padding)
    upper = np.ceil(upper + padding)
    if "size" in locks or ("crop" in locks and spec.crop is not None):
        size = spec.size
    else:
        extent = np.maximum(-lower, upper)
        if not np.isfinite(extent).all() or np.any(extent > MAX_FOOTPRINT_COORDINATE):
            raise ValueError(
                "The fitted sky grid is outside supported limits. Choose a grid in Mosaic Settings."
            )
        half_width, half_height = map(int, extent)
        size = (2 * half_width + 1, 2 * half_height + 1)
    suggested = _coverage_crop(lower, upper, size)
    crop = spec.crop if "crop" in locks else suggested
    grid = replace(
        spec,
        center=center,
        size=size,
        scale_arcsec=scale_arcsec,
        projection=projection,
        crop=None if crop == Region(0, 0, *size) else crop,
    )
    return FramingFit(grid, suggested, rotation)
