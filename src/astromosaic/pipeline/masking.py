"""Make bounded panel thumbnails and propose local, bottom-attached horizons."""

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import median_filter

from astromosaic.core import Region, Tile
from astromosaic.core.job import JobContext
from astromosaic.core.masks import (
    FOREGROUND,
    MASK_EDGE,
    SKY,
    ForegroundSuggestion,
    SourceMask,
    bounded_grid,
    grid_cells,
)
from astromosaic.io import PanelSource

DETECTION_EDGE = 128


def read_thumbnail(
    source: PanelSource, edge: int, budget: int, context: JobContext, *, binary_mask: bool = False
) -> Tile:
    """Area-average valid pixels using a single decoded source tile at a time."""
    panel = source.descriptor
    width, height = panel.width, panel.height
    columns, rows = bounded_grid((width, height), edge)
    if edge > MASK_EDGE:
        raise ValueError("The mask thumbnail exceeds the supported grid size.")
    reserved = 128 * columns * rows
    step = 256
    while step:
        largest = Region(0, 0, min(width, step), min(height, step))
        if reserved + source.tile_bytes(largest) + 48 * largest.width * largest.height <= budget:
            break
        step //= 2
    if not step:
        raise ValueError("The working budget cannot fit a panel thumbnail and source tile.")

    sums = np.zeros((rows, columns), dtype=np.float64)
    counts = np.zeros((rows, columns), dtype=np.int64)
    completed = 0
    for y in range(0, height, step):
        bottom = min(y + step, height)
        row_cells = grid_cells(y, bottom, height, rows)
        row_starts = _cell_starts(row_cells)
        for x in range(0, width, step):
            context.check_cancelled()
            right = min(x + step, width)
            col_cells = grid_cells(x, right, width, columns)
            col_starts = _cell_starts(col_cells)
            tile = source.read_tile(Region(x, y, right - x, bottom - y))
            pixels = tile.pixels
            if pixels.ndim == 3:
                pixels = pixels.mean(axis=-1, dtype=np.float64)
            if binary_mask and np.any((pixels != 0) & (pixels != 1)):
                raise ValueError("Expected binary values in the FITS sky mask.")
            cells = np.s_[row_cells[0] : row_cells[-1] + 1, col_cells[0] : col_cells[-1] + 1]
            subtotal = np.add.reduceat(
                np.where(tile.valid, pixels, 0), row_starts, axis=0, dtype=np.float64
            )
            support = np.add.reduceat(tile.valid, row_starts, axis=0, dtype=np.int64)
            sums[cells] += np.add.reduceat(subtotal, col_starts, axis=1)
            counts[cells] += np.add.reduceat(support, col_starts, axis=1)
            completed += tile.region.width * tile.region.height
            del tile, pixels, subtotal, support
            if context.on_progress is not None:
                context.on_progress(completed, width * height)

    context.check_cancelled()
    valid = counts > 0
    pixels = np.full((rows, columns), np.nan, dtype=np.float32)
    np.divide(sums, counts, out=pixels, where=valid)
    return Tile(Region(0, 0, columns, rows), pixels, valid)


def _cell_starts(cells: NDArray[np.int64]) -> NDArray[np.intp]:
    return np.flatnonzero(np.diff(cells, prepend=-1))


