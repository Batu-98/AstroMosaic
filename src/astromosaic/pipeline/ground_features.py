"""Discover bounded terrain correspondences and submit them to the shared fit."""

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from importlib import import_module
from itertools import combinations
from math import ceil
from threading import Lock
from types import ModuleType

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import distance_transform_cdt
from scipy.spatial.distance import cdist

from astromosaic.core.job import JobContext
from astromosaic.core.masks import bounded_grid
from astromosaic.io import PanelSource
from astromosaic.pipeline.control_points import (
    ComplexArray,
    ControlPointFit,
    FloatArray,
    GroundControlPoint,
    Model,
    ModelChoice,
    Pair,
    _pair_errors,
    _pair_transform,
    _scale_supported,
    _similarity_seed,
    _spread,
    control_point_fit_bytes,
    fit_ground_control_points,
)
from astromosaic.pipeline.ground_patches import refine_ground_match
from astromosaic.pipeline.masking import MATCHING_EDGE, read_thumbnail

_MAX_PANELS = 16
_MAX_FEATURES = 512
_MAX_PER_CELL = 12
_MAX_PATCH_TRIALS = 64
_MAX_POINTS = 32
_MAX_HOLDOUTS = 512
_MIN_MATCHES = 8
_AUDIT_RADIUS = 24.0
_MIB = 1024**2
_PAIR_WORK_BYTES = 8 * _MIB
_FEATURE_LOCK = Lock()


@dataclass(frozen=True, slots=True)
class FeaturePanelDiagnostic:
    panel: int
    thumbnail_size: tuple[int, int]
    supported_cells: int
    detected: int
    outside_footprint: int
    near_audit: int
    features: int
    status: str


@dataclass(frozen=True, slots=True)
class FeaturePairDiagnostic:
    panels: Pair
    status: str
    mutual_matches: int = 0
    coarse_inliers: int = 0
    patch_trials: int = 0
    patch_matches: int = 0
    submitted: int = 0
    coarse_p95_px: float | None = None


@dataclass(frozen=True, slots=True)
class GroundFeatureFit:
    backend_version: str
    reserved_peak_bytes: int
    panels: tuple[FeaturePanelDiagnostic, ...]
    pairs: tuple[FeaturePairDiagnostic, ...]
    points: tuple[GroundControlPoint, ...]
    fit: ControlPointFit


@dataclass(frozen=True, slots=True)
class _Features:
    xy: ComplexArray
    descriptors: NDArray[np.float32]
    pixel_step: float


def _backend() -> ModuleType:
    try:
        backend = import_module("cv2")
        if not hasattr(backend, "SIFT_create"):
            raise ImportError("The installed cv2 module does not provide SIFT.")
    except (ImportError, OSError) as error:
        raise ValueError(
            "Automatic terrain matching requires the optional OpenCV SIFT backend. "
            "Use --points for manual recovery. See the Phase 7C setup."
        ) from error
    return backend


def _feature_view(source: PanelSource, available: int) -> tuple[int, tuple[int, int], int]:
    panel_size = source.descriptor.width, source.descriptor.height
    for edge in range(MATCHING_EDGE, 255, -16):
        width, height = bounded_grid(panel_size, edge)
        # One SIFT worker. Include the doubled Gaussian and DoG pyramids,
        # temporary native buffers, spatial grids and capped descriptors.
        reserve = 272 * width * height + 8 * _MIB
        if reserve <= available:
            return edge, (width, height), reserve
    raise ValueError("The working budget cannot fit the smallest terrain matching view.")


def _source_coordinate(value: FloatArray, source_span: int, view_span: int) -> FloatArray:
    # Each sample is the mean of [edge[i], edge[i+1]) in the source raster.
    edges = np.arange(view_span + 1, dtype=np.int64) * source_span // view_span
    return np.interp(value, np.arange(view_span), (edges[:-1] + edges[1:] - 1) / 2)


