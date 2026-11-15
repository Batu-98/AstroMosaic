"""Fit an anchored offset or plane to paired, star-masked sky samples."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt
from typing import Literal, cast

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from astromosaic.astrometry.registration import (
    Bounds,
    FloatArray,
    components,
    overlap,
    robust_linear_fit,
)
from astromosaic.core.job import JobContext
from astromosaic.geometry import PanelGeometry, TileSky
from astromosaic.io import PanelSource
from astromosaic.photometry import normalized_pixel
from astromosaic.resampling import sample, source_window

BackgroundMode = Literal["none", "offset", "plane"]
_GRID_SIDE = 26
_MIN_PAIR_SAMPLES = 32


@dataclass(frozen=True, slots=True)
class BackgroundPanel:
    source: PanelSource
    geometry: PanelGeometry
    bounds: Bounds | None
    exclusions: FloatArray
    shift: tuple[float, float]
    gain: float


@dataclass(frozen=True, slots=True)
class BackgroundReport:
    model: BackgroundMode
    samples: int
    held_out: int
    uncorrected_median: float | None
    corrected_median: float | None
    detail: str


@dataclass(frozen=True, slots=True)
class _Overlap:
    panels: tuple[int, int]
    left_xy: FloatArray
    right_xy: FloatArray
    difference: FloatArray


def _shifted_bounds(panel: BackgroundPanel) -> Bounds | None:
    if panel.bounds is None:
        return None
    x0, y0, x1, y1 = panel.bounds
    dx, dy = panel.shift
    return x0 + dx, y0 + dy, x1 + dx, y1 + dy


def _sample_group(
    source: PanelSource,
    x: FloatArray,
    y: FloatArray,
    selected: NDArray[np.intp],
    out: FloatArray,
    budget: int,
    context: JobContext,
) -> None:
    context.check_cancelled()
    descriptor = source.descriptor
    window = source_window(
        x[selected],
        y[selected],
        np.ones(selected.size, dtype=np.bool_),
        descriptor.width,
        descriptor.height,
    )
    if window is None:
        return
    if source.tile_bytes(window.region) + 512 * selected.size <= budget:
        indices, samples = sample(source.read_tile(window.region), window)
        out[selected[indices]] = samples
        return
    if selected.size < 2:
        raise ValueError("The working budget cannot fit a background sample window.")
    mid = selected.size // 2
    _sample_group(source, x, y, selected[:mid], out, budget, context)
    _sample_group(source, x, y, selected[mid:], out, budget, context)


def _sky_samples(
    panel: BackgroundPanel, sky: TileSky, budget: int, context: JobContext
) -> tuple[FloatArray, FloatArray]:
    x, y, usable = sky.in_panel(panel.geometry, panel.shift)
    indices = np.flatnonzero(usable)
    if indices.size and panel.exclusions.size:
        exclusions = panel.exclusions
        distance, nearest = cKDTree(exclusions[:, :2]).query(
            np.column_stack((x[indices], y[indices]))
        )
        indices = indices[distance > exclusions[nearest, 2] + 1]
    samples = np.full(x.size, np.nan)
    _sample_group(panel.source, x, y, indices, samples, budget, context)
    descriptor = panel.source.descriptor
    coordinates = np.column_stack(
        (normalized_pixel(x, descriptor.width), normalized_pixel(y, descriptor.height))
    )
    return samples * panel.gain, coordinates


def _measure_overlap(
    panels: Sequence[BackgroundPanel],
    pair: tuple[int, int],
    target: PanelGeometry,
    budget: int,
    context: JobContext,
) -> _Overlap | None:
    left, right = (panels[index] for index in pair)
    area = overlap(_shifted_bounds(left), _shifted_bounds(right))
    if area is None:
        return None
    lo_x, lo_y, hi_x, hi_y = area
    grid = (np.arange(_GRID_SIDE, dtype=np.float64) + 0.5) / _GRID_SIDE
    x, y = np.meshgrid(lo_x + grid * (hi_x - lo_x), lo_y + grid * (hi_y - lo_y))
    sky = TileSky.from_pixels(target, x.ravel(), y.ravel())
    left_values, left_xy = _sky_samples(left, sky, budget, context)
    right_values, right_xy = _sky_samples(right, sky, budget, context)
    common = np.isfinite(left_values) & np.isfinite(right_values)
    if np.count_nonzero(common) < _MIN_PAIR_SAMPLES:
        return None
    return _Overlap(
        pair, left_xy[common], right_xy[common], left_values[common] - right_values[common]
    )


def _design(
    overlaps: Sequence[_Overlap], count: int, terms: int
) -> tuple[FloatArray, FloatArray, FloatArray, NDArray[np.bool_]]:
    rows = sum(item.difference.size for item in overlaps)
    matrix = np.zeros((rows, count * terms))
    values = np.empty((rows, 1))
    weights = np.empty(rows)
    held_out = np.zeros(rows, dtype=np.bool_)
    start = 0
    for item in overlaps:
        left, right = item.panels
        size = item.difference.size
        end = start + size
        values[start:end, 0] = item.difference
        weights[start:end] = 1 / sqrt(size)
        held_out[start:end:5] = True
        matrix[start:end, left * terms] = -1
        matrix[start:end, right * terms] = 1
        if terms == 3:
            matrix[start:end, left * terms + 1 : (left + 1) * terms] = -item.left_xy
            matrix[start:end, right * terms + 1 : (right + 1) * terms] = item.right_xy
        start = end
    return matrix[:, terms:], values, weights, held_out


def _fit_model(
    overlaps: Sequence[_Overlap], count: int, terms: int, budget: int
) -> tuple[FloatArray, float, float, int] | None:
    rows = sum(item.difference.size for item in overlaps)
    if 48 * rows * count * terms + 1024**2 > budget:
        return None
    matrix, values, weights, held = _design(overlaps, count, terms)
    train = ~held
    singular = np.linalg.svd(matrix[train] * weights[train, None], compute_uv=False)
    if singular.size < matrix.shape[1] or singular[-1] < 0.015 * singular[0]:
        return None
    design, response, base = matrix[train], values[train], weights[train]
    if terms == 3:
        # A small slope penalty reduces extrapolation from uneven overlap support.
        penalty = np.diag(np.tile([0.0, 0.01, 0.01], count - 1))
        design = np.vstack((design, penalty))
        response = np.vstack((response, np.zeros((penalty.shape[0], 1))))
        base = np.concatenate((base, np.ones(penalty.shape[0])))
    solution = robust_linear_fit(design, response, base)
    error = float(np.median(np.abs((matrix[held] @ solution) - values[held])))
    initial = float(np.median(np.abs(values[held])))
    coefficients = np.zeros((count, 3))
    coefficients[1:, :terms] = solution.reshape(count - 1, terms)
    return coefficients, initial, error, int(held.sum())


def fit_background(
    panels: Sequence[BackgroundPanel],
    pairs: Sequence[tuple[int, int]],
    target: PanelGeometry,
    mode: BackgroundMode,
    budget: int,
    context: JobContext,
) -> tuple[FloatArray, BackgroundReport]:
    count = len(panels)
    coefficients = np.zeros((count, 3))
    if mode == "none":
        return coefficients, BackgroundReport("none", 0, 0, None, None, "Background fit disabled.")
    samples = []
    for pair in pairs:
        item = _measure_overlap(panels, pair, target, budget, context)
        if item is not None:
            samples.append(item)
    rows = sum(item.difference.size for item in samples)
    if len(components(count, [item.panels for item in samples])) > 1:
        return coefficients, BackgroundReport(
            "none", rows, 0, None, None, "Insufficient unmasked overlap support."
        )

    context.check_cancelled()
    offset = _fit_model(samples, count, 1, budget)
    if offset is None:
        return coefficients, BackgroundReport(
            "none", rows, 0, None, None, "Offset fit exceeded its rank or memory limit."
        )
    values, baseline, error, held = offset
    model: BackgroundMode = "none"
    detail = "Held-out overlap error did not improve with an offset."
    best = baseline
    if error < 0.95 * best:
        coefficients, best, model, detail = values, error, "offset", "Held-out offset improvement."

    if mode == "plane":
        context.check_cancelled()
        plane = _fit_model(samples, count, 3, budget)
        if plane is not None and plane[2] < 0.85 * best:
            coefficients, _, best, _ = plane
            model, detail = "plane", "Held-out plane improvement."
        else:
            detail += (
                " A plane requires stable support and at least 15% further held-out improvement."
            )
    return cast(FloatArray, coefficients), BackgroundReport(
        model, rows, held, baseline, best, detail
    )
