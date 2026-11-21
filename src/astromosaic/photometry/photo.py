"""Linked preview tone and the standard sRGB output transfer."""

from dataclasses import dataclass
from math import isfinite

import numpy as np
from numpy.typing import NDArray

from astromosaic.core import Tile

MIN_MIDTONES = 5
MAX_MIDTONES = 95
DEFAULT_MIDTONES = 25


@dataclass(frozen=True, slots=True)
class PhotoTone:
    midtones: float
    levels: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        validate_midtones(self.midtones)
        if self.levels is not None:
            black, white = self.levels
            if not (isfinite(black) and isfinite(white) and black <= white):
                raise ValueError("Expected finite photo tone levels in black-to-white order.")


def validate_midtones(midtones: float) -> None:
    if not MIN_MIDTONES / 100 <= midtones <= MAX_MIDTONES / 100:
        raise ValueError("Expected preview midtones between 0.05 and 0.95.")


def preview_levels(samples: NDArray[np.float64]) -> tuple[float, float]:
    black, white = np.percentile(samples, (1.0, 99.5))
    if black == white:
        black, white = samples.min(), samples.max()
    return float(black), float(white)


def normalize_levels(samples: NDArray[np.float64], levels: tuple[float, float]) -> None:
    black, white = levels
    if black == white:
        samples.fill(0.5)
    else:
        samples -= black
        samples /= white - black
        np.clip(samples, 0.0, 1.0, out=samples)


def stretch_midtones(samples: NDArray[np.float32], midtones: float) -> NDArray[np.float32]:
    return ((midtones - 1.0) * samples) / (((2.0 * midtones - 1.0) * samples) - midtones)


def encode_srgb(samples: NDArray[np.float32]) -> None:
    """Encode unit-range linear sRGB in place."""
    np.clip(samples, 0.0, 1.0, out=samples)
    high = samples > np.float32(0.0031308)
    np.power(samples, np.float32(1 / 2.4), out=samples, where=high)
    np.multiply(samples, np.float32(1.055), out=samples, where=high)
    np.subtract(samples, np.float32(0.055), out=samples, where=high)
    np.logical_not(high, out=high)
    np.multiply(samples, np.float32(12.92), out=samples, where=high)


def encode_photo_tile(tile: Tile, tone: PhotoTone | None) -> None:
    """Replace the render tile with integer codes held exactly in its float32 buffer."""
    pixels = tile.pixels
    if tone is not None:
        assert tone.levels is not None
        normalized = pixels.astype(np.float64)
        normalize_levels(normalized, tone.levels)
        pixels[:] = stretch_midtones(normalized.astype(np.float32), tone.midtones)
    pixels[~tile.valid] = 0.0
    encode_srgb(pixels)
    pixels *= np.float32(65535)
    np.rint(pixels, out=pixels)
