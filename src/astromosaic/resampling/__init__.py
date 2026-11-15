"""Windowed, mask-aware bilinear sampling of original image data."""

from dataclasses import dataclass
from math import ceil, floor
from typing import cast

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import map_coordinates

from astromosaic.core import Region, Tile

_CENTER_TOLERANCE = 1e-7  # source pixels
_SUPPORT_TOLERANCE = 1e-10


@dataclass(frozen=True, slots=True)
class SamplingWindow:
    region: Region
    indices: NDArray[np.intp]
    coordinates: NDArray[np.float64]


def source_window(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    usable: NDArray[np.bool_],
    width: int,
    height: int,
) -> SamplingWindow | None:
    # Give coordinates computed at the same half-pixel edge a stable side of the footprint.
    inside = (
        usable
        & (x >= -0.5 - _CENTER_TOLERANCE)
        & (x < width - 0.5 - _CENTER_TOLERANCE)
        & (y >= -0.5 - _CENTER_TOLERANCE)
        & (y < height - 0.5 - _CENTER_TOLERANCE)
    )
    indices = np.flatnonzero(inside)
    if not indices.size:
        return None

    sx = np.clip(x[indices], 0, width - 1)
    sy = np.clip(y[indices], 0, height - 1)
    for axis in (sx, sy):
        nearest = np.rint(axis)
        np.copyto(axis, nearest, where=np.abs(axis - nearest) <= _CENTER_TOLERANCE)

    left, top = floor(sx.min()), floor(sy.min())
    # Include every pixel with nonzero bilinear weight, including across tile seams.
    right, bottom = ceil(sx.max()) + 1, ceil(sy.max()) + 1
    return SamplingWindow(
        Region(left, top, right - left, bottom - top), indices, np.stack((sy - top, sx - left))
    )


def sample(tile: Tile, window: SamplingWindow) -> tuple[NDArray[np.intp], NDArray[np.float64]]:
    support = map_coordinates(
        tile.valid, window.coordinates, order=1, output=np.float64, prefilter=False
    )
    has_support = support >= 1 - _SUPPORT_TOLERANCE
    # Zero the missing payloads for interpolation. The separate mask gates each sample.
    coordinates = window.coordinates[:, has_support]
    normalization = support[has_support]
    if tile.pixels.ndim == 2:
        np.copyto(tile.pixels, 0, where=~tile.valid)
        values = map_coordinates(
            tile.pixels, coordinates, order=1, output=np.float64, prefilter=False
        )
    else:
        np.copyto(tile.pixels, 0, where=~tile.valid[..., None])
        values = np.stack(
            [
                map_coordinates(plane, coordinates, order=1, output=np.float64, prefilter=False)
                for plane in np.moveaxis(tile.pixels, -1, 0)
            ],
            axis=-1,
        )
        normalization = normalization[:, None]
    return window.indices[has_support], cast(NDArray[np.float64], values / normalization)
