"""Core image data contracts."""

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
    channel_layout: Literal["mono"]
    filter_name: str | None
    unit: str | None
    bitpix: int
    bscale: float
    bzero: float
    wcs_provenance: Literal["primary-header"] | None
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


@dataclass(frozen=True, slots=True)
class Tile:
    region: Region
    pixels: NDArray[np.float32]
    valid: NDArray[np.bool_]
