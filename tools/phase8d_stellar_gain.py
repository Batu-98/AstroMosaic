"""Measure independent stellar support for the offline photo overlap candidates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from math import expm1, isfinite
from typing import TypedDict, cast

import numpy as np

from astromosaic.astrometry.stars import measure_stars
from astromosaic.core import Region
from astromosaic.core.job import DEFAULT_JOB_CONTEXT
from astromosaic.geometry import PanelGeometry
from astromosaic.photometry.stellar_gain import (
    GAIN_TOLERANCE,
    Aperture,
    aperture_flux,
    aperture_masks,
    aperture_region,
    check_stellar_gain,
    matched_apertures,
)
from astromosaic.pipeline.photo_color import PhotoTileSource

_BLOCK = 64
_MARGIN = 1  # Keep the projected aperture apart from fit-sample interpolation support.

type Pair = tuple[str, str]
type Coefficients = Mapping[str, Sequence[float]]


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
        region = aperture_region(x, y)
        if not Region(0, 0, descriptor.width, descriptor.height).contains(region):
            continue
        yy, xx = np.mgrid[region.y : region.y + region.height, region.x : region.x + region.width]
        core, sky = aperture_masks(region, x, y)
        used = core | sky
        projected = target.inverse(geometry.forward(xx[used], yy[used]))
        lo = np.array([col, row]) * _BLOCK
        if not np.all((projected >= lo + _MARGIN) & (projected < lo + _BLOCK - _MARGIN)):
            continue
        flux = aperture_flux(source.read_photometry_tile(region), x, y)
        if flux is not None:
            result.append(Aperture((ox, oy), (col, row), flux))
    return result


def _split_metrics(
    matches: Sequence[tuple[Aperture, Aperture]], fold: int, log_gain: float
) -> SplitMetrics:
    selected = [pair for pair in matches if (pair[0].block[1] + 2 * pair[0].block[0]) % 5 == fold]
    measured = asdict(check_stellar_gain(selected, log_gain))
    return cast(SplitMetrics, {key: value for key, value in measured.items() if value is not None})


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
    matches = {
        tuple(pair): matched_apertures(apertures[pair[0]], apertures[pair[1]]) for pair in pairs
    }
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
                    "requires_support": abs(log_gain) > GAIN_TOLERANCE,
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