def _horizon(
    thumb: Tile,
) -> tuple[ForegroundSuggestion, NDArray[np.intp], NDArray[np.bool_], NDArray[np.intp]]:
    height, width = thumb.valid.shape
    empty: tuple[ForegroundSuggestion, NDArray[np.intp], NDArray[np.bool_], NDArray[np.intp]] = (
        "sky-only",
        np.zeros(width, dtype=np.intp),
        np.zeros(width, dtype=np.bool_),
        np.zeros(width, dtype=np.intp),
    )
    if min(width, height) < 12 or np.count_nonzero(thumb.valid) < 0.3 * width * height:
        return empty
    samples = thumb.pixels[thumb.valid].astype(np.float64)
    low, middle, high = np.percentile(samples, (5, 50, 95))
    if high <= low:
        return empty

    image = np.where(thumb.valid, thumb.pixels.astype(np.float64), middle)
    smooth = median_filter(image, size=3, mode="nearest")
    adjacent = thumb.valid[:-1] & thumb.valid[1:]
    differences = np.abs(np.diff(smooth, axis=0))[adjacent]
    noise = float(np.median(differences)) if differences.size else 0.0
    threshold = max(3.0 * noise, 0.012 * (high - low))

    band = min(5, max(2, height // 48))
    search = np.arange(max(2 * band, height // 9), min(height - 2 * band, 15 * height // 16) + 1)
    support = np.cumsum(thumb.valid, axis=0, dtype=np.int32)
    support = np.pad(support, ((1, 0), (0, 0)))
    prefix = np.pad(np.cumsum(smooth, axis=0), ((1, 0), (0, 0)))
    before, upper, lower, after = (
        np.diff(prefix[search[None, :] + band * np.arange(-2, 3)[:, None]], axis=0) / band
    )
    contrast = lower - upper
    strength = np.abs(contrast) - np.maximum(np.abs(upper - before), np.abs(after - lower))
    strength[support[search + 2 * band] - support[search - 2 * band] != 4 * band] = 0.0

    best = np.argmax(strength, axis=0)
    columns = np.arange(width)
    levels = search[best]
    scores = strength[best, columns]
    polarity = contrast[best, columns] > 0
    credible = scores >= threshold
    neighbors = np.zeros(width, dtype=np.uint8)
    for offset in (-2, -1, 1, 2):
        center = slice(max(0, -offset), min(width, width - offset))
        nearby = slice(max(0, offset), min(width, width + offset))
        neighbors[center] += (
            credible[nearby]
            & (polarity[center] == polarity[nearby])
            & (np.abs(levels[center] - levels[nearby]) <= 2 * band)
        )
    coherent = credible & (neighbors >= 2)
    # Isolated stellar profiles can produce a strong step across a few columns.
    linked = (
        coherent[:-1]
        & coherent[1:]
        & (polarity[:-1] == polarity[1:])
        & (np.abs(np.diff(levels)) <= 2 * band)
    )
    ends = np.r_[0, np.flatnonzero(~linked) + 1, width]
    runs = np.diff(ends)
    coherent &= np.repeat(runs >= max(4, (width + 63) // 64), runs)
    positive = np.count_nonzero(coherent & polarity)
    negative = np.count_nonzero(coherent & ~polarity)
    selected = coherent & (polarity == (positive >= negative))
    fraction = max(positive, negative) / width
    strong = np.count_nonzero(selected & (scores >= 1.5 * threshold)) / width
    suggestion: ForegroundSuggestion = "sky-only"
    if fraction >= 0.68 and strong >= 0.55:
        suggestion = "mixed"
    elif fraction >= 0.32:
        suggestion = "uncertain"
    # Strong steps need less padding around the boundary than low-contrast edges.
    sharp = scores >= max(8 * noise, 0.10 * (high - low))
    margin = np.where(sharp, max(2, band // 2), band + 1)
    return suggestion, levels, selected, margin


def suggest_foreground(thumb: Tile) -> ForegroundSuggestion:
    return _horizon(thumb)[0]


def propose_mask(
    thumb: Tile, source_size: tuple[int, int], context: JobContext
) -> SourceMask | None:
    context.check_cancelled()
    suggestion, levels, selected, margin = _horizon(thumb)
    context.check_cancelled()
    if suggestion == "sky-only":
        return None
    rows = np.arange(thumb.region.height)[:, None]
    labels = np.zeros(thumb.valid.shape, dtype=np.uint8)
    labels[(rows < levels - margin) & selected] = SKY
    labels[(rows >= levels + margin) & selected] = FOREGROUND
    return SourceMask(source_size, labels.tobytes())
