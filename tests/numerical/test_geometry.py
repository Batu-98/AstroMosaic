from math import atan2, cos, degrees, hypot, pi, radians, sin
from pathlib import Path

import numpy as np
from astropy.wcs import WCS
from reproject import reproject_interp

from astromosaic.io.fits import open_fits_panel
from astromosaic.pipeline.smoke import write_smoke_panel


def test_gnomonic_coordinate_origin_and_ra_wrap(tmp_path: Path) -> None:
    path = tmp_path / "panel.fits"
    write_smoke_panel(path)
    with open_fits_panel(path) as panel:
        wcs = WCS(panel.header).celestial

    # Decreasing x by one pixel crosses RA zero east of the tangent point.
    plane_x = radians(0.002)
    declination = radians(20.0)
    expected_ra = (359.999 + degrees(atan2(plane_x, cos(declination)))) % 360.0
    expected_dec = degrees(atan2(sin(declination), hypot(cos(declination), plane_x)))
    sky = wcs.pixel_to_world_values(3.0, 3.0)
    assert 0.0 <= float(sky[0]) < 0.01
    np.testing.assert_allclose(sky, (expected_ra, expected_dec), atol=1e-9, rtol=0)
    np.testing.assert_allclose(wcs.world_to_pixel_values(*sky), (3.0, 3.0), atol=1e-8, rtol=0)


def _test_wcs(center: int, arcsec: float) -> WCS:
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [359.999, 20.0]
    wcs.wcs.crpix = [center, center]
    wcs.wcs.cdelt = [-arcsec / 3600, arcsec / 3600]
    return wcs


def test_surface_brightness_and_solid_angle_at_half_pixel_scale() -> None:
    source_wcs = _test_wcs(17, 2.0)
    output_wcs = _test_wcs(33, 1.0)
    field, coverage = reproject_interp((np.full((33, 33), 7.0), source_wcs), output_wcs, (65, 65))
    np.testing.assert_allclose(field, 7.0, rtol=0, atol=1e-10)
    np.testing.assert_array_equal(coverage, 1.0)

    y, x = np.indices((33, 33), dtype=np.float64) - 16
    star = 5 * np.exp(-(x**2 + y**2) / (2 * 3**2))
    output, _ = reproject_interp((star, source_wcs), output_wcs, (65, 65))
    step = radians(1.0 / 3600)
    y, x = (np.indices((65, 65), dtype=np.float64) - 32) * step
    # Integrate brightness using the TAN solid-angle Jacobian at each pixel center.
    solid_angle = step**2 / (1 + x**2 + y**2) ** 1.5
    flux = np.sum(output * solid_angle)
    expected_flux = 5 * 2 * pi * (6 * step) ** 2
    np.testing.assert_allclose(flux, expected_flux, rtol=0.01, atol=0.0)
