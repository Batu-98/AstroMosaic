"""Write an atomic TIFF mosaic with embedded WCS and coverage."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from shutil import disk_usage

from astropy.io import fits
from tifffile import TiffWriter

from astromosaic.io import TIFF_SUFFIXES
from astromosaic.io.atomic import atomic_binary_file
from astromosaic.io.raster import RasterMosaicWriter
from astromosaic.io.tiff import COMPOSITION_VERSION, DESCRIPTION_LIMIT, DESCRIPTION_VERSION


@contextmanager
def open_tiff_mosaic(
    path: Path,
    width: int,
    height: int,
    channels: int,
    header: fits.Header,
    max_output_bytes: int,
    *,
    layers: bool = False,
    publish_check: Callable[[], None] | None = None,
) -> Iterator[RasterMosaicWriter]:
    path = path.absolute()
    if path.suffix.lower() not in TIFF_SUFFIXES:
        raise ValueError("The TIFF output path must end in .tif or .tiff.")
    if channels not in (1, 3):
        raise ValueError("Expected mono or RGB channels for TIFF export.")
    if min(width, height) < 1 or max(width, height) >= 2**32:
        raise ValueError("The mosaic dimensions exceed the supported TIFF range.")
    description = (COMPOSITION_VERSION if layers else DESCRIPTION_VERSION) + header.tostring(
        sep="\n", padding=False
    )
    if len(description) > DESCRIPTION_LIMIT:
        raise ValueError("The TIFF mosaic metadata exceeds its size limit.")
    subimages = 2 if layers else 1
    raster_bytes = width * height * (4 * channels + subimages)
    if raster_bytes + len(description) > max_output_bytes:
        raise ValueError("The TIFF mosaic exceeds the configured output byte limit.")
    free = disk_usage(path.parent).free
    if raster_bytes + len(description) > free:
        raise OSError("There is insufficient disk space for the TIFF mosaic.")

    rgb = channels == 3
    shape = (height, width, 3) if rgb else (height, width)
    bigtiff = raster_bytes + len(description) >= 2**32 - 4096
    with atomic_binary_file(path, publish_check=publish_check) as stream:
        # The writer reserves the rasters on disk and returns their byte offsets.
        with TiffWriter(stream, byteorder="<", bigtiff=bigtiff) as tiff:
            science = tiff.write(
                None,
                shape=shape,
                dtype="float32",
                photometric="rgb" if rgb else "minisblack",
                planarconfig="contig" if rgb else None,
                metadata=None,
                description=description,
                subifds=subimages,
                returnoffset=True,
            )
            offsets = []
            for _ in range(subimages):
                raster = tiff.write(
                    None,
                    shape=(height, width),
                    dtype="uint8",
                    photometric="minisblack",
                    metadata=None,
                    returnoffset=True,
                )
                if raster is None:
                    raise RuntimeError("Could not reserve contiguous TIFF mask rasters.")
                offsets.append(raster[0])
        if science is None:
            raise RuntimeError("Could not reserve a contiguous TIFF science raster.")
        size = stream.seek(0, 2)
        if size > max_output_bytes:
            raise ValueError("The TIFF mosaic exceeds the configured output byte limit.")
        if size > free:
            raise OSError("There is insufficient disk space for the TIFF mosaic.")
        yield RasterMosaicWriter(
            stream, width, science[0], offsets[0], "<f4", offsets[1] if layers else None
        )
