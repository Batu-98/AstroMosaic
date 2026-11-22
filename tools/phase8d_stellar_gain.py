"""Measure independent stellar support for the offline photo overlap candidates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import expm1, isfinite, log1p, sqrt
from typing import TypedDict, cast

import numpy as np
from scipy.spatial import cKDTree

from astromosaic.astrometry.stars import measure_stars
from astromosaic.core import Region
from astromosaic.core.job import DEFAULT_JOB_CONTEXT
from astromosaic.geometry import PanelGeometry
from astromosaic.photometry.photo_match import LUMINANCE
from astromosaic.pipeline.photo_color import PhotoTileSource

_BLOCK = 64
_RADIUS = 13
_MARGIN = 1  # Keep the projected aperture apart from fit-sample interpolation support.
_MIN_STARS = 8
_MIN_BLOCKS = 3
_GAIN_TOLERANCE = log1p(0.01)
_MEDIAN_TOLERANCE = log1p(0.05)
_BLOCK_TOLERANCE = log1p(0.12)
_BASELINE_ALLOWANCE = log1p(0.02)

type Block = tuple[int, int]
type Pair = tuple[str, str]
type Coefficients = Mapping[str, Sequence[float]]


@dataclass(frozen=True)
class Aperture:
    xy: tuple[float, float]
    block: Block
    flux: float


class SplitMetrics(TypedDict, total=False):
    stars: int
    blocks: int
    status: str
    reason: str
    median_before: float
    median_after: float
    block_abs_log_error_p80: float


class EdgeMetrics(TypedDict):
    panels: list[str]
    relative_gain: float
    requires_support: bool
    selection: SplitMetrics
    test: SplitMetrics


def measure_apertures(
    source: PhotoTileSource,
    geometry: PanelGeometry,
    target: PanelGeometry,
    size: tuple[int, int],
    budget: int,
) -> list[Aperture]:
    """Use complete native, unsaturated apertures in the two reserved spatial folds."""
    descriptor = source.descriptor
    field = measure_stars(source, budget, DEFAULT_JOB_CONTEXT)
    xy = np.asarray([(s.x, s.y) for s in field.stars]).reshape(-1, 2)
    if not xy.size:
        return []
    output = target.inverse(geometry.forward(*xy.T))
    inside = np.isfinite(output).all(axis=1) & (output >= 0).all(axis=1)
    inside &= (output < size).all(axis=1)
    result = []
    for index in np.flatnonzero(inside):
        ox, oy = map(float, output[index])
        col, row = int(ox // _BLOCK), int(oy // _BLOCK)
        if (row + 2 * col) % 5 >= 2:
            continue
        x, y = map(float, xy[index])
        left, top = int(x) - _RADIUS, int(y) - _RADIUS
        side = 2 * (_RADIUS + 1)
        if min(left, top) < 0 or left + side > descriptor.width or top + side > descriptor.height:
            continue
        yy, xx = np.mgrid[top : top + side, left : left + side]
        distance = (xx - x) ** 2 + (yy - y) ** 2
        core = distance <= 7**2
        sky = (distance >= 10**2) & (distance <= _RADIUS**2)
        used = core | sky
        projected = target.inverse(geometry.forward(xx[used], yy[used]))
        lo = np.array([col, row]) * _BLOCK
        if not np.all((projected >= lo + _MARGIN) & (projected < lo + _BLOCK - _MARGIN)):
            continue
        tile = source.read_photometry_tile(Region(left, top, side, side))
        if not tile.valid[used].all():
            continue
        background = np.median(tile.pixels[sky], axis=0)
        flux_rgb = (tile.pixels[core] - background).sum(axis=0, dtype=np.float64)
        flux = float(flux_rgb @ LUMINANCE)
        residual = (tile.pixels[sky] - background) @ LUMINANCE
        sigma = 1.4826 * np.median(np.abs(residual - np.median(residual)))
        if np.all(flux_rgb > 0) and flux > 10 * sigma * sqrt(int(core.sum())):
            result.append(Aperture((ox, oy), (col, row), flux))
    return result


def _matched(
    left: Sequence[Aperture], right: Sequence[Aperture]
) -> list[tuple[Aperture, Aperture]]:
    if not left or not right:
        return []
    a = np.asarray([star.xy for star in left])
    b = np.asarray([star.xy for star in right])
    distance, nearest = cKDTree(b).query(a, k=2, distance_upper_bound=1.0)
    _, reverse = cKDTree(a).query(b, distance_upper_bound=1.0)
    possible = np.flatnonzero(
        np.isfinite(distance[:, 0]) & (distance[:, 0] <= 0.8 * distance[:, 1])
    )
    result = []
    for i in possible.tolist():
        j = int(nearest[i, 0])
        if reverse[j] == i and left[i].block == right[j].block:
            result.append((left[i], right[j]))
    return result


def _split_metrics(
    matches: Sequence[tuple[Aperture, Aperture]], fold: int, log_gain: float
) -> SplitMetrics:
    rows: dict[Block, list[float]] = {}
    for left, right in matches:
        col, row = left.block
        if (row + 2 * col) % 5 == fold:
            rows.setdefault(left.block, []).append(float(np.log(right.flux / left.flux)))
    count = sum(map(len, rows.values()))
    reason = "Insufficient matched stars or spatial blocks."
    metrics: SplitMetrics = {"stars": count, "blocks": len(rows), "status": "insufficient"}
    if rows:
        medians = np.array([np.median(ratios) for ratios in rows.values()])
        before = float(np.median(medians))
        after = before + log_gain
        block_error = float(np.percentile(np.abs(medians + log_gain), 80))
        metrics["median_before"] = expm1(before)
        metrics["median_after"] = expm1(after)
        metrics["block_abs_log_error_p80"] = block_error
        if count >= _MIN_STARS and len(rows) >= _MIN_BLOCKS:
            problems = []
            if abs(after) > _MEDIAN_TOLERANCE or block_error > _BLOCK_TOLERANCE:
                problems.append("Corrected stellar ratios differ from unity.")
            if abs(after) > abs(before) + _BASELINE_ALLOWANCE:
                problems.append("The gain worsens the stellar ratio relative to Off.")
            reason = " ".join(problems)
            metrics["status"] = "rejected" if problems else "supported"
    metrics["reason"] = reason
    return metrics


def qualify_gains(
    overlap_report: Mapping[str, object],
    apertures: Mapping[str, Sequence[Aperture]],
    *,
    additional: Mapping[str, Coefficients] | None = None,
) -> dict[str, object]:
    """Gate existing sky candidates on selection stars and report untouched test stars."""
    pairs = cast(Sequence[Pair], overlap_report["scored_edges"])
    models = dict(cast(Mapping[str, Coefficients], overlap_report["coefficients"]))
    if additional:
        for name, coefficients in additional.items():
            if (
                name in models
                or coefficients.keys() != apertures.keys()
                or any(
                    not values or not isfinite(values[0]) or values[0] <= 0
                    for values in coefficients.values()
                )
            ):
                raise ValueError("An external audit requires one positive finite gain per panel.")
        models.update(additional)
    matches = {tuple(pair): _matched(apertures[pair[0]], apertures[pair[1]]) for pair in pairs}
    candidates = {}
    eligible = set()
    for model, coefficients in models.items():
        edges: list[EdgeMetrics] = []
        for (left, right), stars in matches.items():
            log_gain = float(np.log(coefficients[right][0] / coefficients[left][0]))
            edges.append(
                {
                    "panels": [left, right],
                    "relative_gain": expm1(log_gain) + 1,
                    "requires_support": abs(log_gain) > _GAIN_TOLERANCE,
                    "selection": _split_metrics(stars, 1, log_gain),
                    "test": _split_metrics(stars, 0, log_gain),
                }
            )
        selection_passed = all(
            not edge["requires_support"] or edge["selection"]["status"] == "supported"
            for edge in edges
        )
        test_passed = all(
            not edge["requires_support"] or edge["test"]["status"] == "supported" for edge in edges
        )
        candidates[model] = dict(
            selection_passed=selection_passed, test_passed=test_passed, edges=edges
        )
        if selection_passed and (additional is None or model not in additional):
            eligible.add(model)
    return {"candidates": candidates, "eligible": sorted(eligible)}
