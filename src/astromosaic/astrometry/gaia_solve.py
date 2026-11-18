"""Bound the optional Seiza search and query its local catalog for validation."""

from dataclasses import dataclass
from functools import partial
from importlib.metadata import version
from math import isfinite
from pathlib import Path
from time import monotonic

import numpy as np
from astropy.io import fits

from astromosaic.astrometry.astap_catalog import CatalogStar
from astromosaic.astrometry.distortion import validate_models
from astromosaic.astrometry.solve_validation import MIN_MATCHES, QualityRejected, associate
from astromosaic.astrometry.solver_worker import run_solver_worker
from astromosaic.core.job import JobContext
from astromosaic.geometry import read_panel_geometry

GAIA_BROAD_SCALES = (0.1, 120.0)


@dataclass(frozen=True, slots=True)
class GaiaCandidate:
    header: str
    version: str
    catalog: str
    matched_stars: int
    rms_arcsec: float
    probability: float


def _catalog_identity(path: Path) -> str:
    stat = path.stat()
    return f"{path.name} ({stat.st_size} bytes, mtime_ns {stat.st_mtime_ns})"


def _remaining(deadline: float) -> float:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise TimeoutError("The Seiza operation reached its deadline.")
    return remaining


def _search(
    catalog_path: Path,
    index_path: Path | None,
    size: tuple[int, int],
    coordinates: list[tuple[float, float, float]],
    position: tuple[float, float] | None,
    scale: float | None,
    deadline: float,
) -> GaiaCandidate:
    try:
        import seiza
    except ImportError as error:
        raise ValueError("Install the gaia extra to use the local Seiza backend.") from error

    _remaining(deadline)
    catalog_id = _catalog_identity(catalog_path)
    catalog = seiza.StarCatalog.open(catalog_path)
    try:
        if position is not None and scale is not None:
            solution = seiza.solve(
                coordinates,
                catalog,
                *size,
                ra=position[0],
                dec=position[1],
                scale_arcsec_px=scale,
                time_limit=_remaining(deadline),
                sip_order=3,
            )
        else:
            if index_path is None:
                raise ValueError("Provide the matching local Gaia blind index file.")
            index_id = _catalog_identity(index_path)
            index = seiza.BlindIndex.open(index_path)
            solution = seiza.solve_blind(
                coordinates,
                catalog,
                index,
                *size,
                min_scale_arcsec_px=GAIA_BROAD_SCALES[0],
                max_scale_arcsec_px=GAIA_BROAD_SCALES[1],
                time_limit=_remaining(deadline),
                sip_order=3,
            )
            catalog_id += f"; index {index_id}"
    except seiza.SolveError as error:
        _remaining(deadline)
        raise ValueError(str(error)) from error
    _remaining(deadline)
    matches = int(solution.matched_stars)
    rms = float(solution.rms_arcsec)
    probability = float(solution.false_match_probability)
    if matches < MIN_MATCHES or not (isfinite(rms) and rms >= 0 and 0 <= probability <= 1e-3):
        raise QualityRejected(
            f"Gaia native confidence failed ({matches} native matches, "
            f"RMS {rms:.3g} arcsec, false-match probability {probability:.3g})."
        )
    header = fits.Header(solution.fits_header_cards())
    return GaiaCandidate(
        header.tostring(sep="\n", padding=False),
        version("seiza"),
        catalog_id,
        matches,
        rms,
        probability,
    )


def search_gaia(
    catalog_path: Path,
    index_path: Path | None,
    size: tuple[int, int],
    coordinates: list[tuple[float, float, float]],
    position: tuple[float, float] | None,
    scale: float | None,
    seconds: float,
    context: JobContext,
) -> GaiaCandidate:
    task = partial(
        _search, catalog_path, index_path, size, coordinates, position, scale, monotonic() + seconds
    )
    return run_solver_worker(task, seconds, context)


def _validate(
    candidate: GaiaCandidate,
    catalog_path: Path,
    size: tuple[int, int],
    coordinates: list[tuple[float, float, float]],
    strict_edges: bool,
    deadline: float,
) -> tuple[str, dict[str, object]]:
    import seiza

    def checkpoint() -> None:
        _remaining(deadline)

    context = JobContext(checkpoint=checkpoint)
    context.check_cancelled()
    if not candidate.catalog.startswith(_catalog_identity(catalog_path)):
        raise QualityRejected("The Gaia star catalog changed after the native search.")
    catalog = seiza.StarCatalog.open(catalog_path)
    seed = read_panel_geometry(fits.Header.fromstring(candidate.header, sep="\n"), *size)

    def query(center: tuple[float, float], radius: float, limit: int) -> list[CatalogStar]:
        return [
            CatalogStar(f"{ra:.15g}/{dec:.15g}", ra, dec, magnitude)
            for ra, dec, magnitude in catalog.cone_search(*center, radius, limit=limit)
        ]

    xy = np.asarray(coordinates, dtype=np.float64)[:, :2]
    pairs = associate(seed, size, xy, query, context)
    geometry, quality = validate_models(seed, size, pairs, context, strict_edges=strict_edges)
    quality.update(
        {
            "catalog_epoch_year": None,
            "native_match_count": candidate.matched_stars,
            "native_rms_arcsec": candidate.rms_arcsec,
            "native_false_match_probability": candidate.probability,
            "native_seed_sip_order": int(seed.wcs.sip.a_order) if seed.wcs.sip is not None else 0,
        }
    )
    return geometry.wcs.to_header(relax=True).tostring(sep="\n", padding=False), quality


def validate_gaia(
    candidate: GaiaCandidate,
    catalog: Path,
    size: tuple[int, int],
    coordinates: list[tuple[float, float, float]],
    strict_edges: bool,
    seconds: float,
    context: JobContext,
) -> tuple[fits.Header, dict[str, object]]:
    task = partial(
        _validate, candidate, catalog, size, coordinates, strict_edges, monotonic() + seconds
    )
    header, quality = run_solver_worker(task, seconds, context)
    return fits.Header.fromstring(header, sep="\n"), quality
