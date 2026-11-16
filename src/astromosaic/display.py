"""Bounded display buffers and a linked mono/RGB stretch for sky previews."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from astromosaic.core import Tile
from astromosaic.pipeline.mosaic import PreviewFrame

MIN_MIDTONES = 5
MAX_MIDTONES = 95
DEFAULT_MIDTONES = 25


@dataclass(frozen=True, slots=True, eq=False)
class DisplayFrame:
    output_size: tuple[int, int]
    rgba: NDArray[np.float32]
    has_coverage: bool

    @property
    def size(self) -> tuple[int, int]:
        return self.rgba.shape[1], self.rgba.shape[0]


def normalize_preview(frame: PreviewFrame) -> DisplayFrame:
    return normalize_tile(frame.tile, frame.output_size)


def normalize_tile(tile: Tile, output_size: tuple[int, int]) -> DisplayFrame:
    """Set linked black and white points from valid samples only."""
    valid = tile.valid
    rgba = np.zeros((*valid.shape, 4), dtype=np.float32)
    samples = tile.pixels[valid].astype(np.float64)
    if samples.size:
        low, high = np.percentile(samples, (1.0, 99.5))
        if low == high:
            low, high = samples.min(), samples.max()
        if low == high:
            samples.fill(0.5)
        else:
            samples -= low
            samples /= high - low
            np.clip(samples, 0.0, 1.0, out=samples)
        rgba[valid, :3] = samples.reshape(-1, 1) if samples.ndim == 1 else samples
        rgba[..., 3] = valid
    rgba.setflags(write=False)
    return DisplayFrame(output_size, rgba, bool(samples.size))


def stretch_rgba(frame: DisplayFrame, midtones: float) -> NDArray[np.uint8]:
    """Apply the midtone transfer to the cached display values and retain coverage."""
    if not MIN_MIDTONES / 100 <= midtones <= MAX_MIDTONES / 100:
        raise ValueError("Expected preview midtones between 0.05 and 0.95.")
    x = frame.rgba[..., :3]
    stretched = ((midtones - 1.0) * x) / (((2.0 * midtones - 1.0) * x) - midtones)
    rgba = np.empty(frame.rgba.shape, dtype=np.uint8)
    rgba[..., :3] = np.rint(255.0 * stretched)
    rgba[..., 3] = 255 * frame.rgba[..., 3]
    return rgba
