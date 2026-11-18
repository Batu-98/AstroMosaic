"""Measure independent, unique source-to-catalog associations and residuals."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import isfinite

import numpy as np
from astropy.coordinates import SkyCoord
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from astromosaic.astrometry.astap_catalog import CatalogStar
from astromosaic.core.job import JobContext
from astromosaic.geometry import PanelGeometry

MIN_MATCHES = 15
MATCH_RADIUS = 3.0
REGION_MIN_MATCHES = 5
MODEL_GRID = 9
FloatArray = NDArray[np.float64]
CatalogQuery = Callable[[tuple[float, float], float, int], Sequence[CatalogStar]]


class QualityRejected(ValueError):
    """A localized candidate lacks sufficient astrometric evidence."""

    def __init__(self, detail: str, evidence: dict[str, object] | None = None) -> None:
        super().__init__(detail)
        self.evidence = evidence


@dataclass(frozen=True, slots=True)
class Associations:
    xy: FloatArray
    sky: SkyCoord
    chance_matches: int
    catalog_candidates: int


def _cone(
    geometry: PanelGeometry, rect: tuple[float, float, float, float]
) -> tuple[tuple[float, float], float]:
    left, top, right, bottom = rect
    x, y = np.meshgrid(np.linspace(left, right, 3), np.linspace(top, bottom, 3))
    sky = geometry.forward(x.ravel(), y.ravel()).icrs
    center = sky[4]
    return (float(center.ra.deg), float(center.dec.deg)), float(np.max(center.separation(sky).deg))


def associate(
    geometry: PanelGeometry,
    size: tuple[int, int],
    xy: FloatArray,
    query: CatalogQuery,
    context: JobContext,
) -> Associations:
    """Find mutual nearest stars, with shifted controls for coincidental matches."""
    if len(xy) < MIN_MATCHES or not np.all(np.isfinite(xy)):
        raise QualityRejected(f"Fewer than {MIN_MATCHES} usable measured sky stars.")
    width, height = size
    _, radius = _cone(geometry, (0, 0, width - 1, height - 1))
    # Avoid one large query for a very wide field. Controls share the same queries.
    div = MODEL_GRID if radius > 3 else 1
    measured_tree = cKDTree(xy)
    shifts = np.array([[13.1, 0], [-13.1, 0], [0, 13.1], [0, -13.1]])
    control_counts = np.zeros(len(shifts), dtype=np.int64)
    matches: list[tuple[float, int, CatalogStar]] = []
    candidates = 0
    for row in range(div):
        for col in range(div):
            context.check_cancelled()
            left, right = width * col / div, width * (col + 1) / div
            top, bottom = height * row / div, height * (row + 1) / div
            indexes = np.flatnonzero(
                (xy[:, 0] >= left) & (xy[:, 0] < right) & (xy[:, 1] >= top) & (xy[:, 1] < bottom)
            )
            if not len(indexes):
                continue
            pad = float(np.max(np.abs(shifts))) + MATCH_RADIUS
            rect = (
                max(0, left - pad),
                max(0, top - pad),
                min(width - 1, right + pad),
                min(height - 1, bottom + pad),
            )
            center, cell_radius = _cone(geometry, rect)
            radius_deg = cell_radius + 0.015
            if not 0 < radius_deg <= 10:
                raise QualityRejected(
                    "The candidate exceeds the supported local catalog query domain."
                )
            stars = query(center, radius_deg, max(256, 6 * len(indexes)))
            context.check_cancelled()
            if not stars:
                continue
            ra_dec = np.array([(star.ra_deg, star.dec_deg) for star in stars], dtype=np.float64)
            sky = SkyCoord(ra_dec[:, 0], ra_dec[:, 1], unit="deg", frame="icrs")
            projected = geometry.inverse(sky)
            keep = np.flatnonzero(
                np.all(np.isfinite(projected), axis=1)
                & (projected[:, 0] >= left - pad)
                & (projected[:, 0] < right + pad)
                & (projected[:, 1] >= top - pad)
                & (projected[:, 1] < bottom + pad)
            )
            if div > 1:
                keep = np.array(
                    sorted(keep, key=lambda i: stars[int(i)].magnitude)[
                        : max(30, 3 * len(indexes))
                    ],
                    dtype=np.intp,
                )
            if not len(keep):
                continue
            candidates += len(keep)
            local_xy = projected[keep]
            tree = cKDTree(local_xy)
            distance, nearest = tree.query(xy[indexes], k=1)
            _, reverse = measured_tree.query(local_xy, k=1)
            bound = (distance <= MATCH_RADIUS) & (reverse[nearest] == indexes)
            matches.extend(
                (float(d), int(index), stars[int(cat)])
                for d, index, cat in zip(
                    distance[bound], indexes[bound], keep[nearest[bound]], strict=True
                )
            )
            for i, shift in enumerate(shifts):
                shifted, _ = tree.query(xy[indexes] + shift, k=1)
                control_counts[i] += np.count_nonzero(shifted <= MATCH_RADIUS)
    if not matches:
        raise QualityRejected("No mutual local catalog associations within three source pixels.")

    distances = np.array([match[0] for match in matches])
    median = float(np.median(distances))
    mad = float(np.median(np.abs(distances - median)))
    cutoff = min(MATCH_RADIUS, max(0.75, median + 4 * 1.4826 * mad))
    selected: list[tuple[int, CatalogStar]] = []
    used_sources: set[int] = set()
    used_catalog: set[str] = set()
    used_coordinates: set[tuple[float, float]] = set()
    for distance, index, star in sorted(matches, key=lambda match: (match[0], match[1])):
        if distance > cutoff:
            break
        coords = star.ra_deg, star.dec_deg
        if index in used_sources or star.identifier in used_catalog or coords in used_coordinates:
            continue
        used_sources.add(index)
        used_catalog.add(star.identifier)
        used_coordinates.add(coords)
        selected.append((index, star))
    chance = int(control_counts.max())
    if len(selected) < MIN_MATCHES or len(selected) < 4 * (chance + 1):
        raise QualityRejected(
            f"Only {len(selected)} unique catalog associations after rejection; "
            f"the shifted control found up to {chance}.",
            {"unique_matches": len(selected), "chance_control_matches": chance},
        )
    coords_array = np.array([(star.ra_deg, star.dec_deg) for _, star in selected], dtype=np.float64)
    return Associations(
        xy[[i for i, _ in selected]],
        SkyCoord(coords_array[:, 0], coords_array[:, 1], unit="deg", frame="icrs"),
        chance,
        candidates,
    )


def residuals(
    geometry: PanelGeometry, xy: FloatArray, sky: SkyCoord
) -> tuple[FloatArray, FloatArray]:
    angular = np.asarray(geometry.forward(*xy.T).separation(sky).arcsec, dtype=np.float64)
    pixels = np.linalg.norm(geometry.inverse(sky) - xy, axis=1)
    if not np.all(np.isfinite(angular)) or not np.all(np.isfinite(pixels)):
        raise QualityRejected("The candidate has nonfinite astrometric residuals.")
    return angular, pixels


def rms(values: FloatArray) -> float:
    return float(np.sqrt(np.mean(values**2)))


def p95(values: FloatArray) -> float:
    return float(np.percentile(values, 95))


def require_quality(count: int, rms_arcsec: float, scales: tuple[float, float]) -> float:
    if count < MIN_MATCHES or not all(isfinite(s) and s > 0 for s in scales):
        raise QualityRejected(
            f"At least {MIN_MATCHES} unique matches and valid solved scales are required."
        )
    ceiling = max(3.0, 2.0 * min(scales))
    if not isfinite(rms_arcsec) or not 0 <= rms_arcsec <= ceiling:
        raise QualityRejected(
            f"Catalog RMS {rms_arcsec:.3g} arcsec exceeds the {ceiling:.3g} arcsec limit.",
            {
                "unique_matches": count,
                "rms_arcsec": rms_arcsec if isfinite(rms_arcsec) else None,
                "rms_limit_arcsec": ceiling,
            },
        )
    return ceiling


def cells(xy: FloatArray, size: tuple[int, int], count: int) -> NDArray[np.intp]:
    indexes = np.clip((xy / size * count).astype(np.intp), 0, count - 1)
    return indexes[:, 0] + count * indexes[:, 1]


def outer_stars(xy: FloatArray, size: tuple[int, int]) -> NDArray[np.bool_]:
    frac = (xy + 0.5) / size
    return np.any((frac < 0.2) | (frac > 0.8), axis=1)


def regional_metrics(
    xy: FloatArray,
    size: tuple[int, int],
    angular: FloatArray,
    pixels: FloatArray,
    held_out: NDArray[np.intp],
) -> list[dict[str, object]]:
    indexes = cells(xy, size, MODEL_GRID)
    reports: list[dict[str, object]] = []
    for index in range(MODEL_GRID**2):
        active = indexes == index
        count = int(np.count_nonzero(active))
        hold = held_out[indexes[held_out] == index]
        supported = count >= REGION_MIN_MATCHES
        reports.append(
            {
                "row": index // MODEL_GRID,
                "column": index % MODEL_GRID,
                "matches": count,
                "support": "measured" if supported else "insufficient",
                "rms_arcsec": rms(angular[active]) if supported else None,
                "p95_arcsec": p95(angular[active]) if supported else None,
                "max_arcsec": float(np.max(angular[active])) if supported else None,
                "rms_source_px": rms(pixels[active]) if supported else None,
                "p95_source_px": p95(pixels[active]) if supported else None,
                "max_source_px": float(np.max(pixels[active])) if supported else None,
                "held_out_matches": len(hold),
                "held_out_p95_source_px": p95(pixels[hold])
                if len(hold) >= REGION_MIN_MATCHES
                else None,
            }
        )
    return reports
