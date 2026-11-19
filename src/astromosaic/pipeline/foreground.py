"""Estimate anchored ground translations using only masked terrestrial texture."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations
from math import ceil, floor, isfinite
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.signal import fftconvolve

from astromosaic.astrometry.registration import components, robust_linear_fit
from astromosaic.core import Region, Tile
from astromosaic.core.job import JobContext
from astromosaic.io import PanelSource
from astromosaic.pipeline.masking import read_thumbnail

_ALIGNMENT_EDGE = 256
MIN_GROUND_CORRELATION = 0.72
MIN_GROUND_PEAK_SEPARATION = 0.06
_MAX_GRAPH_RESIDUAL = 1.0

type _CorrelationStage = Literal["support", "texture", "correlation", "ambiguity", "matched"]
type ForegroundPairStage = Literal[
    "support", "texture", "correlation", "ambiguity", "refinement", "accepted"
]
type ForegroundGraphResiduals = tuple[tuple[tuple[int, int], float], ...]


class ForegroundAlignmentRejected(ValueError):
    """A rejected foreground graph with project panel indices and source-pixel residuals."""

    def __init__(
        self,
        message: str,
        stage: Literal["disconnected", "graph-disagreement"],
        groups: tuple[tuple[int, ...], ...],
        residuals: ForegroundGraphResiduals = (),
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.groups = groups
        self.residuals = residuals


@dataclass(frozen=True, slots=True)
class GroundPanel:
    index: int
    shift: tuple[float, float]

    def __post_init__(self) -> None:
        if self.index < 0 or any(not isfinite(value) for value in self.shift):
            raise ValueError("Invalid foreground panel transform.")


@dataclass(frozen=True, slots=True)
class GroundOverlap:
    panels: tuple[int, int]
    correlation: float
    support: int
    patches: int

    def __post_init__(self) -> None:
        left, right = self.panels
        if (
            not 0 <= left < right
            or not MIN_GROUND_CORRELATION <= self.correlation <= 1.0
            or self.support < 1
            or self.patches < 0
        ):
            raise ValueError("Invalid foreground match evidence.")


@dataclass(frozen=True, slots=True)
class ForegroundAlignment:
    source_size: tuple[int, int]
    canvas: Region
    panels: tuple[GroundPanel, ...]
    overlaps: tuple[GroundOverlap, ...]

    def __post_init__(self) -> None:
        indices = tuple(panel.index for panel in self.panels)
        known = set(indices)
        if (
            min(*self.source_size, self.canvas.width, self.canvas.height) < 1
            or not indices
            or tuple(sorted(known)) != indices
            or self.panels[0].shift != (0.0, 0.0)
            or any(not known.issuperset(edge.panels) for edge in self.overlaps)
        ):
            raise ValueError("Invalid saved foreground alignment.")


@dataclass(frozen=True, slots=True)
class GroundCorrelation:
    stage: _CorrelationStage
    usable_samples: tuple[int, int]
    shared_threshold: float
    maximum_shared_samples: int | None = None
    peak_shared_samples: int | None = None
    peak: float | None = None
    competing_peak: float | None = None
    shift: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class GroundRefinement:
    tested_patches: int
    matched_patches: int
    agreeing_patches: int
    shift: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class ForegroundPairDiagnostic:
    panels: tuple[int, int]
    thumbnail: GroundCorrelation
    refinement: GroundRefinement | None

    @property
    def stage(self) -> ForegroundPairStage:
        if self.thumbnail.stage != "matched":
            return self.thumbnail.stage
        if self.refinement is not None and self.refinement.shift is None:
            return "refinement"
        return "accepted"


def _texture(tile: Tile) -> NDArray[np.float32] | None:
    values = tile.pixels
    if values.ndim == 3:
        values = values.mean(axis=-1, dtype=np.float64).astype(np.float32)
    observed = values[tile.valid].astype(np.float64)
    if observed.size < 24:
        return None
    scale = observed.std()
    if scale == 0:
        return None
    texture = np.zeros(tile.valid.shape, dtype=np.float32)
    texture[tile.valid] = (observed - observed.mean()) / scale
    return texture


def _correlate(a: NDArray[np.float32], b: NDArray[np.float32]) -> NDArray[np.float32]:
    return fftconvolve(a, b[::-1, ::-1], mode="full")  # type: ignore[no-any-return]


def _match(left: Tile, right: Tile, budget: int) -> GroundCorrelation:
    lh, lw = left.valid.shape
    rh, rw = right.valid.shape
    if 128 * (lh + rh - 1) * (lw + rw - 1) > budget:
        raise ValueError("The working budget cannot fit foreground correlation buffers.")
    counts = (int(np.count_nonzero(left.valid)), int(np.count_nonzero(right.valid)))
    threshold = max(24.0, 0.18 * min(counts))
    a, b = _texture(left), _texture(right)
    if a is None or b is None:
        return GroundCorrelation("support" if min(counts) < 24 else "texture", counts, threshold)
    am, bm = left.valid.astype(np.float32), right.valid.astype(np.float32)
    overlap = np.rint(_correlate(am, bm))
    maximum_support = int(overlap.max())
    supported = overlap >= threshold
    if not supported.any():
        return GroundCorrelation("support", counts, threshold, maximum_support)
    count = np.maximum(overlap, 1)
    sa, sb = _correlate(a, bm), _correlate(am, b)
    aa = _correlate(a * a, bm) - sa * sa / count
    bb = _correlate(am, b * b) - sb * sb / count
    covariance = _correlate(a, b) - sa * sb / count
    supported &= (aa > 0.003 * count) & (bb > 0.003 * count)
    score = np.full(overlap.shape, -np.inf, dtype=np.float32)
    np.divide(
        covariance, np.sqrt(np.maximum(aa, 0) * np.maximum(bb, 0)), out=score, where=supported
    )
    row, col = (int(value) for value in np.unravel_index(score.argmax(), score.shape))
    peak = min(float(score[row, col]), 1.0)
    if peak == -np.inf:
        return GroundCorrelation("texture", counts, threshold, maximum_support)
    peak_support = int(overlap[row, col])
    if peak < MIN_GROUND_CORRELATION:
        return GroundCorrelation(
            "correlation", counts, threshold, maximum_support, peak_support, peak
        )
    # Peaks more than two pixels apart can represent distinct repeated structures.
    score[max(row - 2, 0) : row + 3, max(col - 2, 0) : col + 3] = -np.inf
    competing = float(score.max())
    if peak - competing < MIN_GROUND_PEAK_SEPARATION:
        return GroundCorrelation(
            "ambiguity", counts, threshold, maximum_support, peak_support, peak, competing
        )
    return GroundCorrelation(
        "matched",
        counts,
        threshold,
        maximum_support,
        peak_support,
        peak,
        competing if isfinite(competing) else None,
        shift=(
            float(col - rw + 1 + left.region.x - right.region.x),
            float(row - rh + 1 + left.region.y - right.region.y),
        ),
    )


def _refine_shift(
    left: PanelSource,
    right: PanelSource,
    coarse: tuple[float, float],
    factors: tuple[float, float],
    budget: int,
    context: JobContext,
) -> GroundRefinement:
    width, height = left.descriptor.width, left.descriptor.height
    dx, dy = (round(shift * factor) for shift, factor in zip(coarse, factors, strict=True))
    x0, x1 = max(0, dx), min(width, width + dx)
    y0, y1 = max(0, dy), min(height, height + dy)
    size = min(64, x1 - x0, y1 - y0)
    if size < 12:
        return GroundRefinement(0, 0, 0)
    margin = ceil(max(factors) * 1.75) + 2
    xs = np.unique(np.linspace(x0, x1 - size, 4, dtype=np.int64))
    ys = np.unique(np.linspace(y0, y1 - size, 5, dtype=np.int64))
    tested = len(xs) * len(ys)
    accepted = []
    for y in ys:
        for x in xs:
            context.check_cancelled()
            a = Region(int(x), int(y), size, size)
            bx, by = max(0, a.x - dx - margin), max(0, a.y - dy - margin)
            b = Region(
                bx,
                by,
                min(width, a.x + size - dx + margin) - bx,
                min(height, a.y + size - dy + margin) - by,
            )
            remaining = budget - left.tile_bytes(a) - right.tile_bytes(b)
            if remaining < 128 * (a.width + b.width - 1) * (a.height + b.height - 1):
                raise ValueError("The working budget cannot fit a full-resolution ground match.")
            shift = _match(left.read_tile(a), right.read_tile(b), remaining).shift
            if shift is not None and max(abs(shift[0] - dx), abs(shift[1] - dy)) <= margin:
                accepted.append(shift)
    if len(accepted) < 2:
        return GroundRefinement(tested, len(accepted), len(accepted))
    shifts = np.asarray(accepted)
    median = np.median(shifts, axis=0)
    good = np.max(np.abs(shifts - median), axis=1) <= 1.0
    count = int(good.sum())
    if count < max(2, 0.75 * len(accepted)):
        return GroundRefinement(tested, len(accepted), count)
    x_shift, y_shift = np.median(shifts[good], axis=0)
    return GroundRefinement(tested, len(accepted), count, (float(x_shift), float(y_shift)))


def align_foreground(
    candidates: Sequence[tuple[int, PanelSource, Region]],
    budget: int,
    context: JobContext,
    *,
    on_pair: Callable[[ForegroundPairDiagnostic], None] | None = None,
) -> ForegroundAlignment:
    """Find full-resolution translations on a common pixel scale and orientation."""
    if not candidates:
        raise ValueError("Apply an editable foreground mask to at least one panel.")
    first = candidates[0][1].descriptor
    size = (first.width, first.height)
    if any(
        (source.descriptor.width, source.descriptor.height) != size for _, source, _ in candidates
    ):
        raise ValueError(
            "Foreground alignment requires matching source dimensions and pixel scale."
        )

    count = len(candidates)
    total = count + count * (count - 1) // 2
    thumbs = []
    retained = 0
    steps = 0

    def progress() -> None:
        nonlocal steps
        steps += 1
        if context.on_progress is not None:
            context.on_progress(steps, total)

    for index, source, _ in candidates:
        thumb = read_thumbnail(
            source, _ALIGNMENT_EDGE, budget - retained, JobContext(context.is_cancelled)
        )
        if not thumb.valid.any():
            raise ValueError(f"Panel {index + 1} has no valid foreground samples.")
        retained += thumb.pixels.nbytes + thumb.valid.nbytes
        thumbs.append(thumb)
        progress()

    edges, offsets, evidence = [], [], []
    grid = thumbs[0].region
    factors = (size[0] / grid.width, size[1] / grid.height)
    for left, right in combinations(range(count), 2):
        context.check_cancelled()
        match = _match(thumbs[left], thumbs[right], budget - retained)
        panel_pair = (candidates[left][0], candidates[right][0])
        refinement = None
        shift = match.shift
        if shift is not None and factors != (1.0, 1.0):
            refinement = _refine_shift(
                candidates[left][1],
                candidates[right][1],
                shift,
                factors,
                budget - retained,
                context,
            )
            shift = refinement.shift
        context.check_cancelled()
        if on_pair is not None:
            on_pair(ForegroundPairDiagnostic(panel_pair, match, refinement))
        if shift is not None:
            assert match.peak is not None and match.peak_shared_samples is not None
            edges.append((left, right))
            offsets.append(shift)
            evidence.append(
                GroundOverlap(
                    panel_pair,
                    match.peak,
                    match.peak_shared_samples,
                    refinement.agreeing_patches if refinement is not None else 0,
                )
            )
        progress()

    context.check_cancelled()
    groups = tuple(tuple(candidates[i][0] for i in group) for group in components(count, edges))
    if len(groups) > 1:
        panel_groups = " | ".join(", ".join(str(i + 1) for i in group) for group in groups)
        raise ForegroundAlignmentRejected(
            f"Weak or disconnected foreground overlaps. Panel groups {panel_groups}.",
            "disconnected",
            groups,
        )
    shifts = np.zeros((count, 2), dtype=np.float64)
    if edges:
        if 64 * len(edges) * count > budget - retained:
            raise ValueError("The working budget cannot fit the foreground alignment graph.")
        matrix = np.zeros((len(edges), count), dtype=np.float64)
        for row, (left, right) in enumerate(edges):
            matrix[row, left], matrix[row, right] = -1, 1
        expected = np.asarray(offsets, dtype=np.float64)
        weights = np.sqrt([edge.support for edge in evidence])
        shifts[1:] = robust_linear_fit(matrix[:, 1:], expected, weights)
        residuals = np.max(np.abs(matrix @ shifts - expected), axis=1)
        if np.max(residuals) > _MAX_GRAPH_RESIDUAL:
            raise ForegroundAlignmentRejected(
                "Foreground overlaps disagree by more than one source pixel.",
                "graph-disagreement",
                groups,
                tuple(
                    (edge.panels, float(residual))
                    for edge, residual in zip(evidence, residuals, strict=True)
                    if residual > _MAX_GRAPH_RESIDUAL
                ),
            )
        rounded = np.rint(shifts)
        np.copyto(shifts, rounded, where=np.abs(shifts - rounded) < 1e-9)
    places = tuple(
        GroundPanel(item[0], (float(x), float(y)))
        for item, (x, y) in zip(candidates, shifts, strict=True)
    )
    boxes = [item[2] for item in candidates]
    xmin = floor(min(box.x + panel.shift[0] for box, panel in zip(boxes, places, strict=True)))
    ymin = floor(min(box.y + panel.shift[1] for box, panel in zip(boxes, places, strict=True)))
    xmax = ceil(
        max(box.x + box.width + panel.shift[0] for box, panel in zip(boxes, places, strict=True))
    )
    ymax = ceil(
        max(box.y + box.height + panel.shift[1] for box, panel in zip(boxes, places, strict=True))
    )
    context.check_cancelled()
    return ForegroundAlignment(
        size, Region(xmin, ymin, xmax - xmin, ymax - ymin), places, tuple(evidence)
    )
