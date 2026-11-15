"""Write a tiled science image and binary coverage into an atomic FITS export."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from shutil import disk_usage
from tempfile import NamedTemporaryFile
from typing import IO

import numpy as np
from astropy.io import fits

from astromosaic.core import Region, Tile

_FITS_BLOCK_SIZE = 2880


def _padded_size(size: int) -> int:
    return ((size + _FITS_BLOCK_SIZE - 1) // _FITS_BLOCK_SIZE) * _FITS_BLOCK_SIZE


def _image_header(header: fits.Header, width: int, height: int, bitpix: int) -> bytes:
    header["BITPIX"] = bitpix
    header["NAXIS"] = 2
    header.set("NAXIS1", width, after="NAXIS")
    header.set("NAXIS2", height, after="NAXIS1")
    encoded: str = header.tostring()
    return encoded.encode("ascii")


class FitsMosaicWriter:
    def __init__(self, stream: IO[bytes], width: int, pixels: int, coverage: int) -> None:
        self._stream = stream
        self._width = width
        self._pixels_offset = pixels
        self._coverage_offset = coverage

    def _write_rectangle(self, offset: int, region: Region, raw: memoryview, itemsize: int) -> None:
        stride = region.width * itemsize
        start = offset + (region.y * self._width + region.x) * itemsize
        if region.width == self._width:
            self._stream.seek(start)
            self._stream.write(raw)
            return
        for row in range(region.height):
            self._stream.seek(start + row * self._width * itemsize)
            self._stream.write(raw[row * stride : (row + 1) * stride])

    def write(self, tile: Tile) -> None:
        pixels = np.ascontiguousarray(tile.pixels, dtype=">f4")
        coverage = np.ascontiguousarray(tile.valid, dtype=np.uint8)
        self._write_rectangle(self._pixels_offset, tile.region, memoryview(pixels).cast("B"), 4)
        self._write_rectangle(self._coverage_offset, tile.region, memoryview(coverage).cast("B"), 1)


@contextmanager
def open_fits_mosaic(
    path: Path, width: int, height: int, header: fits.Header, max_output_bytes: int
) -> Iterator[FitsMosaicWriter]:
    """Publish only after all tiles are written and flushed, without replacing an existing file."""
    path = path.absolute()
    if path.suffix.lower() not in {".fits", ".fit", ".fts"}:
        raise ValueError("The FITS output path must end in .fits, .fit, or .fts.")
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"The output file already exists: {path}")

    primary = fits.PrimaryHDU(header=header).header
    primary.set("EXTEND", True, after="NAXIS")
    pixels_header = _image_header(primary, width, height, -32)
    coverage_header = _image_header(fits.ImageHDU(name="COVERAGE").header, width, height, 8)
    pixel_count = width * height
    extension_offset = len(pixels_header) + _padded_size(4 * pixel_count)
    coverage_offset = extension_offset + len(coverage_header)
    total_size = coverage_offset + _padded_size(pixel_count)
    if total_size > max_output_bytes:
        raise ValueError("The FITS mosaic exceeds the configured output byte limit.")
    if total_size > disk_usage(path.parent).free:
        raise OSError("There is insufficient disk space for the FITS mosaic.")

    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w+b", dir=path.parent, prefix=".astromosaic-", suffix=".part", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.truncate(total_size)
            stream.write(pixels_header)
            primary_end = len(pixels_header) + 4 * pixel_count
            stream.seek(primary_end)
            stream.write(bytes(extension_offset - primary_end))
            stream.seek(extension_offset)
            stream.write(coverage_header)
            coverage_end = coverage_offset + pixel_count
            stream.seek(coverage_end)
            stream.write(bytes(total_size - coverage_end))
            yield FitsMosaicWriter(stream, width, len(pixels_header), coverage_offset)
            stream.flush()
            os.fsync(stream.fileno())

        if os.name == "nt":
            # Windows rename fails if another job published the destination first.
            temporary.rename(path)
        else:
            os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
