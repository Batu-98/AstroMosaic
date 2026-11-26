"""Check SDSS sky restoration at fractional detector coordinates."""

import numpy as np
from astropy.coordinates import ICRS

from astromosaic.geometry import PanelGeometry, TileSky
from astromosaic.pipeline.mosaic import RenderSpec
from tools.phase8d_sdss_sky import Band


def test_sky_is_calibrated_on_detector_before_resampling() -> None:
    geometry = PanelGeometry(RenderSpec((0, 0), (3, 3), 1).output_wcs(), ICRS())
    band = Band(
        np.array([[6, 10, 14], [10, 14, 18], [14, 18, 22]], np.float32),
        np.array([[4, 12], [8, 16]], np.float32),
        np.array([-0.5, 0.5, 1.5], np.float32),
        np.array([0, 1, 2], np.float32),
        np.array([2, 4, 6], np.float32),
        geometry,
    )
    sky = TileSky.from_pixels(geometry, np.array([0.5, 1.5, 4]), np.array([0.5, 1.5, 1]))
    calibrated, background = band.sample(sky)
    np.testing.assert_allclose(calibrated, [10, 18, np.nan], atol=1e-8)
    # Columns 0 and 2 clamp to their nearest archived sky column. The calibrated
    # first-cell corners are 8, 32, 16, 48, giving 26 at its center.
    np.testing.assert_allclose(background, [26, 72, np.nan], atol=1e-8)
