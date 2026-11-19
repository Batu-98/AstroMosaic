"""Conservative pixel bounds for selecting panels before mapping a tile."""

from dataclasses import dataclass
from re import fullmatch

import numpy as np
from astropy.coordinates import ICRS, SkyCoord
from numpy.typing import NDArray

from astromosaic.core import Region
from astromosaic.geometry import ROUND_TRIP_TOLERANCE, PanelGeometry

# Restrict corner projection to a well-conditioned part of the TAN hemisphere.
_MAX_TAN_DISTANCE_DEG = 80.0
_MAX_ZEA_DISTANCE_DEG = 150.0
_MIN_TARGET_SCALE_DEG = 1e-8
MAX_FOOTPRINT_COORDINATE = 2**32
_TAN_AXES = ("RA---TAN", "DEC--TAN")
_TAN_SIP_AXES = ("RA---TAN-SIP", "DEC--TAN-SIP")
_ZEA_AXES = ("RA---ZEA", "DEC--ZEA")
_STANDARD_SKY_CARDS = frozenset(
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


def _simple_icrs_projection(geometry: PanelGeometry, axes: tuple[str, str]) -> bool:
    wcs = geometry.wcs
    if (
        not isinstance(geometry.frame, ICRS)
        or tuple(wcs.wcs.ctype) != axes
        or tuple(map(str, wcs.wcs.cunit)) != ("deg", "deg")
        or not np.all(np.abs(wcs.wcs.crpix) <= MAX_FOOTPRINT_COORDINATE)
    ):
        return False
    sip_only = axes == _TAN_SIP_AXES
    if sip_only:
        if wcs.sip is None or any(
            item is not None for item in (wcs.cpdis1, wcs.cpdis2, wcs.det2im1, wcs.det2im2)
        ):
            return False
    elif wcs.has_distortion:
        return False
    # WCSLIB can normalize TPV to TAN internally while retaining its polynomial.
    # Serialization exposes the actual projection and any extra distortion cards.
    try:
        header = wcs.to_header(relax=True)
    except (ValueError, RuntimeError):
        return False
    return (header.get("CTYPE1"), header.get("CTYPE2")) == axes and all(
        key in _STANDARD_SKY_CARDS
        or (sip_only and fullmatch(r"(?:A|B|AP|BP)_(?:ORDER|[0-9]+_[0-9]+)", key))
        for key in header
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
        not _simple_icrs_projection(source, _TAN_AXES)
        or not _simple_icrs_projection(target, _TAN_AXES)
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


def _sip_padding(
    source: PanelGeometry, lower: NDArray[np.float64], upper: NDArray[np.float64]
) -> NDArray[np.float64] | None:
    sip = source.wcs.sip
    if sip is None:
        return np.zeros(2, dtype=np.float64)
    offsets = np.maximum(np.abs(lower + 1 - sip.crpix), np.abs(upper + 1 - sip.crpix))
    if max(sip.a_order, sip.b_order) > 5 or not np.all(offsets <= MAX_FOOTPRINT_COORDINATE):
        return None
    # Bound each forward SIP displacement by the sum of its absolute terms.
    padding = []
    for polynomial in (sip.a, sip.b):
        coefficients = np.abs(polynomial)
        if not np.all(coefficients <= MAX_FOOTPRINT_COORDINATE):
            return None
        x_power, y_power = np.indices(coefficients.shape)
        padding.append(np.sum(coefficients * offsets[0] ** x_power * offsets[1] ** y_power))
    return np.array(padding, dtype=np.float64)


def zea_footprint(
    source: PanelGeometry,
    target: PanelGeometry,
    source_size: tuple[int, int],
    target_size: tuple[int, int],
    shift: tuple[float, float],
) -> PixelBounds | None:
    """Enclose TAN or TAN-SIP support in a ZEA output, including curved edges."""
    axes = _TAN_SIP_AXES if source.wcs.sip is not None else _TAN_AXES
    if (
        not _simple_icrs_projection(source, axes)
        or not _simple_icrs_projection(target, _ZEA_AXES)
        or max(*source_size, *target_size, *map(abs, shift)) > MAX_FOOTPRINT_COORDINATE
        or not np.isfinite(shift).all()
    ):
        return None

    lower, upper = raster_bounds(Region(0, 0, *source_size)).corners()[[0, 3]]
    lower -= ROUND_TRIP_TOLERANCE
    upper += ROUND_TRIP_TOLERANCE
    padding = _sip_padding(source, lower, upper)
    if padding is None or np.any(padding > MAX_FOOTPRINT_COORDINATE):
        return None

    # Subdivide the corrected detector rectangle. The normalized gnomonic ray has
    # angular derivative at most one, so the plane radius bounds each sky cap.
    step = (upper - lower + 2 * padding) / 4
    centers = lower - padding + (np.indices((4, 4)).reshape(2, -1).T + 0.5) * step
    half_x, half_y = step / 2
    offsets = PixelBounds(-half_x, -half_y, half_x, half_y).corners()
    source_matrix = source.wcs.pixel_scale_matrix
    if not np.all(np.abs(source_matrix) <= _MAX_ZEA_DISTANCE_DEG):
        return None
    radius = np.hypot(*(offsets @ source_matrix.T).T).max()
    if not 0 < radius < _MAX_ZEA_DISTANCE_DEG:
        return None

    try:
        scale = np.linalg.svd(target.wcs.pixel_scale_matrix, compute_uv=False).min()
        sky = SkyCoord(*source.wcs.wcs_pix2world(centers, 0).T, unit="deg", frame=source.frame)
        pole = SkyCoord(*target.wcs.wcs.crval, unit="deg", frame=target.frame)
        distance = sky.separation(pole).deg + radius
        if not (scale >= _MIN_TARGET_SCALE_DEG and np.all(distance < _MAX_ZEA_DISTANCE_DEG)):
            return None
        # Along any cap radius, the maximum ZEA scale is sec(distance / 2).
        spread = radius / (scale * np.cos(np.deg2rad(distance / 2)))
        points = target.inverse(sky) + shift
    except (ValueError, ArithmeticError, np.linalg.LinAlgError):
        return None
    return enclosing_bounds(np.vstack((points - spread[:, None], points + spread[:, None])))
