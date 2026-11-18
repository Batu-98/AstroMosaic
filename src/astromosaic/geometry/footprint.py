"""Conservative pixel bounds for selecting panels before mapping a tile."""

from dataclasses import dataclass

import numpy as np
from astropy.coordinates import ICRS, SkyCoord
from numpy.typing import NDArray

from astromosaic.core import Region
from astromosaic.geometry import ROUND_TRIP_TOLERANCE, PanelGeometry

# Restrict corner projection to a well-conditioned part of the TAN hemisphere.
_MAX_TAN_DISTANCE_DEG = 80.0
_MIN_TARGET_SCALE_DEG = 1e-8
MAX_FOOTPRINT_COORDINATE = 2**32
_TAN_AXES = ("RA---TAN", "DEC--TAN")
_PLAIN_TAN_CARDS = frozenset(
    {
        "WCSAXES",
        "WCSNAME",
        "CTYPE1",
        "CTYPE2",
        "CUNIT1",
        "CUNIT2",
        "CRPIX1",
        "CRPIX2",
        "CRVAL1",
        "CRVAL2",
        "CDELT1",
        "CDELT2",
        "PC1_1",
        "PC1_2",
        "PC2_1",
        "PC2_2",
        "CD1_1",
        "CD1_2",
        "CD2_1",
        "CD2_2",
        "LONPOLE",
        "LATPOLE",
        "RADESYS",
        "EQUINOX",
        "CNAME1",
        "CNAME2",
        "CRDER1",
        "CRDER2",
        "CSYER1",
        "CSYER2",
        "MJDREF",
        "MJDREFI",
        "MJDREFF",
        "DATE-OBS",
        "MJD-OBS",
        "DATE-AVG",
        "MJD-AVG",
        "DATE-BEG",
        "MJD-BEG",
        "DATE-END",
        "MJD-END",
        "OBSGEO-X",
        "OBSGEO-Y",
        "OBSGEO-Z",
    }
)


@dataclass(frozen=True, slots=True)
class PixelBounds:
    left: float
    top: float
    right: float
    bottom: float

    def intersects(self, other: "PixelBounds") -> bool:
        return (
            self.left <= other.right
            and other.left <= self.right
            and self.top <= other.bottom
            and other.top <= self.bottom
        )

    def corners(self) -> NDArray[np.float64]:
        return np.array(
            [
                [self.left, self.top],
                [self.right, self.top],
                [self.left, self.bottom],
                [self.right, self.bottom],
            ],
            dtype=np.float64,
        )


def raster_bounds(
    region: Region,
    scale: tuple[float, float] = (1.0, 1.0),
    origin: tuple[float, float] = (0.0, 0.0),
) -> PixelBounds:
    """Enclose the sample centers produced by raster_pixels, including preview tiles."""
    sx, sy = scale
    ox, oy = origin
    return PixelBounds(
        region.x * sx - 0.5 + ox,
        region.y * sy - 0.5 + oy,
        (region.x + region.width) * sx - 0.5 + ox,
        (region.y + region.height) * sy - 0.5 + oy,
    )


def enclosing_bounds(points: NDArray[np.float64]) -> PixelBounds | None:
    if not np.isfinite(points).all() or np.max(np.abs(points)) > MAX_FOOTPRINT_COORDINATE:
        return None
    left, top = points.min(axis=0)
    right, bottom = points.max(axis=0)
    # Cover the round trip tolerance and conservative floating-point error at the edges.
    return PixelBounds(float(left) - 1, float(top) - 1, float(right) + 1, float(bottom) + 1)


def _simple_icrs_tan(geometry: PanelGeometry) -> bool:
    wcs = geometry.wcs
    if (
        not isinstance(geometry.frame, ICRS)
        or wcs.has_distortion
        or tuple(wcs.wcs.ctype) != _TAN_AXES
        or tuple(map(str, wcs.wcs.cunit)) != ("deg", "deg")
        or not np.all(np.abs(wcs.wcs.crpix) <= MAX_FOOTPRINT_COORDINATE)
    ):
        return False
    # WCSLIB can normalize TPV to TAN internally while retaining its polynomial.
    # Serialization exposes the actual projection and any extra distortion cards.
    try:
        header = wcs.to_header(relax=True)
    except (ValueError, RuntimeError):
        return False
    return (header.get("CTYPE1"), header.get("CTYPE2")) == _TAN_AXES and (
        _PLAIN_TAN_CARDS.issuperset(header)
    )


def _within_tan_domain(sky: SkyCoord, geometry: PanelGeometry) -> bool:
    center = SkyCoord(*geometry.wcs.wcs.crval, unit="deg", frame=geometry.frame)
    return bool(np.all(sky.separation(center).deg < _MAX_TAN_DISTANCE_DEG))


def tan_footprint(
    source: PanelGeometry,
    target: PanelGeometry,
    source_size: tuple[int, int],
    target_size: tuple[int, int],
    shift: tuple[float, float],
) -> PixelBounds | None:
    """Bound a plain ICRS TAN panel in the cropped output pixel grid.

    Between tangent planes, each projected coordinate is a ratio of linear
    functions. With a positive denominator at all four corners, its extrema
    on the rectangle occur at the corners. Other projections keep the full path.
    """
    if (
        not _simple_icrs_tan(source)
        or not _simple_icrs_tan(target)
        or min(abs(target.wcs.wcs.cdelt)) < _MIN_TARGET_SCALE_DEG
        or max(*source_size, *target_size, *map(abs, shift)) > MAX_FOOTPRINT_COORDINATE
        or not np.isfinite(shift).all()
    ):
        return None

    source_edges = raster_bounds(Region(0, 0, *source_size))
    # Extend the source rectangle beyond the resampler's edge snap tolerance.
    source_corners = (
        source_edges.corners()
        + np.array([[-1, -1], [1, -1], [-1, 1], [1, 1]], dtype=np.float64) * ROUND_TRIP_TOLERANCE
    )
    target_corners = raster_bounds(Region(0, 0, *target_size)).corners() - shift
    try:
        source_sky = source.forward(*source_corners.T)
        if not _within_tan_domain(source_sky, target):
            return None
        if not _within_tan_domain(target.forward(*target_corners.T), source):
            return None
        points = target.inverse(source_sky)
    except (ValueError, ArithmeticError):
        # Keep the full mapper when the auxiliary corner projection is unusable.
        return None
    if np.max(np.abs(points)) > MAX_FOOTPRINT_COORDINATE:
        return None
    return enclosing_bounds(points + shift)