def _features(
    cv: ModuleType,
    source: PanelSource,
    panel: int,
    context: JobContext,
    available: int,
    exclusions: Sequence[complex],
) -> tuple[_Features, FeaturePanelDiagnostic, int]:
    edge, (width, height), reserve = _feature_view(source, available)
    thumb = read_thumbnail(source, edge, reserve, context, complete_support=True)
    support = int(thumb.valid.sum())
    size = source.descriptor.width, source.descriptor.height
    step = max(size[0] / width, size[1] / height)
    empty = _Features(np.empty(0, dtype=np.complex128), np.empty((0, 128), np.float32), step)
    report = FeaturePanelDiagnostic(panel, (width, height), support, 0, 0, 0, 0, "support")
    if support < 64:
        return empty, report, reserve
    samples = thumb.pixels[thumb.valid].astype(np.float64)
    low, high = np.percentile(samples, (2, 98))
    if high <= low:
        return empty, replace(report, status="texture"), reserve
    view = np.zeros((height, width), dtype=np.uint8)
    view[thumb.valid] = np.rint(np.clip((samples - low) * 255 / (high - low), 0, 255))
    footprint = distance_transform_cdt(np.pad(thumb.valid, 1), metric="chessboard")[1:-1, 1:-1]

    context.check_cancelled()
    # OpenCV's thread setting is process-wide. Serialize the optional backend
    # and restore the caller's setting before doing source I/O or pair work.
    with _FEATURE_LOCK:
        threads = cv.getNumThreads()
        cv.setNumThreads(1)
        try:
            sift = cv.SIFT_create(
                nfeatures=2048, contrastThreshold=0.018, enable_precise_upscale=True
            )
            found = sift.detect(view, thumb.valid.astype(np.uint8))
            context.check_cancelled()
            xs, ys = (
                np.asarray(values, dtype=np.float64)
                for values in ([key.pt[0] for key in found], [key.pt[1] for key in found])
            )
            source_xy = _source_coordinate(xs, size[0], width) + 1j * _source_coordinate(
                ys, size[1], height
            )
            chosen: list[int] = []
            cells: Counter[tuple[int, int]] = Counter()
            used = np.zeros((height, width), dtype=np.bool_)
            outside = near_audit = 0
            for i in sorted(
                range(len(found)),
                key=lambda i: (-found[i].response, ys[i], xs[i], found[i].size, found[i].angle),
            ):
                key = found[i]
                x, y = int(xs[i] + 0.5), int(ys[i] + 0.5)
                if (
                    x >= width
                    or y >= height
                    or key.size > 24
                    # Include the rotated descriptor, gradients and scale-space blur.
                    or footprint[y, x] <= ceil(10 * key.size) + 4
                ):
                    outside += 1
                    continue
                if any(abs(source_xy[i] - point) <= _AUDIT_RADIUS for point in exclusions):
                    near_audit += 1
                    continue
                cell = x // 64, y // 64
                if used[y, x] or cells[cell] >= _MAX_PER_CELL or len(chosen) == _MAX_FEATURES:
                    continue
                used[max(y - 2, 0) : y + 3, max(x - 2, 0) : x + 3] = True
                cells[cell] += 1
                chosen.append(i)
            if chosen:
                keys, descriptors = sift.compute(view, [found[i] for i in chosen])
                if len(keys) != len(chosen) or descriptors.shape != (len(chosen), 128):
                    raise ValueError("The SIFT backend returned an unexpected descriptor shape.")
        except cv.error as error:
            raise ValueError(f"Terrain feature extraction failed: {error}") from error
        finally:
            cv.setNumThreads(threads)
    context.check_cancelled()
    status = "ready" if len(chosen) >= _MIN_MATCHES else "insufficient-features"
    report = replace(
        report,
        detected=len(found),
        outside_footprint=outside,
        near_audit=near_audit,
        features=len(chosen),
        status=status,
    )
    if not chosen:
        return empty, report, reserve
    return _Features(source_xy[chosen], np.asarray(descriptors, np.float32), step), report, reserve


def _nearest(distances: FloatArray) -> tuple[NDArray[np.intp], FloatArray]:
    rows = np.arange(len(distances))
    nearest = distances.argmin(axis=1)
    d1 = distances[rows, nearest]
    distances[rows, nearest] = np.inf
    d2 = distances.min(axis=1)
    distances[rows, nearest] = d1
    ratio = np.full(len(distances), np.inf)
    np.divide(d1, d2, out=ratio, where=d2 > 0)
    return nearest, ratio


