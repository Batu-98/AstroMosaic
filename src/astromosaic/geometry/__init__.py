"""Celestial geometry for the CPU FITS reference renderer."""

from dataclasses import dataclass
from math import cos, isfinite, radians, sin
from typing import Self, cast

import numpy as np
from astropy.coordinates import BaseCoordinateFrame, SkyCoord
from astropy.io import fits
from astropy.wcs import WCS, NoConvergence
from astropy.wcs.utils import wcs_to_celestial_frame
from numpy.typing import NDArray

from astromosaic.core import Region

ROUND_TRIP_TOLERANCE = 1e-4  # pixels
_INVERSE_TOLERANCE = 1e-8  # pixels


def tan_output_wcs(
    center: tuple[float, float],
    size: tuple[int, int],
    scale_arcsec: float,
    rotation_deg: float,
    crop: Region,
) -> WCS:
    ra, dec = center
    scale = scale_arcsec / 3600
    if not (isfinite(ra) and -90 <= dec <= 90 and isfinite(scale) and scale > 0):
        raise ValueError("Expected a finite ICRS center and a positive pixel scale.")
    if not isfinite(rotation_deg):
        raise ValueError("The output rotation must be finite.")

    width, height = size
    angle = radians(rotation_deg % 360)
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.radesys = "ICRS"
    wcs.wcs.crval = [ra % 360, dec]
    wcs.wcs.crpix = [(width + 1) / 2 - crop.x, (height + 1) / 2 - crop.y]
    wcs.wcs.cdelt = [-scale, scale]
    wcs.wcs.pc = [[cos(angle), -sin(angle)], [sin(angle), cos(angle)]]
    wcs.wcs.set()
    return wcs


@dataclass(frozen=True, slots=True)
class PanelGeometry:
    wcs: WCS
    frame: BaseCoordinateFrame

    def forward(self, x: NDArray[np.float64], y: NDArray[np.float64]) -> SkyCoord:
        world = self.wcs.all_pix2world(x, y, 0)
        return SkyCoord(
            world[self.wcs.wcs.lng], world[self.wcs.wcs.lat], unit="deg", frame=self.frame
        )

    def inverse(self, sky: SkyCoord) -> NDArray[np.float64]:
        """Return pixel coordinates, marking failed SIP inversions as NaN."""
        sphere = sky.transform_to(self.frame).spherical
        world = np.empty((sky.size, 2), dtype=np.float64)
        world[:, self.wcs.wcs.lng] = sphere.lon.deg
        world[:, self.wcs.wcs.lat] = sphere.lat.deg
        try:
            pixels = self.wcs.all_world2pix(world, 0, tolerance=_INVERSE_TOLERANCE)
        except NoConvergence as error:
            pixels = error.best_solution
            if error.divergent is not None:
                pixels[error.divergent] = np.nan
            if error.slow_conv is not None:
                pixels[error.slow_conv] = np.nan
        return cast(NDArray[np.float64], pixels)


def read_panel_geometry(header: fits.Header, width: int, height: int) -> PanelGeometry:
    keywords = ("CTYPE1", "CTYPE2", "CRPIX1", "CRPIX2", "CRVAL1", "CRVAL2")
    has_scale = ("CDELT1" in header and "CDELT2" in header) or any(
        f"CD{i}_{j}" in header for i in (1, 2) for j in (1, 2)
    )
    if not has_scale or not all(key in header for key in keywords):
        raise ValueError("Expected an existing celestial WCS with explicit pointing and scale.")

    wcs = WCS(header)
    if wcs.pixel_n_dim != 2 or wcs.world_n_dim != 2 or not wcs.is_celestial:
        raise ValueError("Expected a two-dimensional celestial WCS.")
    geometry = PanelGeometry(wcs, wcs_to_celestial_frame(wcs))
    center = np.array([[(width - 1) / 2, (height - 1) / 2]], dtype=np.float64)
    sky = geometry.forward(*center.T)
    if not np.allclose(geometry.inverse(sky), center, rtol=0, atol=ROUND_TRIP_TOLERANCE):
        raise ValueError("The celestial WCS does not round-trip at the panel center.")
    return geometry


@dataclass(frozen=True, slots=True)
class TileSky:
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    sky: SkyCoord
    geometry: PanelGeometry

    @classmethod
    def from_output(cls, output: PanelGeometry, region: Region) -> Self:
        y, x = np.indices((region.height, region.width), dtype=np.float64)
        return cls.from_pixels(output, x.ravel() + region.x, y.ravel() + region.y)

    @classmethod
    def from_pixels(
        cls, output: PanelGeometry, x: NDArray[np.float64], y: NDArray[np.float64]
    ) -> Self:
        return cls(x, y, output.forward(x, y), output)

    def in_panel(
        self, geometry: PanelGeometry, shift: tuple[float, float] = (0.0, 0.0)
    ) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]]:
        dx, dy = shift
        sky = self.sky if shift == (0.0, 0.0) else self.geometry.forward(self.x - dx, self.y - dy)
        source_x, source_y = geometry.inverse(sky).T
        sky_back = geometry.forward(source_x, source_y)
        check_x, check_y = self.geometry.inverse(sky_back).T
        usable = (
            np.isfinite(source_x)
            & np.isfinite(source_y)
            & (np.abs(check_x + dx - self.x) <= ROUND_TRIP_TOLERANCE)
            & (np.abs(check_y + dy - self.y) <= ROUND_TRIP_TOLERANCE)
        )
        return source_x, source_y, usable
