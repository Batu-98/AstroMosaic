"""Exercise FITS reading and WCS reprojection on a small, known cutout."""

from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from reproject import reproject_interp

from astromosaic.core import Region
from astromosaic.io.fits import open_fits_panel


def write_smoke_panel(path: Path) -> None:
    """Generate a deterministic scaled integer FITS without using any external data."""
    y, x = np.indices((12, 16), dtype=np.int16)
    raw = 4 * y + x - 15
    raw[4, 6] = -32768

    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crpix = [5.0, 4.0]
    wcs.wcs.crval = [359.999, 20.0]
    wcs.wcs.cdelt = [-0.002, 0.002]
    hdu = fits.PrimaryHDU(raw, header=wcs.to_header())
    hdu.header.update(
        {"BSCALE": 0.5, "BZERO": -2.0, "BLANK": -32768, "FILTER": "L", "BUNIT": "MJy/sr"}
    )
    hdu.writeto(path)


def _process_cutout() -> dict[str, int | float]:
    region = Region(x=3, y=2, width=5, height=4)
    with TemporaryDirectory(prefix="astromosaic-") as directory:
        path = Path(directory) / "input.fits"
        write_smoke_panel(path)
        with open_fits_panel(path, max_tile_bytes=8192) as panel:
            tile = panel.read_tile(region, halo=1)
            wcs = WCS(panel.header).celestial

    shape = (region.height, region.width)
    pixels = np.empty(shape, dtype=np.float32)
    coverage = np.empty(shape, dtype=np.float32)
    reproject_interp(
        (tile.pixels, wcs.slice(tile.region.slices)),
        wcs.slice(region.slices),
        shape,
        order="nearest-neighbor",
        output_array=pixels,
        output_footprint=coverage,
    )
    expected = np.array(
        [
            [-4.0, -3.5, -3.0, -2.5, -2.0],
            [-2.0, -1.5, -1.0, -0.5, 0.0],
            [0.0, 0.5, 1.0, np.nan, 2.0],
            [2.0, 2.5, 3.0, 3.5, 4.0],
        ],
        dtype=np.float32,
    )
    valid = np.isfinite(expected)
    if not np.array_equal(pixels, expected, equal_nan=True) or not np.array_equal(coverage, valid):
        raise RuntimeError("The synthetic FITS cutout disagrees with its known values or coverage.")

    return {
        "width": region.width,
        "height": region.height,
        "valid_pixels": int(valid.sum()),
        "min_pixel": float(np.nanmin(pixels)),
        "max_pixel": float(np.nanmax(pixels)),
    }


def run_smoke(*, spawn: bool = False) -> dict[str, int | float | str | bool]:
    if spawn:
        with ProcessPoolExecutor(max_workers=1, mp_context=get_context("spawn")) as pool:
            result = pool.submit(_process_cutout).result()
    else:
        result = _process_cutout()
    return {**result, "backend": "cpu", "spawned": spawn}