def _match(left: _Features, right: _Features) -> tuple[ComplexArray, ComplexArray]:
    distances = cdist(left.descriptors, right.descriptors, metric="sqeuclidean")
    to_right, ratio_r = _nearest(distances)
    to_left, ratio_l = _nearest(distances.T)
    a = np.arange(left.xy.size)
    both = np.maximum(ratio_r, ratio_l[to_right])
    mutual = a[(to_left[to_right] == a) & (both < 0.78**2)]
    ranked = mutual[np.argsort(both[mutual], kind="stable")]
    return left.xy[ranked], right.xy[to_right[ranked]]


def _distributed(a: ComplexArray, b: ComplexArray, steps: tuple[float, float]) -> bool:
    for xy, step in zip((a, b), steps, strict=True):
        if len(xy) < _MIN_MATCHES or _spread(xy) < max(8.0, 6 * step):
            return False
        cells = np.column_stack((xy.real, xy.imag)) // (48 * step)
        if len(np.unique(cells, axis=0)) < 4:
            return False
    return True


def _pair_points(
    pair: Pair,
    sources: Mapping[int, PanelSource],
    features: Mapping[int, _Features],
    model: ModelChoice,
    budget: int,
    context: JobContext,
    right_audit: Sequence[complex],
) -> tuple[FeaturePairDiagnostic, tuple[GroundControlPoint, ...]]:
    a, b = pair
    left, right = features[a], features[b]
    report = FeaturePairDiagnostic(pair, "insufficient-features")
    if min(len(left.xy), len(right.xy)) < _MIN_MATCHES:
        return report, ()
    xy_a, xy_b = _match(left, right)
    count = len(xy_a)
    report = replace(report, status="ambiguous-descriptors", mutual_matches=count)
    if count < _MIN_MATCHES:
        return report, ()

    steps = left.pixel_step, right.pixel_step
    limit = max(2.5, 1.5 * max(steps))
    geometry: Model = "translation" if model == "translation" else "similarity"
    seed = (
        _pair_transform("translation", xy_a, xy_b)
        if geometry == "translation"
        else _similarity_seed(xy_a, xy_b, context, error_limit=limit, seed_limit=32)
    )
    report = replace(report, status="no-coherent-model")
    if seed is None:
        return report, ()
    good = _pair_errors(seed, xy_a, xy_b) <= limit
    count_good = int(good.sum())
    report = replace(report, coarse_inliers=count_good)
    if count_good < max(_MIN_MATCHES, ceil(0.60 * count)):
        return report, ()
    if not _distributed(xy_a[good], xy_b[good], steps):
        return replace(report, status="localized-model"), ()
    transform = _pair_transform(geometry, xy_a[good], xy_b[good])
    if not _scale_supported(transform):
        return report, ()
    errors = _pair_errors(transform, xy_a, xy_b)
    report = replace(report, coarse_p95_px=float(np.percentile(errors[good], 95)))
    good &= errors <= limit
    if int(good.sum()) < max(_MIN_MATCHES, ceil(0.60 * count)):
        return report, ()

    trials = 0
    refined_a, refined_b = [], []
    cells: Counter[tuple[int, int]] = Counter()
    for i in np.flatnonzero(good):
        context.check_cancelled()
        p, q = xy_a[i], xy_b[i]
        cell = int(p.real // (48 * steps[0])), int(p.imag // (48 * steps[0]))
        if cells[cell] >= 4:
            continue
        trials += 1
        refined = refine_ground_match(sources[a], sources[b], p, q, transform, budget)
        if refined is not None and all(
            abs(refined - point) > _AUDIT_RADIUS for point in right_audit
        ):
            cells[cell] += 1
            refined_a.append(p)
            refined_b.append(refined)
        if trials == _MAX_PATCH_TRIALS or len(refined_a) == _MAX_POINTS:
            break
    report = replace(
        report, status="unverified-patches", patch_trials=trials, patch_matches=len(refined_a)
    )
    if not _distributed(np.asarray(refined_a), np.asarray(refined_b), steps):
        return report, ()
    points = tuple(
        GroundControlPoint(
            f"auto:{a + 1}-{b + 1}:{i}",
            pair,
            (float(p.real), float(p.imag)),
            (float(q.real), float(q.imag)),
        )
        for i, (p, q) in enumerate(zip(refined_a, refined_b, strict=True), 1)
    )
    return replace(report, status="submitted", submitted=len(points)), points


def fit_ground_features(
    sources: Mapping[int, PanelSource],
    budget: int,
    context: JobContext,
    *,
    model: ModelChoice = "auto",
    anchor: int | None = None,
    holdouts: Sequence[GroundControlPoint] = (),
) -> GroundFeatureFit:
    """Try every active pair within explicit limits, leaving weak links for manual recovery."""
    context.check_cancelled()
    panels = tuple(sorted(sources))
    if not 2 <= len(panels) <= _MAX_PANELS:
        raise ValueError(f"Apply active foreground masks to 2–{_MAX_PANELS} panels.")
    reference = panels[0] if anchor is None else anchor
    if reference not in sources:
        raise ValueError("The anchor panel must have an active foreground mask.")
    if model not in ("auto", "translation", "similarity"):
        raise ValueError("Unknown ground control point model.")
    holdouts = tuple(point for point in holdouts if point.enabled)
    if len(holdouts) > _MAX_HOLDOUTS:
        raise ValueError(f"Supply at most {_MAX_HOLDOUTS} independent audit points.")
    exclusions: dict[int, list[complex]] = defaultdict(list)
    for point in holdouts:
        context.check_cancelled()
        if not point.held_out or point.id.startswith("auto:"):
            raise ValueError(
                "Audit points must be held out and must not use the 'auto:' ID prefix."
            )
        for index, xy in zip(point.panels, (point.left_xy, point.right_xy), strict=True):
            exclusions[index].append(complex(*xy))
    pairs = tuple(combinations(panels, 2))
    storage = len(panels) * (_MAX_FEATURES * 544) + len(pairs) * _MAX_POINTS * 1024
    storage += len(holdouts) * 1024
    fit_reserve = control_point_fit_bytes(len(pairs) * _MAX_POINTS + len(holdouts), len(panels))
    available = budget - storage
    if available < max(_PAIR_WORK_BYTES, fit_reserve):
        raise ValueError("The working budget cannot fit the automatic terrain graph.")
    reserves = [storage + _PAIR_WORK_BYTES, storage + fit_reserve]
    total = len(panels) + len(pairs) + 1
    inner = replace(context, on_progress=None)
    cv = _backend()
    features = {}
    reports = []
    for done, index in enumerate(panels, 1):
        features[index], report, reserve = _features(
            cv, sources[index], index, inner, available, exclusions[index]
        )
        reports.append(report)
        reserves.append(storage + reserve)
        if context.on_progress is not None:
            context.on_progress(done, total)
    matches: list[GroundControlPoint] = []
    edges = []
    for done, pair in enumerate(pairs, len(panels) + 1):
        context.check_cancelled()
        edge, points = _pair_points(
            pair, sources, features, model, _PAIR_WORK_BYTES, inner, exclusions[pair[1]]
        )
        matches.extend(points)
        edges.append(edge)
        if context.on_progress is not None:
            context.on_progress(done, total)
    steps = {index: entry.pixel_step for index, entry in features.items()}
    del features

    def inlier_support(pair: Pair, a: ComplexArray, b: ComplexArray) -> bool:
        return _distributed(a, b, (steps[pair[0]], steps[pair[1]]))

    if matches or holdouts:
        fit = fit_ground_control_points(
            sources,
            [*matches, *holdouts],
            available,
            inner,
            model=model,
            anchor=reference,
            inlier_support=inlier_support,
        )
    else:
        fallback: Model = "translation" if model == "translation" else "similarity"
        fit = ControlPointFit(
            fallback, "disconnected", reference, tuple((i,) for i in panels), (), (), ()
        )
    audit_results = fit.points[-len(holdouts) :] if holdouts else ()
    for row in audit_results:
        if row.status in (
            "same-panel",
            "panel-without-active-ground",
            "nonfinite-position",
            "outside-source",
            "outside-valid-ground",
            "duplicate-correspondence",
        ):
            raise ValueError(f"Audit point {row.id!r} is unusable ({row.status}).")
    if fit.status == "accepted" and any(row.residual_basis != "anchored" for row in audit_results):
        fit = replace(fit, status="audit-unavailable", poses=())
    if context.on_progress is not None:
        context.on_progress(total, total)
    context.check_cancelled()
    return GroundFeatureFit(
        cv.__version__, max(reserves), tuple(reports), tuple(edges), tuple(matches), fit
    )
