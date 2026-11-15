"""Build a stellar overlap graph and fit anchored relative translations and gains."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Literal, cast

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from astromosaic.astrometry.stars import StarField
from astromosaic.core.job import JobContext
from astromosaic.geometry import PanelGeometry

FloatArray = NDArray[np.float64]
Bounds = tuple[float, float, float, float]
_MIN_MATCHES = 8
_MAX_P95 = 0.5


@dataclass(frozen=True, slots=True)
class ProjectedField:
    bounds: Bounds | None
    positions: FloatArray
    fluxes: FloatArray


def project_field(
    stars: StarField, geometry: PanelGeometry, target: PanelGeometry, width: int, height: int
) -> ProjectedField:
    # Sample each full-WCS edge to include curved and rotated footprints.
    x = np.linspace(-0.5, width - 0.5, 33)
    y = np.linspace(-0.5, height - 0.5, 33)
    boundary_x = np.concatenate((x, x, np.full_like(y, x[0]), np.full_like(y, x[-1])))
    boundary_y = np.concatenate((np.full_like(x, y[0]), np.full_like(x, y[-1]), y, y))
    boundary = target.inverse(geometry.forward(boundary_x, boundary_y))
    boundary = boundary[np.isfinite(boundary).all(axis=1)]
    bounds = None
    if boundary.size:
        lo, hi = boundary.min(axis=0), boundary.max(axis=0)
        bounds = float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])

    if not stars.stars:
        return ProjectedField(bounds, np.empty((0, 2)), np.empty(0))
    x, y, flux = np.array([(star.x, star.y, star.flux) for star in stars.stars], dtype=np.float64).T
    positions = target.inverse(geometry.forward(x, y))
    east_west = (
        geometry.forward(x + 0.5, y).cartesian.xyz.value
        - geometry.forward(x - 0.5, y).cartesian.xyz.value
    ).T
    north_south = (
        geometry.forward(x, y + 0.5).cartesian.xyz.value
        - geometry.forward(x, y - 0.5).cartesian.xyz.value
    ).T
    # Convert summed surface brightness into aperture flux using the local WCS Jacobian.
    flux *= np.linalg.norm(np.cross(east_west, north_south), axis=1)
    usable = np.isfinite(positions).all(axis=1) & np.isfinite(flux) & (flux > 0)
    return ProjectedField(bounds, positions[usable], flux[usable])


def overlap(left: Bounds | None, right: Bounds | None, margin: float = 0) -> Bounds | None:
    if left is None or right is None:
        return None
    lo_x, lo_y = max(left[0], right[0]) - margin, max(left[1], right[1]) - margin
    hi_x, hi_y = min(left[2], right[2]) + margin, min(left[3], right[3]) + margin
    return (lo_x, lo_y, hi_x, hi_y) if lo_x < hi_x and lo_y < hi_y else None


def components(count: int, pairs: Sequence[tuple[int, int]]) -> tuple[tuple[int, ...], ...]:
    adjacency: list[set[int]] = [set() for _ in range(count)]
    for left, right in pairs:
        adjacency[left].add(right)
        adjacency[right].add(left)
    remaining = set(range(count))
    groups = []
    while remaining:
        group: set[int] = set()
        pending = [min(remaining)]
        while pending:
            item = pending.pop()
            if item in remaining:
                remaining.remove(item)
                group.add(item)
                pending.extend(adjacency[item] & remaining)
        groups.append(tuple(sorted(group)))
    return tuple(groups)


@dataclass(frozen=True, slots=True)
class Residuals:
    count: int
    median_px: float
    rms_px: float
    p95_px: float


@dataclass(frozen=True, slots=True)
class EdgeReport:
    panels: tuple[int, int]
    matched: int
    training_inliers: int
    held_out: int


@dataclass(frozen=True, slots=True)
class Registration:
    status: Literal["ready", "weak", "disconnected"]
    components: tuple[tuple[int, ...], ...]
    edges: tuple[EdgeReport, ...]
    pairs: tuple[tuple[int, int], ...]
    shifts: FloatArray
    gains: FloatArray
    held_out: Residuals | None
    held_out_gain_error: float | None


@dataclass(frozen=True, slots=True)
class _Edge:
    panels: tuple[int, int]
    shift: FloatArray
    log_gain: float
    hold_shift: FloatArray
    hold_gain: FloatArray
    count: int


def _match_edge(
    left: ProjectedField,
    right: ProjectedField,
    pair: tuple[int, int],
    radius: float,
) -> tuple[EdgeReport, _Edge | None]:
    if not left.positions.size or not right.positions.size:
        return EdgeReport(pair, 0, 0, 0), None
    distances, neighbors = cKDTree(right.positions).query(
        left.positions, k=2, distance_upper_bound=radius
    )
    _, reverse = cKDTree(left.positions).query(right.positions, distance_upper_bound=radius)
    plausible = np.flatnonzero(
        np.isfinite(distances[:, 0]) & (distances[:, 0] <= 0.8 * distances[:, 1])
    )
    li = plausible[reverse[neighbors[plausible, 0]] == plausible]
    li = li[np.lexsort((left.positions[li, 1], left.positions[li, 0]))]
    ri = neighbors[li, 0]
    if li.size < _MIN_MATCHES:
        return EdgeReport(pair, int(li.size), 0, 0), None

    shift = left.positions[li] - right.positions[ri]
    log_gain = np.log(left.fluxes[li]) - np.log(right.fluxes[ri])
    hold = np.arange(li.size) % 4 == 0
    train_shift = shift[~hold]
    center = np.median(train_shift, axis=0)
    scatter = np.linalg.norm(train_shift - center, axis=1)
    typical = np.median(scatter)
    mad = np.median(np.abs(scatter - typical))
    inliers = scatter <= max(0.12, min(0.45, typical + 4 * 1.4826 * mad))
    count = int(np.count_nonzero(inliers))
    report = EdgeReport(pair, int(li.size), count, int(hold.sum()))
    if count < max(6, 0.65 * train_shift.shape[0]):
        return report, None
    return report, _Edge(
        pair,
        np.median(train_shift[inliers], axis=0),
        float(np.median(log_gain[~hold][inliers])),
        shift[hold],
        log_gain[hold],
        count,
    )


def robust_linear_fit(matrix: FloatArray, values: FloatArray, weights: FloatArray) -> FloatArray:
    """Solve a small linear response with Huber reweighting and fixed base weights."""
    effective = weights.copy()
    for _ in range(5):
        answer = np.linalg.lstsq(
            matrix * effective[:, None], values * effective[:, None], rcond=None
        )[0]
        error = np.linalg.norm(matrix @ answer - values, axis=1)
        cutoff = max(1e-10, 2.5 * float(np.median(error)))
        effective = weights * np.sqrt(cutoff / np.maximum(error, cutoff))
    return answer


def register(
    fields: Sequence[ProjectedField], max_shift: float, context: JobContext
) -> Registration:
    if not isfinite(max_shift) or max_shift <= 0:
        raise ValueError("Expected a positive finite registration search radius.")
    count = len(fields)
    if count < 2:
        raise ValueError("Relative refinement requires at least two panels.")
    potential, edges, reports = [], [], []
    for left, field in enumerate(fields):
        for right in range(left + 1, count):
            context.check_cancelled()
            if overlap(field.bounds, fields[right].bounds, max_shift) is None:
                continue
            potential.append((left, right))
            report, edge = _match_edge(field, fields[right], (left, right), max_shift)
            reports.append(report)
            if edge is not None:
                edges.append(edge)

    pairs = tuple(edge.panels for edge in edges)
    groups = components(count, pairs)
    shifts, gains = np.zeros((count, 2)), np.ones(count)
    if len(groups) > 1:
        state: Literal["disconnected", "weak"] = (
            "disconnected" if len(components(count, potential)) > 1 else "weak"
        )
        return Registration(state, groups, tuple(reports), pairs, shifts, gains, None, None)

    # The first panel is the spatial and photometric reference. Fit all overlap equations jointly.
    matrix = np.zeros((len(edges), count))
    for row, edge in enumerate(edges):
        left, right = edge.panels
        matrix[row, left], matrix[row, right] = -1, 1
    design = matrix[:, 1:]
    weights = np.sqrt(np.array([edge.count for edge in edges], dtype=np.float64))
    shifts[1:] = robust_linear_fit(design, np.stack([edge.shift for edge in edges]), weights)
    logs = np.zeros(count)
    logs[1:] = robust_linear_fit(
        design, np.array([[edge.log_gain] for edge in edges]), weights
    ).ravel()
    with np.errstate(over="ignore", under="ignore"):
        np.exp(logs, out=gains)

    held_out = np.concatenate(
        [
            np.linalg.norm(shifts[right] - shifts[left] - edge.hold_shift, axis=1)
            for edge in edges
            for left, right in (edge.panels,)
        ]
    )
    relative = np.concatenate(
        [
            np.abs(np.expm1(np.clip(logs[right] - logs[left] - edge.hold_gain, -50, 50)))
            for edge in edges
            for left, right in (edge.panels,)
        ]
    )
    metrics = Residuals(
        int(held_out.size),
        float(np.median(held_out)),
        float(np.sqrt(np.mean(held_out**2))),
        float(np.percentile(held_out, 95)),
    )
    gain_error = float(np.median(relative))
    edge_p95 = max(
        float(
            np.percentile(
                np.linalg.norm(shifts[right] - shifts[left] - edge.hold_shift, axis=1), 95
            )
        )
        for edge in edges
        for left, right in (edge.panels,)
    )
    ready = (
        edge_p95 < _MAX_P95 and gain_error < 0.10 and np.isfinite(gains).all() and np.all(gains > 0)
    )
    return Registration(
        "ready" if ready else "weak",
        groups,
        tuple(reports),
        pairs,
        cast(FloatArray, shifts),
        cast(FloatArray, gains),
        metrics,
        gain_error,
    )
