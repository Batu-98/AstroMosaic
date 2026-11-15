"""Write an atomic TIFF mosaic with embedded WCS and coverage."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from shutil import disk_usage

from astropy.io import fits
from tifffile import TiffWriter

from astromosaic.io import TIFF_SUFFIXES
from astromosaic.io.atomic import atomic_binary_file
from astromosaic.io.raster import RasterMosaicWriter
from astromosaic.io.tiff import DESCRIPTION_LIMIT, DESCRIPTION_VERSION


@contextmanager
def open_tiff_mosaic(
    path: Path, width: int, height: int, channels: int, header: fits.Header, max_output_bytes: int
) -> Iterator[RasterMosaicWriter]:
    path = path.absolute()
    if path.suffix.lower() not in TIFF_SUFFIXES:
        raise ValueError("The TIFF output path must end in .tif or .tiff.")
    if channels not in (1, 3):
        raise ValueError("Expected mono or RGB channels for TIFF export.")
    if min(width, height) < 1 or max(width, height) >= 2**32:
        raise ValueError("The mosaic dimensions exceed the supported TIFF range.")
    description = DESCRIPTION_VERSION + header.tostring(sep="\n", padding=False)
    if len(description) > DESCRIPTION_LIMIT:
        raise ValueError("The TIFF mosaic metadata exceeds its size limit.")
    raster_bytes = width * height * (4 * channels + 1)
    if raster_bytes + len(description) > max_output_bytes:
        raise ValueError("The TIFF mosaic exceeds the configured output byte limit.")
    free = disk_usage(path.parent).free
    if raster_bytes + len(description) > free:
        raise OSError("There is insufficient disk space for the TIFF mosaic.")

    rgb = channels == 3
    shape = (height, width, 3) if rgb else (height, width)
    bigtiff = raster_bytes + len(description) >= 2**32 - 4096
    with atomic_binary_file(path) as stream:
        # The writer reserves both rasters on disk and returns their byte offsets.
        with TiffWriter(stream, byteorder="<", bigtiff=bigtiff) as tiff:
            science = tiff.write(
                None,
                shape=shape,
                dtype="float32",
                photometric="rgb" if rgb else "minisblack",
                planarconfig="contig" if rgb else None,
                metadata=None,
                description=description,
                subifds=1,
                returnoffset=True,
            )
            coverage = tiff.write(
                None,
                shape=(height, width),
                dtype="uint8",
                photometric="minisblack",
                metadata=None,
                returnoffset=True,
            )
        if science is None or coverage is None:
            raise RuntimeError("Could not reserve contiguous TIFF science and coverage rasters.")
        size = stream.seek(0, 2)
        if size > max_output_bytes:
            raise ValueError("The TIFF mosaic exceeds the configured output byte limit.")
        if size > free:
            raise OSError("There is insufficient disk space for the TIFF mosaic.")
        yield RasterMosaicWriter(stream, width, science[0], coverage[0], "<f4")
