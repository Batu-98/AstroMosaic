"""Core image data contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    size_bytes: int
    modified_ns: int


@dataclass(frozen=True, slots=True)
class PanelDescriptor:
    fingerprint: SourceFingerprint
    width: int
    height: int
    channel_layout: Literal["mono", "rgb"]
    filter_name: str | None
    unit: str | None
    bitpix: int
    bscale: float
    bzero: float
    wcs_provenance: Literal["primary-header", "tiff-description", "xisf-fits-keywords"] | None
    blank: int | None
    mask_provenance: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Region:
    """Zero-based pixel rectangle with exclusive right and bottom edges."""

    x: int
    y: int
    width: int
    height: int

    @property
    def slices(self) -> tuple[slice, slice]:
        return slice(self.y, self.y + self.height), slice(self.x, self.x + self.width)

    def with_halo(self, width: int, height: int, halo: int) -> Region:
        right = self.x + self.width
        bottom = self.y + self.height
        if not (0 <= self.x < right <= width and 0 <= self.y < bottom <= height) or halo < 0:
            raise ValueError("Expected a nonempty in-bounds tile and a nonnegative halo.")
        x = max(0, self.x - halo)
        y = max(0, self.y - halo)
        return Region(x, y, min(width, right + halo) - x, min(height, bottom + halo) - y)


@dataclass(frozen=True, slots=True)
class Tile:
    """Linear YX mono or YXC RGB samples and one shared YX validity mask."""

    region: Region
    pixels: NDArray[np.float32]
    valid: NDArray[np.bool_]
