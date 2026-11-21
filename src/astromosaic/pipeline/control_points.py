"""Fit terrain control points on a graph anchored to a source panel."""

from collections import defaultdict, deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import combinations
from math import atan2, ceil, degrees, floor, isfinite
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from astromosaic.astrometry.registration import components
from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.io import PanelSource

type XY = tuple[float, float]
type Pair = tuple[int, int]
type Model = Literal["translation", "similarity"]
type ModelChoice = Literal["auto", "translation", "similarity"]
type ComplexArray = NDArray[np.complex128]
type FloatArray = NDArray[np.float64]
type InlierSupport = Callable[[Pair, ComplexArray, ComplexArray], bool]

_ERROR_LIMIT = 2.0
_MIN_POINTS = 3
_MIN_SPREAD = 8.0
_MIN_SCALE = 0.5
_MAX_SCALE = 2.0
_MAX_SEEDS = 16


@dataclass(frozen=True, slots=True)
class GroundControlPoint:
    id: str
    panels: Pair
    left_xy: XY
    right_xy: XY
    held_out: bool = False


@dataclass(frozen=True, slots=True)
class ControlPointDiagnostic:
    id: str
    panels: Pair
    held_out: bool
    status: str
    forward_error_px: float | None = None
    reverse_error_px: float | None = None
    residual_basis: Literal["pair", "anchored"] | None = None


@dataclass(frozen=True, slots=True)
class ControlEdgeDiagnostic:
    panels: Pair
    status: str
    training_points: int
    inliers: int
    held_out: int
    training_p95_px: float | None = None
    held_out_p95_px: float | None = None


@dataclass(frozen=True, slots=True)
class ControlPose:
    panel: int
    shift: XY
    scale: float
    rotation_deg: float


