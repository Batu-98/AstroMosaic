"""Verify feature correspondences against bounded original-pixel patches."""

from math import ceil, floor

import numpy as np
from scipy.ndimage import map_coordinates
from scipy.signal import correlate

from astromosaic.core import Region
from astromosaic.io import PanelSource
from astromosaic.pipeline.control_points import FloatArray, _Transform

_RADIUS = 10
_SEARCH = 7
_PATCH_WORK_BYTES = 1024**2


def _read_patch(
    source: PanelSource, center: complex, step: complex, radius: int, budget: int
) -> FloatArray | None:
    shifts = np.arange(-radius, radius + 1, dtype=np.float64)
    xy = center + step * (shifts[None, :] + 1j * shifts[:, None])
    x0, y0 = floor(xy.real.min()), floor(xy.imag.min())
    x1, y1 = ceil(xy.real.max()), ceil(xy.imag.max())
    if min(x0, y0) < 0 or x1 >= source.descriptor.width or y1 >= source.descriptor.height:
        return None
    region = Region(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
    if source.tile_bytes(region) + _PATCH_WORK_BYTES > budget:
        raise ValueError("The working budget cannot fit a source-resolution feature patch.")
    tile = source.read_tile(region)
    if not tile.valid.all():
        return None
    values = tile.pixels.astype(np.float64)
    if values.ndim == 3:
        values = values.mean(axis=-1)
    return np.asarray(
        map_coordinates(values, (xy.imag - y0, xy.real - x0), order=1, prefilter=False)
    )


def _peak(template: FloatArray, search: FloatArray) -> complex | None:
    template = template - template.mean()
    search = search - search.mean()
    size = template.size
    box = np.ones_like(template)
    total = correlate(search, box, mode="valid", method="direct")
    power = correlate(search**2, box, mode="valid", method="direct") - total**2 / size
    norm = np.sqrt(np.maximum(0, power) * np.sum(template**2))
    score = np.full_like(norm, -1)
    np.divide(
        correlate(search, template, mode="valid", method="direct"),
        norm,
        out=score,
        where=norm > 0,
    )
    y, x = (int(i) for i in np.unravel_index(score.argmax(), score.shape))
    peak = score[y, x]
    if peak < 0.75 or min(x, y) == 0 or max(x, y) == 2 * _SEARCH:
        return None
    # Interpolate the two axial profiles around the peak.
    offsets = []
    for lower, upper in ((score[y, x - 1], score[y, x + 1]), (score[y - 1, x], score[y + 1, x])):
        curvature = 2 * peak - lower - upper
        offsets.append(0.5 * (upper - lower) / curvature if curvature > 0 else 0.0)
    score[max(0, y - 2) : y + 3, max(0, x - 2) : x + 3] = -1
    if peak - score.max() < 0.035:
        return None
    return complex(x - _SEARCH + offsets[0], y - _SEARCH + offsets[1])


def _refine(
    source: PanelSource,
    target: PanelSource,
    left: complex,
    right: complex,
    step: complex,
    budget: int,
) -> complex | None:
    template = _read_patch(source, left, 1, _RADIUS, budget)
    if template is None:
        return None
    search = _read_patch(target, right, step, _RADIUS + _SEARCH, budget)
    if search is None:
        return None
    offset = _peak(template, search)
    return None if offset is None else right + step * offset


def refine_ground_match(
    left_source: PanelSource,
    right_source: PanelSource,
    left: complex,
    right: complex,
    transform: _Transform,
    budget: int,
) -> complex | None:
    """Return the refined right position when a separate reverse check agrees."""
    refined = _refine(left_source, right_source, left, right, 1 / transform.multiplier, budget)
    if refined is None:
        return None
    back = _refine(right_source, left_source, refined, left, transform.multiplier, budget)
    return refined if back is not None and abs(back - left) <= 1.25 else None
