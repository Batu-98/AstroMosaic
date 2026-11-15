"""Independent truth for the Phase 1 two-panel FITS reference."""

from math import atan2, cos, degrees, hypot, radians, sin
from pathlib import Path

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray

SHAPE = (9, 15)
CENTER = (359.999, 20.0)
SCALE_ARCSEC = 7.2
WEIGHTS = (1.0, 3.0)


def write_reference_panels(directory: Path) -> tuple[Path, Path]:
    x, y = np.meshgrid(np.arange(1, 9), np.arange(1, 7))
    left_values = (2 * x + 4 * y - 8).astype(np.int16)
    for bad_x, bad_y in ((3, 3), (7, 3), (8, 5)):
        left_values[bad_y - 1, bad_x - 1] = -32768
    left = directory / "Panel A.fits"
    left_hdu = fits.PrimaryHDU(left_values, header=source_header(1, 1))
    left_hdu.header.update({"BSCALE": 0.5, "BZERO": -4.0, "BLANK": -32768})
    left_hdu.writeto(left)

    x, y = np.meshgrid(np.arange(6, 13), np.arange(2, 7))
    right_values = (x + 2 * y - 4.5).astype(np.float32)
    right_values[4 - 2, 6 - 6] = np.nan
    right_values[5 - 2, 8 - 6] = np.nan
    right_values[6 - 2, 11 - 6] = np.inf
    right = directory / "Panel B.fits"
    fits.writeto(right, right_values, header=source_header(6, 2))
    return left, right


def source_header(offset_x: int, offset_y: int) -> fits.Header:
    return fits.Header(
        {
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "RADESYS": "ICRS",
            "CRVAL1": CENTER[0],
            "CRVAL2": CENTER[1],
            "CRPIX1": 8.0 - offset_x,
            "CRPIX2": 5.0 - offset_y,
            "CDELT1": -0.002,
            "CDELT2": 0.002,
            "BUNIT": "MJy/sr",
            "FILTER": "L",
        }
    )


def reference_pixels() -> NDArray[np.float32]:
    expected = np.full(SHAPE, np.nan, dtype=np.float32)
    for y, x in np.ndindex(SHAPE):
        left = 1 <= x <= 8 and 1 <= y <= 6 and (x, y) not in {(3, 3), (7, 3), (8, 5)}
        right = 6 <= x <= 12 and 2 <= y <= 6 and (x, y) not in {(6, 4), (8, 5), (11, 6)}
        baseline = x + 2 * y - 8
        if left and right:
            expected[y, x] = baseline + 2.625
        elif left:
            expected[y, x] = baseline
        elif right:
            expected[y, x] = baseline + 3.5
    return expected


def tan_world(east_degrees: float, north_degrees: float) -> tuple[float, float]:
    """Analytic inverse Gnomonic projection in the reference field."""
    east, north, dec = map(radians, (east_degrees, north_degrees, CENTER[1]))
    radial = cos(dec) - north * sin(dec)
    ra = (CENTER[0] + degrees(atan2(east, radial))) % 360.0
    return ra, degrees(atan2(sin(dec) + north * cos(dec), hypot(radial, east)))