@dataclass(frozen=True, slots=True)
class ControlPointFit:
    model: Model
    status: Literal[
        "accepted",
        "disconnected",
        "ill-conditioned",
        "unsupported-scale",
        "graph-disagreement",
        "audit-unavailable",
    ]
    anchor: int
    groups: tuple[tuple[int, ...], ...]
    poses: tuple[ControlPose, ...]
    edges: tuple[ControlEdgeDiagnostic, ...]
    points: tuple[ControlPointDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class _Transform:
    multiplier: complex = 1 + 0j
    offset: complex = 0j

    def then(self, outer: "_Transform") -> "_Transform":
        return _Transform(
            outer.multiplier * self.multiplier, outer.multiplier * self.offset + outer.offset
        )

    def inverse(self) -> "_Transform":
        return _Transform(1 / self.multiplier, -self.offset / self.multiplier)

    def apply(self, position: ComplexArray) -> ComplexArray:
        return self.multiplier * position + self.offset

    def pose(self, panel: int) -> ControlPose:
        return ControlPose(
            panel,
            (float(self.offset.real), float(self.offset.imag)),
            float(abs(self.multiplier)),
            degrees(atan2(self.multiplier.imag, self.multiplier.real)),
        )


@dataclass(frozen=True, slots=True)
class _Edge:
    pair: Pair
    indices: tuple[int, ...]
    left: ComplexArray
    right: ComplexArray
    training: NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class _PairFit:
    edge: _Edge
    transform: _Transform
    inliers: NDArray[np.bool_]


def _sample_status(source: PanelSource, xy: XY) -> str:
    x, y = xy
    size = source.descriptor
    if not (isfinite(x) and isfinite(y)):
        return "nonfinite-position"
    if not (0 <= x <= size.width - 1 and 0 <= y <= size.height - 1):
        return "outside-source"
    region = Region(floor(x), floor(y), ceil(x) - floor(x) + 1, ceil(y) - floor(y) + 1)
    return "usable" if source.read_tile(region).valid.all() else "outside-valid-ground"


def _prepare(
    sources: Mapping[int, PanelSource], points: Sequence[GroundControlPoint], context: JobContext
) -> tuple[tuple[_Edge, ...], list[ControlPointDiagnostic]]:
    if any(not point.id.strip() for point in points) or len({p.id for p in points}) != len(points):
        raise ValueError("Control point IDs must be nonempty and unique.")

    diagnostics = []
    entries: dict[Pair, list[tuple[int, complex, complex]]] = defaultdict(list)
    seen: dict[Pair, set[tuple[complex, complex]]] = defaultdict(set)
    samples: dict[tuple[int, XY], str] = {}
    for index, point in enumerate(points):
        context.check_cancelled()
        a, b = point.panels
        if a == b:
            status = "same-panel"
        elif a not in sources or b not in sources:
            status = "panel-without-active-ground"
        else:
            status = "usable"
            for panel, xy in zip(point.panels, (point.left_xy, point.right_xy), strict=True):
                if (panel, xy) not in samples:
                    samples[panel, xy] = _sample_status(sources[panel], xy)
                status = samples[panel, xy]
                if status != "usable":
                    break
            if status == "usable":
                left, right = complex(*point.left_xy), complex(*point.right_xy)
                pair, coordinates = ((a, b), (left, right)) if a < b else ((b, a), (right, left))
                if coordinates in seen[pair]:
                    status = "duplicate-correspondence"
                else:
                    seen[pair].add(coordinates)
                    entries[pair].append((index, *coordinates))
        diagnostics.append(ControlPointDiagnostic(point.id, point.panels, point.held_out, status))
        if context.on_progress is not None:
            context.on_progress(index + 1, len(points) + 1)

    edges = []
    for pair, rows in sorted(entries.items()):
        indices, left_xy, right_xy = zip(*rows, strict=True)
        edges.append(
            _Edge(
                pair,
                indices,
                np.asarray(left_xy, dtype=np.complex128),
                np.asarray(right_xy, dtype=np.complex128),
                np.asarray([not points[index].held_out for index in indices], dtype=np.bool_),
            )
        )
    return tuple(edges), diagnostics


def _scale_supported(transform: _Transform) -> bool:
    return _MIN_SCALE <= abs(transform.multiplier) <= _MAX_SCALE


def _spread(values: ComplexArray) -> float:
    centered = values - values.mean()
    xy = np.column_stack((centered.real, centered.imag))
    # The RMS extent in the least-covered direction catches collinear support.
    return float(np.linalg.svd(xy, compute_uv=False)[-1] / np.sqrt(values.size))


def _p95(errors: FloatArray) -> float | None:
    return float(np.percentile(errors, 95)) if errors.size else None


def _pair_transform(model: Model, left: ComplexArray, right: ComplexArray) -> _Transform:
    if model == "translation":
        shifts = left - right
        return _Transform(offset=complex(np.median(shifts.real), np.median(shifts.imag)))
    centered = right - right.mean()
    multiplier = complex(np.vdot(centered, left - left.mean()) / np.vdot(centered, centered))
    return _Transform(multiplier, complex(left.mean() - multiplier * right.mean()))


def _pair_errors(transform: _Transform, left: ComplexArray, right: ComplexArray) -> FloatArray:
    return np.abs(transform.apply(right) - left) / min(1.0, abs(transform.multiplier))


def _similarity_seed(
    left: ComplexArray,
    right: ComplexArray,
    context: JobContext,
    *,
    error_limit: float = _ERROR_LIMIT,
    seed_limit: int = _MAX_SEEDS,
) -> _Transform | None:
    # Bound the deterministic two-point search. Sort by position so JSON order
    # does not control coverage of the seed set.
    order = np.lexsort((right.imag, right.real))
    seeds = order[np.linspace(0, right.size - 1, min(seed_limit, right.size), dtype=int)]
    best = None
    score = (0, -np.inf)
    for a, b in combinations(seeds, 2):
        context.check_cancelled()
        difference = right[b] - right[a]
        if abs(difference) < _MIN_SPREAD:
            continue
        multiplier = complex((left[b] - left[a]) / difference)
        offset = complex(left[a] - multiplier * right[a])
        trial = _Transform(multiplier, offset)
        if _scale_supported(trial):
            errors = _pair_errors(trial, left, right)
            good = errors <= error_limit
            if good.any():
                candidate_score = (int(good.sum()), -float(np.median(errors[good])))
                if candidate_score > score:
                    best, score = trial, candidate_score
    return best


def _annotate(
    edge: _Edge,
    diagnostics: list[ControlPointDiagnostic],
    forward: FloatArray,
    reverse: FloatArray,
    basis: Literal["pair", "anchored"],
    inliers: NDArray[np.bool_],
) -> None:
    for row, index in enumerate(edge.indices):
        initial = diagnostics[index]
        f, r = float(forward[row]), float(reverse[row])
        if initial.panels != edge.pair:
            f, r = r, f
        if initial.held_out:
            status = "held-out" if max(f, r) <= _ERROR_LIMIT else "held-out-error"
        else:
            status = "inlier" if inliers[row] and max(f, r) <= _ERROR_LIMIT else "outlier"
        diagnostics[index] = replace(
            initial, status=status, forward_error_px=f, reverse_error_px=r, residual_basis=basis
        )


def _fit_pair(
    edge: _Edge,
    model: Model,
    points: list[ControlPointDiagnostic],
    context: JobContext,
    inlier_support: InlierSupport | None,
) -> tuple[_PairFit | None, ControlEdgeDiagnostic]:
    left, right = edge.left[edge.training], edge.right[edge.training]
    count = left.size
    report = ControlEdgeDiagnostic(
        edge.pair, "insufficient-points", count, 0, int((~edge.training).sum())
    )
    if count < _MIN_POINTS:
        return None, report
    if min(np.unique(left).size, np.unique(right).size) < _MIN_POINTS:
        return None, replace(report, status="insufficient-distinct-points")

    if model == "similarity":
        if min(_spread(left), _spread(right)) < _MIN_SPREAD:
            return None, replace(report, status="insufficient-point-spread")
        transform = _similarity_seed(left, right, context)
        if transform is None:
            return None, replace(report, status="unsupported-scale-or-geometry")
    else:
        transform = _pair_transform(model, left, right)

    minimum_inliers = max(_MIN_POINTS, ceil(0.75 * count))
    good = _pair_errors(transform, left, right) <= _ERROR_LIMIT
    if good.sum() >= minimum_inliers and (
        model == "translation" or min(_spread(left[good]), _spread(right[good])) >= _MIN_SPREAD
    ):
        transform = _pair_transform(model, left[good], right[good])
    if not _scale_supported(transform):
        return None, replace(report, status="unsupported-scale-or-geometry")

    reverse = np.abs(transform.apply(edge.right) - edge.left)
    forward = reverse / abs(transform.multiplier)
    errors = np.maximum(forward, reverse)
    inliers = edge.training.copy()
    inliers[edge.training] = good
    inliers &= errors <= _ERROR_LIMIT
    _annotate(edge, points, forward, reverse, "pair", inliers)
    fitted = _p95(errors[inliers])
    held = _p95(errors[~edge.training])
    status = "accepted"
    if inliers.sum() < minimum_inliers:
        status = "conflicting-points"
    elif (
        model == "similarity"
        and min(_spread(edge.left[inliers]), _spread(edge.right[inliers])) < _MIN_SPREAD
    ):
        status = "insufficient-point-spread"
    elif inlier_support is not None and not inlier_support(
        edge.pair, edge.left[inliers], edge.right[inliers]
    ):
        status = "localized-inliers"
    elif held is not None and held > _ERROR_LIMIT:
        status = "held-out-error"
    report = replace(
        report,
        status=status,
        inliers=int(inliers.sum()),
        training_p95_px=fitted,
        held_out_p95_px=held,
    )
    return (_PairFit(edge, transform, inliers) if status == "accepted" else None), report


def _initialize(anchor: int, pairs: Sequence[_PairFit]) -> dict[int, _Transform]:
    adjacent: dict[int, list[tuple[int, _Transform]]] = defaultdict(list)
    for pair in pairs:
        left, right = pair.edge.pair
        adjacent[left].append((right, pair.transform))
        adjacent[right].append((left, pair.transform.inverse()))

    poses = {anchor: _Transform()}
    pending = deque([anchor])
    while pending:
        panel = pending.popleft()
        for neighbor, neighbor_to_panel in adjacent[panel]:
            if neighbor not in poses:
                poses[neighbor] = neighbor_to_panel.then(poses[panel])
                pending.append(neighbor)
    return poses


def _refine(
    model: Model,
    pairs: Sequence[_PairFit],
    poses: dict[int, _Transform],
    anchor: int,
    context: JobContext,
) -> dict[int, _Transform] | None:
    variable = {panel: i for i, panel in enumerate(sorted(poses.keys() - {anchor}))}
    # Fit corrections in the anchor's grid. Center and normalize the rotation/
    # scale coefficients to keep the linear system well scaled.
    samples = [
        (
            fit.edge.pair,
            poses[fit.edge.pair[0]].apply(fit.edge.left[fit.inliers]),
            poses[fit.edge.pair[1]].apply(fit.edge.right[fit.inliers]),
        )
        for fit in pairs
    ]
    locations = np.concatenate([left for _, left, _ in samples])
    center = complex(locations.mean())
    extent = max(1.0, float(np.max(np.abs(locations - center))))
    count = locations.size
    translation = model == "translation"
    parameters = 1 if translation else 2
    matrix = np.zeros((count, parameters * len(variable)), dtype=np.complex128)
    target = np.empty(count, dtype=np.complex128)
    source_scale = np.empty(count, dtype=np.float64)
    start = 0
    for (a, b), left, right in samples:
        rows = slice(start, start + left.size)
        start += left.size
        source_scale[rows] = min(abs(poses[a].multiplier), abs(poses[b].multiplier))
        target[rows] = right - left
        for panel, sign, positions in ((a, 1, left), (b, -1, right)):
            if panel != anchor:
                col = variable[panel] * parameters
                matrix[rows, col] = sign
                if not translation:
                    matrix[rows, col + 1] = sign * (positions - center) / extent

    base = 1 / source_scale
    weights = base
    for _ in range(5):
        context.check_cancelled()
        solution, _, rank, singular = np.linalg.lstsq(
            matrix * weights[:, None], target * weights, rcond=None
        )
        if rank < matrix.shape[1] or singular[-1] < singular[0] * 1e-10:
            return None
        # Apply Huber weights to the radial errors in the original source scale.
        errors = np.abs(matrix @ solution - target) * base
        weights = base * np.sqrt(_ERROR_LIMIT / np.maximum(errors, _ERROR_LIMIT))

    updated = {anchor: poses[anchor]}
    for panel, index in variable.items():
        col = index * parameters
        delta = 0j if translation else complex(solution[col + 1] / extent)
        correction = _Transform(1 + delta, complex(solution[col]) - delta * center)
        updated[panel] = poses[panel].then(correction)
    return updated


def _fit(
    model: Model,
    panels: tuple[int, ...],
    anchor: int,
    edges: tuple[_Edge, ...],
    points: list[ControlPointDiagnostic],
    context: JobContext,
    inlier_support: InlierSupport | None,
) -> ControlPointFit:
    diagnostics = points.copy()
    index = {panel: i for i, panel in enumerate(panels)}
    fits: list[_PairFit] = []
    reports = []
    for edge in edges:
        context.check_cancelled()
        fit, report = _fit_pair(edge, model, diagnostics, context, inlier_support)
        reports.append(report)
        if fit is not None:
            fits.append(fit)
        else:
            for i in edge.indices:
                if diagnostics[i].status == "usable":
                    diagnostics[i] = replace(diagnostics[i], status=report.status)
    groups = tuple(
        tuple(panels[i] for i in group)
        for group in components(
            len(panels), [(index[f.edge.pair[0]], index[f.edge.pair[1]]) for f in fits]
        )
    )
    result = ControlPointFit(
        model, "disconnected", anchor, groups, (), tuple(reports), tuple(diagnostics)
    )
    if len(groups) != 1:
        return result

    initial = _initialize(anchor, fits)
    if not all(_scale_supported(pose) for pose in initial.values()):
        return replace(result, status="unsupported-scale")
    poses = _refine(model, fits, initial, anchor, context)
    if poses is None:
        return replace(result, status="ill-conditioned")
    if not all(_scale_supported(pose) for pose in poses.values()):
        return replace(result, status="unsupported-scale")
    reliable = {fit.edge.pair: fit for fit in fits}
    for i, report in enumerate(reports):
        context.check_cancelled()
        accepted = reliable.get(report.panels)
        if accepted is None:
            continue
        edge = accepted.edge
        left, right = (poses[panel] for panel in edge.pair)
        distance = np.abs(left.apply(edge.left) - right.apply(edge.right))
        forward, reverse = distance / abs(right.multiplier), distance / abs(left.multiplier)
        errors = np.maximum(forward, reverse)
        retained = accepted.inliers & (errors <= _ERROR_LIMIT)
        training_error = _p95(errors[accepted.inliers])
        holdout_error = _p95(errors[~edge.training])
        _annotate(edge, diagnostics, forward, reverse, "anchored", retained)
        assert training_error is not None
        count = int(retained.sum())
        supported = count >= max(_MIN_POINTS, ceil(0.75 * report.training_points))
        if supported and model == "similarity":
            supported = (
                min(_spread(edge.left[retained]), _spread(edge.right[retained])) >= _MIN_SPREAD
            )
        if supported and inlier_support is not None:
            supported = inlier_support(edge.pair, edge.left[retained], edge.right[retained])
        if (
            not supported
            or training_error > _ERROR_LIMIT
            or (holdout_error is not None and holdout_error > _ERROR_LIMIT)
        ):
            report = replace(report, status="graph-disagreement")
        reports[i] = replace(
            report,
            inliers=count,
            training_p95_px=training_error,
            held_out_p95_px=holdout_error,
        )

    result = replace(result, edges=tuple(reports), points=tuple(diagnostics))
    if any(report.status == "graph-disagreement" for report in reports):
        return replace(result, status="graph-disagreement")
    return replace(result, status="accepted", poses=tuple(poses[p].pose(p) for p in panels))


def control_point_fit_bytes(point_count: int, panel_count: int) -> int:
    # A dense complex system, its copies and the least-squares work arrays
    # dominate allocation. Leave additional space for validation and diagnostics.
    return point_count * (160 * (panel_count - 1) + 1024)


def fit_ground_control_points(
    sources: Mapping[int, PanelSource],
    points: Sequence[GroundControlPoint],
    budget: int,
    context: JobContext,
    *,
    model: ModelChoice = "auto",
    anchor: int | None = None,
    inlier_support: InlierSupport | None = None,
) -> ControlPointFit:
    """Fit source-pixel correspondences on foreground-selected panel readers."""
    context.check_cancelled()
    if model not in ("auto", "translation", "similarity"):
        raise ValueError("Unknown ground control point model.")
    panels = tuple(sorted(sources))
    if len(panels) < 2:
        raise ValueError("Apply active foreground masks to at least two panels.")
    if not points:
        raise ValueError("Supply ground control points.")
    reference = panels[0] if anchor is None else anchor
    if reference not in sources:
        raise ValueError("The anchor panel must have an active foreground mask.")
    if control_point_fit_bytes(len(points), len(panels)) > budget:
        raise ValueError("The working budget cannot fit the control point graph.")
    edges, diagnostics = _prepare(sources, points, context)
    if model == "similarity":
        result = _fit("similarity", panels, reference, edges, diagnostics, context, inlier_support)
    else:
        result = _fit("translation", panels, reference, edges, diagnostics, context, inlier_support)
        if model == "auto" and result.status != "accepted":
            result = _fit(
                "similarity", panels, reference, edges, diagnostics, context, inlier_support
            )
    if context.on_progress is not None:
        context.on_progress(len(points) + 1, len(points) + 1)
    context.check_cancelled()
    return result
