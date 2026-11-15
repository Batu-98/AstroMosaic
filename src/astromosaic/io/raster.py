"""Write tiles into two reserved row-major rasters in one file."""

from typing import IO

import numpy as np

from astromosaic.core import Region, Tile


class RasterMosaicWriter:
    def __init__(
        self, stream: IO[bytes], width: int, pixels: int, coverage: int, pixel_dtype: str
    ) -> None:
        self._stream = stream
        self._width = width
        self._pixels_offset = pixels
        self._coverage_offset = coverage
        self._pixel_dtype = pixel_dtype

    def _write_rectangle(self, offset: int, region: Region, raw: memoryview, stride: int) -> None:
        pixel_bytes = stride // region.width
        start = offset + (region.y * self._width + region.x) * pixel_bytes
        if region.width == self._width:
            self._stream.seek(start)
            self._stream.write(raw)
            return
        for row in range(region.height):
            self._stream.seek(start + row * self._width * pixel_bytes)
            self._stream.write(raw[row * stride : (row + 1) * stride])

    def write(self, tile: Tile) -> None:
        pixels = np.ascontiguousarray(tile.pixels, dtype=self._pixel_dtype)
        coverage = np.ascontiguousarray(tile.valid, dtype=np.uint8)
        self._write_rectangle(
            self._pixels_offset,
            tile.region,
            memoryview(pixels).cast("B"),
            pixels.nbytes // tile.region.height,
        )
        self._write_rectangle(
            self._coverage_offset, tile.region, memoryview(coverage).cast("B"), tile.region.width
        )
