"""Resolve a panel with local astrometry and keep the solution separate from the image."""

import json
import subprocess
from dataclasses import asdict, dataclass
from importlib.metadata import version
from math import isfinite
from pathlib import Path
from shutil import disk_usage
from time import monotonic
from typing import Literal

import numpy as np
from astropy.io import fits

from astromosaic.astrometry.astap_probe import solve_astap
from astromosaic.astrometry.stars import astrometry_pixels, measure_stars
from astromosaic.core import Region, SourceFingerprint
from astromosaic.core.job import DEFAULT_JOB_CONTEXT, JobContext, MosaicCancelled
from astromosaic.geometry import PanelGeometry, read_panel_geometry
from astromosaic.io import PanelSource
from astromosaic.io.atomic import atomic_binary_file

Stage = Literal["existing-wcs", "gaia-dr3", "astap-hinted", "astap-blind"]
_STAGES: tuple[Stage, ...] = ("existing-wcs", "gaia-dr3", "astap-hinted", "astap-blind")


@dataclass(frozen=True, slots=True)
class SolveOptions:
    gaia_catalog: Path | None = None
    gaia_index: Path | None = None
    astap: Path | None = None
    astap_catalog: Path | None = None
    astap_database: str = "d05"
    position: tuple[float, float] | None = None
    scale_arcsec: float | None = None
    timeout_seconds: float = 60
    max_working_bytes: int = 64 * 1024**2
    max_scratch_bytes: int = 1024**3


@dataclass(frozen=True, slots=True)
class SolverAttempt:
    stage: Stage
    outcome: Literal["solved", "failed", "skipped", "timeout"]
    detail: str
    backend_version: str | None = None
    catalog: str | None = None
    matched_stars: int | None = None
    rms_arcsec: float | None = None


@dataclass(frozen=True, slots=True)
class SolveResult:
    geometry: PanelGeometry | None
    stage: Stage | None
    attempts: tuple[SolverAttempt, ...]

    def report(self) -> dict[str, object]:
        return {
            "status": "solved" if self.geometry is not None else "unsolved",
            "stage": self.stage,
            "attempts": [asdict(attempt) for attempt in self.attempts],
        }


def _pointing(
    source: PanelSource, options: SolveOptions
) -> tuple[tuple[float, float] | None, float | None]:
    position, scale = options.position, options.scale_arcsec
    if position is not None and not (0 <= position[0] < 360 and -90 <= position[1] <= 90):
        raise ValueError("Expected valid ICRS pointing in degrees.")
    if scale is not None and not (isfinite(scale) and scale > 0):
        raise ValueError("Expected a positive finite plate scale in arcseconds per pixel.")
    header = source.header
    if position is None and all(isinstance(header.get(key), int | float) for key in ("RA", "DEC")):
        ra, dec = float(header["RA"]), float(header["DEC"])
        if 0 <= ra < 360 and -90 <= dec <= 90:
            position = ra, dec
    if scale is None and isinstance(header.get("PIXSCALE"), int | float):
        candidate = float(header["PIXSCALE"])
        if isfinite(candidate) and candidate > 0:
            scale = candidate
    return position, scale


