"""Fit a bounded ICRS preview grid to the selected sky footprints."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from math import atan2, degrees, hypot, isqrt
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from astropy import units as u
from astropy.coordinates import ICRS, SkyCoord

from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.geometry import PanelGeometry, SkyProjection, sky_output_wcs
from astromosaic.geometry.footprint import MAX_FOOTPRINT_COORDINATE

if TYPE_CHECKING:
    from astromosaic.pipeline.mosaic import RenderSpec


def _footprint(geometry: PanelGeometry, region: Region, edge: int) -> SkyCoord:
    x = np.linspace(region.x - 0.5, region.x + region.width - 0.5, edge)
    y = np.linspace(region.y - 0.5, region.y + region.height - 0.5, edge)
    grid_x, grid_y = np.meshgrid(x, y)
    sky = geometry.forward(grid_x.ravel(), grid_y.ravel()).icrs
    return sky[np.isfinite(sky.ra.deg) & np.isfinite(sky.dec.deg)]


def fit_preview_grid(
    spec: RenderSpec,
    panels: Sequence[tuple[Path, PanelGeometry, Region]],
    context: JobContext,
) -> RenderSpec:
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
    center = (degrees(atan2(y, x)) % 360, degrees(atan2(z, hypot(x, y))))
    scale_arcsec = float(np.median(scales))
    projection: SkyProjection = spec.projection
    pointing = SkyCoord(*center, unit="deg", frame="icrs")

    while True:
        retry_with_zea = False
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
        for _, geometry, region in panels:
            context.check_cancelled()
            sky = _footprint(geometry, region, edge)
            farthest = np.max(sky.separation(pointing).deg)
            if projection == "TAN" and farthest >= 75:
                retry_with_zea = True
                break
            if projection == "ZEA" and farthest >= 170:
                # The azimuth at the antipode is indeterminate. Enclose the whole disk.
                radius = 2 * degrees(1) * 3600 / scale_arcsec
                lower, upper = np.full(2, -radius), np.full(2, radius)
                break
            pixels = target.inverse(sky)
            lower = np.minimum(lower, pixels.min(axis=0))
            upper = np.maximum(upper, pixels.max(axis=0))
        if not retry_with_zea:
            break
        projection = "ZEA"

    padding = 2 + 0.02 * (upper - lower)
    lower = np.floor(lower - padding)
    upper = np.ceil(upper + padding)
    extent = np.maximum(-lower, upper)
    if not np.isfinite(extent).all() or np.any(extent > MAX_FOOTPRINT_COORDINATE):
        raise ValueError(
            "The fitted sky grid is outside supported limits. Choose a grid in Mosaic Settings."
        )
    half_width, half_height = map(int, extent)
    width, height = 2 * half_width + 1, 2 * half_height + 1
    left, top = map(int, lower)
    right, bottom = map(int, upper)
    crop = Region(left + half_width, top + half_height, right - left + 1, bottom - top + 1)
    return replace(
        spec,
        center=center,
        size=(width, height),
        scale_arcsec=scale_arcsec,
        projection=projection,
        crop=None if crop == Region(0, 0, width, height) else crop,
    )
