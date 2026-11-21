"""A tile adapter used only for visual sky previews of known sRGB panels."""

import numpy as np
from astropy.io.fits import Header

from astromosaic.core import Region, Tile
from astromosaic.io import PanelSource


class SrgbPreviewSource:
    def __init__(self, source: PanelSource, max_tile_bytes: int) -> None:
        self._source = source
        self._max_tile_bytes = max_tile_bytes
        self.descriptor = source.descriptor
        self.sky_mask_fingerprint = source.sky_mask_fingerprint

    @property
    def header(self) -> Header:
        return self._source.header

    def tile_bytes(self, region: Region) -> int:
        # Include the three-channel transfer-curve branch mask.
        return self._source.tile_bytes(region) + 3 * region.width * region.height

    def read_tile(self, region: Region, *, halo: int = 0) -> Tile:
        actual = region.with_halo(self.descriptor.width, self.descriptor.height, halo)
        if self.tile_bytes(actual) > self._max_tile_bytes:
            raise ValueError("The sRGB preview tile exceeds the configured byte budget.")
        tile = self._source.read_tile(actual)
        pixels = tile.pixels
        pixels *= np.float32(1 / 65535)
        high = pixels > np.float32(0.04045)
        np.add(pixels, np.float32(0.055), out=pixels, where=high)
        np.divide(pixels, np.float32(1.055), out=pixels, where=high)
        np.power(pixels, np.float32(2.4), out=pixels, where=high)
        np.logical_not(high, out=high)
        np.divide(pixels, np.float32(12.92), out=pixels, where=high)
        return tile
