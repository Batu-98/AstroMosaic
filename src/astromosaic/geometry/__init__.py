"""Celestial geometry for the CPU FITS reference renderer."""

from dataclasses import dataclass
from math import cos, isfinite, radians, sin
from typing import Literal, Self, cast

import numpy as np
from astropy.coordinates import BaseCoordinateFrame, SkyCoord
from astropy.io import fits
from astropy.wcs import WCS, NoConvergence
from astropy.wcs.utils import wcs_to_celestial_frame
from numpy.typing import NDArray

from astromosaic.core import Region

ROUND_TRIP_TOLERANCE = 1e-4  # pixels
_INVERSE_TOLERANCE = 1e-8  # pixels
# FITS header rounding can move a nominal rim point slightly inside the ZEA disk.
_ZEA_MIN_NATIVE_LATITUDE = -90.0 + 1e-4  # degrees
SkyProjection = Literal["TAN", "ZEA"]


def raster_pixels(
    region: Region, scale: tuple[float, float], origin: tuple[int, int] = (0, 0)
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    y, x = np.indices((region.height, region.width), dtype=np.float64)
    # Map raster centers into the output's zero-based, pixel-edge rectangle.
    return (
        (x.ravel() + region.x + 0.5) * scale[0] - 0.5 + origin[0],
        (y.ravel() + region.y + 0.5) * scale[1] - 0.5 + origin[1],
    )


def sky_output_wcs(
    center: tuple[float, float],
    size: tuple[int, int],
    scale_arcsec: float,
    rotation_deg: float,
    crop: Region,
    *,
    projection: SkyProjection,
) -> WCS:
    if projection not in ("TAN", "ZEA"):
        raise ValueError("Expected TAN or ZEA for the sky projection.")
    ra, dec = center
    scale = scale_arcsec / 3600
    if not (isfinite(ra) and -90 <= dec <= 90 and isfinite(scale) and scale > 0):
        raise ValueError("Expected a finite ICRS center and a positive pixel scale.")
    if not isfinite(rotation_deg):
        raise ValueError("The output rotation must be finite.")

    width, height = size
    angle = radians(rotation_deg % 360)
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = [f"RA---{projection}", f"DEC--{projection}"]
    wcs.wcs.radesys = "ICRS"
    wcs.wcs.crval = [ra % 360, dec]
    wcs.wcs.crpix = [(width + 1) / 2 - crop.x, (height + 1) / 2 - crop.y]
    wcs.wcs.cdelt = [-scale, scale]
    wcs.wcs.pc = [[cos(angle), -sin(angle)], [sin(angle), cos(angle)]]
    wcs.wcs.set()
    return wcs


def tan_output_wcs(
    center: tuple[float, float],
    size: tuple[int, int],
    scale_arcsec: float,
    rotation_deg: float,
    crop: Region,
) -> WCS:
    return sky_output_wcs(center, size, scale_arcsec, rotation_deg, crop, projection="TAN")


@dataclass(frozen=True, slots=True)
class PanelGeometry:
    wcs: WCS
    frame: BaseCoordinateFrame

    @property
    def _plain_zea(self) -> bool:
        return bool(
            self.wcs.wcs.ctype[self.wcs.wcs.lng][5:] == "ZEA" and not self.wcs.has_distortion
        )

    def forward(self, x: NDArray[np.float64], y: NDArray[np.float64]) -> SkyCoord:
        if self._plain_zea:
            xy = np.stack(np.broadcast_arrays(x, y), axis=-1)
            result = self.wcs.wcs.p2s(xy.reshape(-1, 2), 0)
            usable = (result["stat"] == 0) & (result["theta"] > _ZEA_MIN_NATIVE_LATITUDE)
            result["world"][~usable] = np.nan
            world = result["world"].T.reshape((2, *xy.shape[:-1]))
        else:
            world = self.wcs.all_pix2world(x, y, 0)
        return SkyCoord(
            world[self.wcs.wcs.lng], world[self.wcs.wcs.lat], unit="deg", frame=self.frame
        )

    def inverse(self, sky: SkyCoord) -> NDArray[np.float64]:
        """Return pixel coordinates with NaN for failed or singular inversions."""
        sphere = sky.transform_to(self.frame).spherical
        world = np.empty((sky.size, 2), dtype=np.float64)
        world[:, self.wcs.wcs.lng] = sphere.lon.deg
        world[:, self.wcs.wcs.lat] = sphere.lat.deg
        if self._plain_zea:
            result = self.wcs.wcs.s2p(world, 0)
            usable = (result["stat"] == 0) & (result["theta"] > _ZEA_MIN_NATIVE_LATITUDE)
            pixels = result["pixcrd"]
            pixels[~usable] = np.nan
            return cast(NDArray[np.float64], pixels)
        pixels = cast(NDArray[np.float64], self.wcs.wcs_world2pix(world, 0))
        if not self.wcs.has_distortion:
            return pixels
        # SIP and lookup-table iteration need a finite seed from the core projection.
        # An entirely unprojectable batch would otherwise enter an all-NaN reduction.
        usable = np.isfinite(pixels).all(axis=1)
        if usable.all():
            return self._inverse_distortion(world)
        pixels[~usable] = np.nan
        if usable.any():
            pixels[usable] = self._inverse_distortion(world[usable])
        return pixels

    def _inverse_distortion(self, world: NDArray[np.float64]) -> NDArray[np.float64]:
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
    points = np.array([[(width - 1) / 2, (height - 1) / 2]], dtype=np.float64)
    if geometry._plain_zea:
        # A crop can contain valid pixels even when its center is outside the disk.
        inside = np.clip(wcs.wcs.crpix - 1, (0, 0), (width - 1, height - 1))
        points = np.vstack((points, inside))
    sky = geometry.forward(*points.T)
    matches = np.isclose(geometry.inverse(sky), points, rtol=0, atol=ROUND_TRIP_TOLERANCE)
    if not matches.all(axis=1).any():
        if geometry._plain_zea:
            raise ValueError("The ZEA WCS does not round-trip at an in-frame reference position.")
        raise ValueError("The celestial WCS does not round-trip at the panel center.")
    return geometry


@dataclass(frozen=True, slots=True)
class TileSky:
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    sky: SkyCoord
    geometry: PanelGeometry

    @classmethod
    def from_output(
        cls, output: PanelGeometry, region: Region, scale: tuple[float, float] = (1.0, 1.0)
    ) -> Self:
        return cls.from_pixels(output, *raster_pixels(region, scale))

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
        if shift != (0.0, 0.0) and self.geometry._plain_zea:
            # A fitted sample shift must not fill invalid output coordinates.
            usable &= np.isfinite(self.sky.spherical.lat.deg)
        return source_x, source_y, usable