def _stage_astap_input(
    source: PanelSource, path: Path, options: SolveOptions, context: JobContext
) -> None:
    width, height = source.descriptor.width, source.descriptor.height
    staged_bytes = 2880 + ((4 * width * height + 2879) // 2880) * 2880
    if staged_bytes > min(options.max_scratch_bytes, disk_usage(path.parent).free):
        raise ValueError("The solver input exceeds the available scratch byte budget.")

    rows = min(height, 128)
    buffer_budget = options.max_working_bytes - 128 * 1024
    while source.tile_bytes(Region(0, 0, width, rows)) + 8 * width * rows > buffer_budget:
        if rows == 1:
            raise ValueError("The working budget cannot fit a solver input row.")
        rows //= 2
    # Use one neutral sky level throughout the excluded region to avoid patch boundaries.
    sample_width, sample_height = min(width, 32), min(height, rows, 32)
    samples = np.empty(9 * sample_width * sample_height, dtype=np.float32)
    count = 0
    for y in sorted({0, (height - sample_height) // 2, height - sample_height}):
        for x in sorted({0, (width - sample_width) // 2, width - sample_width}):
            context.check_cancelled()
            tile = source.read_tile(Region(x, y, sample_width, sample_height))
            pixels = astrometry_pixels(tile)[tile.valid]
            samples[count : count + pixels.size] = pixels
            count += pixels.size
    fill = float(np.median(samples[:count])) if count else 0.0

    header = fits.PrimaryHDU().header
    header["BITPIX"] = -32
    header["NAXIS"] = 2
    header.set("NAXIS1", width, after="NAXIS")
    header.set("NAXIS2", height, after="NAXIS1")
    stream = fits.StreamingHDU(str(path), header)
    try:
        for y in range(0, height, rows):
            context.check_cancelled()
            tile = source.read_tile(Region(0, y, width, min(rows, height - y)))
            pixels = np.ascontiguousarray(astrometry_pixels(tile))
            np.copyto(pixels, fill, where=~tile.valid)
            stream.write(pixels)
    finally:
        stream.close()


def _solve_gaia(
    source: PanelSource,
    options: SolveOptions,
    catalog_path: Path,
    position: tuple[float, float] | None,
    scale: float | None,
    context: JobContext,
) -> tuple[fits.Header, SolverAttempt]:
    try:
        import seiza
    except ImportError as error:
        raise ValueError("Install the gaia extra to use the local Seiza backend.") from error

    if not catalog_path.is_file():
        raise ValueError("Provide an explicit local Gaia DR3 catalog file.")
    hinted = position is not None and scale is not None
    if not hinted and options.gaia_index is None:
        raise ValueError("Gaia DR3 needs pointing and scale hints or a local blind index.")
    stars = measure_stars(source, options.max_working_bytes, context).stars
    if len(stars) < 8:
        raise ValueError("Too few isolated sky stars for a Gaia DR3 solution.")
    coordinates = [(star.x, star.y, star.flux) for star in stars]
    catalog = seiza.StarCatalog.open(catalog_path)
    width, height = source.descriptor.width, source.descriptor.height
    deadline = monotonic() + options.timeout_seconds
    context.check_cancelled()
    solution = None
    method = "hinted"
    index_identity = ""

    def confident(candidate: seiza.Solution) -> bool:
        return (
            candidate.matched_stars >= 8
            and 0 <= candidate.false_match_probability <= 1e-3
            and 0 <= candidate.rms_arcsec <= 2 * candidate.scale_arcsec_px
        )

    if position is not None and scale is not None:
        try:
            solution = seiza.solve(
                coordinates,
                catalog,
                width,
                height,
                ra=position[0],
                dec=position[1],
                scale_arcsec_px=scale,
                time_limit=options.timeout_seconds,
                cancel=context.is_cancelled,
            )
        except seiza.SolveError:
            context.check_cancelled()
            if options.gaia_index is None:
                raise
    if solution is not None and not confident(solution) and options.gaia_index is not None:
        solution = None
    if solution is None:
        context.check_cancelled()
        index_path = options.gaia_index
        if index_path is None or not index_path.is_file():
            raise ValueError("Provide the matching local Gaia blind index file.")
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("The Gaia DR3 solve deadline elapsed.")
        index = seiza.BlindIndex.open(index_path)
        lower, upper = (scale * 0.8, scale * 1.2) if scale is not None else (0.1, 20.0)
        solution = seiza.solve_blind(
            coordinates,
            catalog,
            index,
            width,
            height,
            min_scale_arcsec_px=lower,
            max_scale_arcsec_px=upper,
            time_limit=remaining,
            cancel=context.is_cancelled,
        )
        method = "blind"
        index_identity = f"; index {_catalog_identity(index_path)}"
    context.check_cancelled()
    if not confident(solution):
        raise ValueError("Gaia DR3 match confidence was below the acceptance threshold.")
    return fits.Header(solution.fits_header_cards()), SolverAttempt(
        "gaia-dr3",
        "solved",
        method,
        version("seiza"),
        _catalog_identity(catalog_path) + index_identity,
        solution.matched_stars,
        solution.rms_arcsec,
    )


def _catalog_identity(path: Path) -> str:
    stat = path.stat()
    return f"{path.name} ({stat.st_size} bytes, mtime_ns {stat.st_mtime_ns})"


def solve_panel(
    source: PanelSource, options: SolveOptions, context: JobContext = DEFAULT_JOB_CONTEXT
) -> SolveResult:
    """Stop at the first validated local WCS and report each attempted stage."""
    if not isfinite(options.timeout_seconds) or options.timeout_seconds <= 0:
        raise ValueError("The solver timeout must be positive and finite.")
    if min(options.max_working_bytes, options.max_scratch_bytes) <= 0:
        raise ValueError("Solver resource budgets must be positive.")
    width, height = source.descriptor.width, source.descriptor.height
    position, scale = _pointing(source, options)
    attempts: list[SolverAttempt] = []
    for stage in _STAGES:
        context.check_cancelled()
        catalog = options.gaia_catalog
        if stage == "gaia-dr3" and catalog is None:
            attempts.append(
                SolverAttempt(stage, "skipped", "No local Gaia DR3 catalog configured.")
            )
            continue
        if stage == "astap-hinted" and position is None:
            attempts.append(SolverAttempt(stage, "skipped", "No usable pointing hint."))
            continue
        if stage.startswith("astap-") and (options.astap is None or options.astap_catalog is None):
            attempts.append(
                SolverAttempt(stage, "skipped", "No local ASTAP executable and catalog configured.")
            )
            continue
        try:
            if stage == "existing-wcs":
                header = source.header
                detail = (
                    "Validated embedded TIFF WCS."
                    if source.descriptor.wcs_provenance == "tiff-description"
                    else "Validated primary FITS WCS."
                )
                attempt = SolverAttempt(stage, "solved", detail)
            elif stage == "gaia-dr3":
                assert catalog is not None
                header, attempt = _solve_gaia(source, options, catalog, position, scale, context)
            else:
                assert options.astap is not None and options.astap_catalog is not None
                header, backend = solve_astap(
                    options.astap,
                    options.astap_catalog,
                    lambda path: _stage_astap_input(source, path, options, context),
                    position=position if stage == "astap-hinted" else None,
                    field_height_deg=height * scale / 3600 if scale is not None else 0,
                    timeout_seconds=options.timeout_seconds,
                    database=options.astap_database,
                    context=context,
                )
                attempt = SolverAttempt(
                    stage, "solved", "Validated ASTAP WCS.", backend, options.astap_database
                )
            context.check_cancelled()
            geometry = read_panel_geometry(header, width, height)
        except MosaicCancelled:
            raise
        except (TimeoutError, subprocess.TimeoutExpired):
            context.check_cancelled()
            attempts.append(
                SolverAttempt(stage, "timeout", f"Exceeded {options.timeout_seconds:g} seconds.")
            )
        except (OSError, RuntimeError, ValueError) as error:
            context.check_cancelled()
            attempts.append(SolverAttempt(stage, "failed", str(error)))
        else:
            attempts.append(attempt)
            return SolveResult(geometry, stage, tuple(attempts))
    return SolveResult(None, None, tuple(attempts))


def _source_identity(source: PanelSource) -> dict[str, object]:
    descriptor = source.descriptor
    mask = source.sky_mask_fingerprint
    return {
        "fingerprint": asdict(descriptor.fingerprint),
        "size": [descriptor.width, descriptor.height],
        "sky_mask": asdict(mask) if isinstance(mask, SourceFingerprint) else mask,
    }


def write_solution(path: Path, source: PanelSource, solution: SolveResult) -> None:
    if solution.geometry is None:
        raise ValueError("A WCS sidecar requires a solved panel.")
    header = solution.geometry.wcs.to_header(relax=True)
    record = {
        "version": 1,
        "source": _source_identity(source),
        **solution.report(),
        "wcs": header.tostring(sep="\n", padding=False),
    }
    with atomic_binary_file(path) as stream:
        stream.write((json.dumps(record, indent=2, allow_nan=False) + "\n").encode("utf-8"))


def load_solution(path: Path, source: PanelSource) -> tuple[PanelGeometry, str]:
    with path.open("rb") as stream:
        payload = stream.read(128 * 1024 + 1)
    if len(payload) > 128 * 1024:
        raise ValueError("The WCS sidecar exceeds its size limit.")
    record = json.loads(payload)
    if (
        not isinstance(record, dict)
        or record.get("version") != 1
        or record.get("status") != "solved"
        or record.get("stage") not in _STAGES
        or not isinstance(record.get("wcs"), str)
    ):
        raise ValueError("Expected a version 1 solved AstroMosaic WCS sidecar.")
    if record.get("source") != _source_identity(source):
        raise ValueError("The WCS sidecar belongs to a different input or sky mask revision.")
    header = fits.Header.fromstring(record["wcs"], sep="\n")
    return (
        read_panel_geometry(header, source.descriptor.width, source.descriptor.height),
        f"{record['stage']} WCS sidecar",
    )
