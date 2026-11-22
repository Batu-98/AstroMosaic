"""Independent aperture measurements and acceptance of linked photo gains."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import expm1, log, log1p, sqrt
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from astromosaic.core import Region, Tile

LUMINANCE = (0.2126, 0.7152, 0.0722)
GAIN_TOLERANCE = log1p(0.01)
_RADIUS = 13
_MIN_STARS = 8
_MIN_BLOCKS = 3

type Block = tuple[int, int]


@dataclass(frozen=True, slots=True)
class Aperture:
    xy: tuple[float, float]
    block: Block
    flux: float
    scale: float = 1.0


@dataclass(frozen=True, slots=True)
class StellarGainCheck:
    stars: int = 0
    blocks: int = 0
    status: Literal["supported", "rejected", "insufficient"] = "insufficient"
    reason: str = "Insufficient matched stars or spatial blocks."
    median_before: float | None = None
    median_after: float | None = None
    block_abs_log_error_p80: float | None = None
    candidate_gain: float | None = None


def aperture_region(x: float, y: float) -> Region:
    side = 2 * (_RADIUS + 1)
    return Region(int(x) - _RADIUS, int(y) - _RADIUS, side, side)


def aperture_intersects(x: float, y: float, region: Region, halo: int) -> bool:
    """Test the circular aperture and annulus against a detector read and clipping halo."""
    dx = max(0.0, region.x - halo - x, x - (region.x + region.width - 1 + halo))
    dy = max(0.0, region.y - halo - y, y - (region.y + region.height - 1 + halo))
    return dx * dx + dy * dy <= _RADIUS**2


def aperture_masks(
    region: Region, x: float, y: float
) -> tuple[NDArray[np.bool_], NDArray[np.bool_]]:
    yy, xx = np.mgrid[region.y : region.y + region.height, region.x : region.x + region.width]
    distance = (xx - x) ** 2 + (yy - y) ** 2
    return distance <= 7**2, (distance >= 10**2) & (distance <= _RADIUS**2)


def aperture_flux(tile: Tile, x: float, y: float) -> float | None:
    core, sky = aperture_masks(tile.region, x, y)
    if not tile.valid[core | sky].all():
        return None
    background = np.median(tile.pixels[sky], axis=0)
    flux_rgb = (tile.pixels[core] - background).sum(axis=0, dtype=np.float64)
    flux = float(flux_rgb @ LUMINANCE)
    residual = (tile.pixels[sky] - background) @ LUMINANCE
    sigma = 1.4826 * np.median(np.abs(residual - np.median(residual)))
    if np.all(flux_rgb > 0) and flux > 10 * sigma * sqrt(int(core.sum())):
        return flux
    return None


def matched_apertures(
    left: Sequence[Aperture], right: Sequence[Aperture]
) -> list[tuple[Aperture, Aperture]]:
    if not left or not right:
        return []
    a = np.asarray([star.xy for star in left])
    b = np.asarray([star.xy for star in right])
    distances, nearest = cKDTree(b).query(a, k=2, distance_upper_bound=1.0)
    _, reverse = cKDTree(a).query(b, distance_upper_bound=1.0)
    possible = np.flatnonzero(
        np.isfinite(distances[:, 0]) & (distances[:, 0] <= 0.8 * distances[:, 1])
    )
    result = []
    for i in possible.tolist():
        j = int(nearest[i, 0])
        first, second = left[i], right[j]
        if (
            reverse[j] == i
            and first.block == second.block
            and max(first.scale, second.scale) <= 1.03 * min(first.scale, second.scale)
        ):
            result.append((first, second))
    return result


def check_stellar_gain(
    matches: Sequence[tuple[Aperture, Aperture]], log_gain: float, log_exposure: float = 0
) -> StellarGainCheck:
    rows: dict[Block, list[float]] = {}
    for left, right in matches:
        rows.setdefault(left.block, []).append(log(right.flux / left.flux))
    if not rows:
        return StellarGainCheck()
    medians = np.array([np.median(ratios) for ratios in rows.values()]) + log_exposure
    before = float(np.median(medians))
    after = before + log_gain
    block_error = float(np.percentile(np.abs(medians + log_gain), 80))
    count = len(matches)
    if count < _MIN_STARS or len(rows) < _MIN_BLOCKS:
        status: Literal["supported", "rejected", "insufficient"] = "insufficient"
        reason = "Insufficient matched stars or spatial blocks."
    else:
        problems = []
        if abs(after) > log1p(0.05) or block_error > log1p(0.12):
            problems.append("Corrected stellar ratios differ from unity.")
        if abs(after) > abs(before) + log1p(0.02):
            problems.append("The gain worsens the stellar ratio relative to Off.")
        status = "rejected" if problems else "supported"
        reason = " ".join(problems)
    return StellarGainCheck(
        count, len(rows), status, reason, expm1(before), expm1(after), block_error
    )
