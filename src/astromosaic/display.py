"""Bounded display buffers and a linked mono/RGB stretch for sky previews."""

from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

from astromosaic.core import Tile
from astromosaic.photometry.photo import (
    DEFAULT_MIDTONES as DEFAULT_MIDTONES,
)
from astromosaic.photometry.photo import (
    MAX_MIDTONES as MAX_MIDTONES,
)
from astromosaic.photometry.photo import (
    MIN_MIDTONES as MIN_MIDTONES,
)
from astromosaic.photometry.photo import (
    encode_srgb,
    normalize_levels,
    preview_levels,
    stretch_midtones,
    validate_midtones,
)
from astromosaic.pipeline.mosaic import PreviewFrame


@dataclass(frozen=True, slots=True, eq=False)
class DisplayFrame:
    output_size: tuple[int, int]
    rgba: NDArray[np.float32]
    has_coverage: bool
    common_coverage: NDArray[np.bool_] | None = None
    seam_width: float | None = None
    photo_levels: tuple[float, float] | None = None
    preserved_rgba: NDArray[np.float32] | None = None
    tone_levels: tuple[float, float] | None = None

    @property
    def size(self) -> tuple[int, int]:
        return self.rgba.shape[1], self.rgba.shape[0]


def normalize_preview(
    frame: PreviewFrame, *, levels: tuple[float, float] | None = None
) -> DisplayFrame:
    return replace(
        normalize_tile(
            frame.tile, frame.output_size, photo=frame.visual_only,
            levels=levels if levels is not None else frame.tone_levels,
        ),
        common_coverage=frame.common_coverage,
        seam_width=frame.seam_width,
    )


def highlight_overlap(frame: DisplayFrame) -> DisplayFrame:
    if frame.common_coverage is None:
        return frame
    rgba = frame.rgba.copy()
    rgba[frame.common_coverage, :3] = (0.0, 0.7, 0.85)
    rgba.setflags(write=False)
    return replace(frame, rgba=rgba)


def normalize_tile(
    tile: Tile, output_size: tuple[int, int], *, photo: bool = False,
    levels: tuple[float, float] | None = None,
) -> DisplayFrame:
    """Set linked black and white points from valid samples only."""
    valid = tile.valid
    rgba = np.zeros((*valid.shape, 4), dtype=np.float32)
    samples = tile.pixels[valid].astype(np.float64)
    preserved = None
    photo_levels = levels if photo else None
    if samples.size:
        levels = levels if levels is not None else preview_levels(samples)
        if photo:
            photo_levels = levels
            preserved = rgba.copy()
            preserved[valid, :3] = samples
            preserved[..., 3] = valid
            preserved.setflags(write=False)
        normalize_levels(samples, levels)
        rgba[valid, :3] = samples.reshape(-1, 1) if samples.ndim == 1 else samples
        rgba[..., 3] = valid
    rgba.setflags(write=False)
    return DisplayFrame(
        output_size, rgba, bool(samples.size), photo_levels=photo_levels, preserved_rgba=preserved,
        tone_levels=levels,
    )


def stretch_rgba(
    frame: DisplayFrame, midtones: float, *, preserve_tone: bool = False
) -> NDArray[np.uint8]:
    """Apply the midtone transfer to the cached display values and retain coverage."""
    validate_midtones(midtones)
    if preserve_tone and frame.preserved_rgba is not None:
        stretched = frame.preserved_rgba[..., :3].copy()
    else:
        stretched = stretch_midtones(frame.rgba[..., :3], midtones)
    if frame.photo_levels is not None:
        encode_srgb(stretched)
    rgba = np.empty(frame.rgba.shape, dtype=np.uint8)
    rgba[..., :3] = np.rint(255.0 * stretched)
    rgba[..., 3] = 255 * frame.rgba[..., 3]
    return rgba
