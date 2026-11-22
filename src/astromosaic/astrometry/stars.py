"""Bounded SEP detection and local aperture measurements on valid sky."""

from dataclasses import dataclass
from math import isfinite
from typing import cast

import numpy as np
import sep
from numpy.typing import NDArray
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree

from astromosaic.core import Region, Tile
from astromosaic.core.job import JobContext
from astromosaic.io import PanelSource

_HALO = 24
_STAR_LIMIT = 1500
_EXCLUSION_LIMIT = 6000
_DETECTION_OVERHEAD = 4 * 1024**2  # SEP stacks, bookkeeping, and retained measurements


class StarBudgetError(ValueError):
    """A star detection window and its halo do not fit the working budget."""


@dataclass(frozen=True, slots=True)
class Star:
    x: float
    y: float
    flux: float
    fwhm: float


@dataclass(frozen=True, slots=True)
class StarField:
    stars: tuple[Star, ...]
    exclusions: NDArray[np.float64]


def astrometry_pixels(tile: Tile) -> NDArray[np.float32]:
    """Use green as the astrometry signal for RGB while preserving the original channels."""
    return tile.pixels if tile.pixels.ndim == 2 else tile.pixels[..., 1]


def _detect_tile(
    tile: Tile, owned: Region, saturation: float | None
) -> tuple[list[Star], list[Star]]:
    if np.count_nonzero(tile.valid) < 32:
        return [], []
    masked = ~tile.valid
    data = np.where(tile.valid, astrometry_pixels(tile), np.float32(0))
    sky = sep.Background(data, mask=masked, bw=32, bh=32)
    residual = data - sky.back()
    rms = np.maximum(sky.rms(), np.finfo(np.float32).eps)
    objects = sep.extract(residual, 5.0, err=rms, mask=masked, minarea=5)
    if not len(objects):
        return [], []

    x, y = objects["x"], objects["y"]
    height, width = data.shape
    origin_x, origin_y = tile.region.x, tile.region.y
    global_x, global_y = x + origin_x, y + origin_y
    owned_before = (
        (global_x >= owned.x)
        & (global_x < owned.x + owned.width)
        & (global_y >= owned.y)
        & (global_y < owned.y + owned.height)
    )
    sigma = np.sqrt(objects["a"] * objects["b"])
    exclusions = [
        Star(float(gx), float(gy), float(obj["flux"]), float(fwhm))
        for gx, gy, obj, fwhm in zip(
            global_x[owned_before],
            global_y[owned_before],
            objects[owned_before],
            (2.355 * sigma)[owned_before],
            strict=True,
        )
    ]
    radii = np.clip(4 * sigma, 6.0, 17.0)
    annulus = radii + 6
    # Include neighbors in the halo so blends and contaminated local backgrounds are rejected.
    xy = np.column_stack((x, y))
    distance = cKDTree(xy).query(xy, k=2)[0][:, 1]
    candidates = (
        (objects["flag"] == 0)
        & (sigma >= 0.8)
        & (sigma <= 4.5)
        & (objects["b"] >= 0.6 * objects["a"])
        & (distance > annulus + 3)
        & (x >= annulus)
        & (x < width - 1 - annulus)
        & (y >= annulus)
        & (y < height - 1 - annulus)
    )
    if saturation is not None:
        candidates &= data[objects["ypeak"], objects["xpeak"]] < saturation
    if not np.any(candidates):
        return [], exclusions

    x, y, sizes, aperture = x[candidates], y[candidates], sigma[candidates], radii[candidates]
    if masked.any():
        mask_distance = distance_transform_edt(tile.valid)
        clear = mask_distance[np.rint(y).astype(int), np.rint(x).astype(int)] > aperture + 7
        x, y, sizes, aperture = x[clear], y[clear], sizes[clear], aperture[clear]
    if not x.size:
        return [], exclusions
    x, y, centroid_flags = sep.winpos(residual, x, y, sizes, mask=masked)
    # Measure the original linear samples with a local annulus after centroid refinement.
    flux, _, aperture_flags = sep.sum_circle(
        data, x, y, aperture, mask=masked, bkgann=(aperture + 2, aperture + 6), subpix=5
    )
    x += origin_x
    y += origin_y
    keep = (
        (centroid_flags == 0)
        & (aperture_flags == 0)
        & np.isfinite(flux)
        & (flux > 0)
        & (x >= owned.x)
        & (x < owned.x + owned.width)
        & (y >= owned.y)
        & (y < owned.y + owned.height)
    )
    return [
        Star(float(sx), float(sy), float(total), float(2.355 * size))
        for sx, sy, total, size in zip(x[keep], y[keep], flux[keep], sizes[keep], strict=True)
    ], exclusions


def measure_stars(source: PanelSource, max_working_bytes: int, context: JobContext) -> StarField:
    """Read tiled sky, keeping the brightest usable measurements and exclusion positions."""
    descriptor = source.descriptor
    width, height = descriptor.width, descriptor.height
    saturation = source.header.get("SATURATE")
    if saturation is not None:
        saturation = float(saturation)
        if not isfinite(saturation):
            raise ValueError("Expected a finite calibrated SATURATE threshold.")

    step = 192
    while True:
        window = Region(0, 0, min(width, step + 2 * _HALO), min(height, step + 2 * _HALO))
        estimate = source.tile_bytes(window) + 112 * window.width * window.height
        if estimate + _DETECTION_OVERHEAD <= max_working_bytes:
            break
        step //= 2
        if step < 12:
            raise StarBudgetError(
                "The working budget cannot fit a star detection tile and its halo."
            )

    stars: list[Star] = []
    exclusion_stars: list[Star] = []
    for y in range(0, height, step):
        for x in range(0, width, step):
            context.check_cancelled()
            region = Region(x, y, min(step, width - x), min(step, height - y))
            measured, exclusions = _detect_tile(
                source.read_tile(region, halo=_HALO), region, saturation
            )
            stars.extend(measured)
            exclusion_stars.extend(exclusions)
            stars = sorted(stars, key=lambda star: -star.flux)[:_STAR_LIMIT]
            exclusion_stars = sorted(exclusion_stars, key=lambda star: -star.flux)[
                :_EXCLUSION_LIMIT
            ]

    context.check_cancelled()
    positions = np.array(
        [(star.x, star.y, min(36.0, max(9.0, 3 * star.fwhm))) for star in exclusion_stars],
        dtype=np.float64,
    ).reshape(-1, 3)
    return StarField(tuple(stars), cast(NDArray[np.float64], positions))
