"""Write a tiled science image and binary coverage into an atomic FITS export."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from shutil import disk_usage

from astropy.io import fits

from astromosaic.io.atomic import atomic_binary_file
from astromosaic.io.raster import RasterMosaicWriter

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


@contextmanager
def open_fits_mosaic(
    path: Path,
    width: int,
    height: int,
    header: fits.Header,
    max_output_bytes: int,
    *,
    layers: bool = False,
) -> Iterator[RasterMosaicWriter]:
    """Publish only after all tiles are written and flushed, without replacing an existing file."""
    path = path.absolute()
    if path.suffix.lower() not in {".fits", ".fit", ".fts"}:
        raise ValueError("The FITS output path must end in .fits, .fit, or .fts.")

    primary = fits.PrimaryHDU(header=header).header
    primary.set("EXTEND", True, after="NAXIS")
    if layers:
        primary["LAYERS"] = (True, "Layer contribution raster present")
    pixels_header = _image_header(primary, width, height, -32)
    coverage_header = _image_header(fits.ImageHDU(name="COVERAGE").header, width, height, 8)
    pixel_count = width * height
    extension_offset = len(pixels_header) + _padded_size(4 * pixel_count)
    coverage_offset = extension_offset + len(coverage_header)
    total_size = coverage_offset + _padded_size(pixel_count)
    layers_header = None
    layers_offset = None
    if layers:
        layers_header = _image_header(fits.ImageHDU(name="LAYERS").header, width, height, 8)
        layers_offset = total_size + len(layers_header)
        total_size = layers_offset + _padded_size(pixel_count)
    if total_size > max_output_bytes:
        raise ValueError("The FITS mosaic exceeds the configured output byte limit.")
    if total_size > disk_usage(path.parent).free:
        raise OSError("There is insufficient disk space for the FITS mosaic.")

    with atomic_binary_file(path) as stream:
        stream.truncate(total_size)
        stream.write(pixels_header)
        primary_end = len(pixels_header) + 4 * pixel_count
        stream.seek(primary_end)
        stream.write(bytes(extension_offset - primary_end))
        stream.seek(extension_offset)
        stream.write(coverage_header)
        coverage_end = coverage_offset + pixel_count
        stream.seek(coverage_end)
        stream.write(bytes(_padded_size(pixel_count) - pixel_count))
        if layers_header is not None and layers_offset is not None:
            stream.write(layers_header)
            stream.seek(layers_offset + pixel_count)
            stream.write(bytes(_padded_size(pixel_count) - pixel_count))
        yield RasterMosaicWriter(
            stream, width, len(pixels_header), coverage_offset, ">f4", layers_offset
        )
