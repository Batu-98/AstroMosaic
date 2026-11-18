"""Resolve a panel with local astrometry and keep the solution separate from the image."""

import json
import subprocess
from dataclasses import asdict, dataclass, replace
from math import atan, degrees, isfinite, radians
from pathlib import Path
from shutil import disk_usage
from typing import Any, Literal

import numpy as np
from astropy.io import fits

from astromosaic.astrometry.astap_catalog import CatalogStar, query_astap_cone
from astromosaic.astrometry.astap_probe import (
    AstapCandidate,
    AstapSetup,
    check_astap_setup,
    solve_astap,
)
from astromosaic.astrometry.distortion import validate_models
from astromosaic.astrometry.gaia_solve import GAIA_BROAD_SCALES, search_gaia, validate_gaia
from astromosaic.astrometry.hints import PanelOptics, positive_header_number, read_optics
from astromosaic.astrometry.solve_budget import (
    DEFAULT_PANEL_SECONDS,
    SolveBudget,
    SolveBudgetExceeded,
)
from astromosaic.astrometry.solve_validation import MIN_MATCHES, QualityRejected, associate
from astromosaic.astrometry.stars import astrometry_pixels, measure_stars
from astromosaic.core import Region, SourceFingerprint
from astromosaic.core.job import DEFAULT_JOB_CONTEXT, JobContext, MosaicCancelled
from astromosaic.geometry import PanelGeometry, read_panel_geometry
from astromosaic.io import PanelSource
from astromosaic.io.atomic import atomic_binary_file

Stage = Literal["existing-wcs", "gaia-dr3", "astap-hinted", "astap-blind"]
_STAGES: tuple[Stage, ...] = ("existing-wcs", "astap-hinted", "astap-blind", "gaia-dr3")


@dataclass(frozen=True, slots=True)
class SolveOptions:
    gaia_catalog: Path | None = None
    gaia_index: Path | None = None
    astap: Path | None = None
    astap_catalog: Path | None = None
    astap_database: str = "auto"
    position: tuple[float, float] | None = None
    scale_arcsec: float | None = None
    timeout_seconds: float = 60
    max_working_bytes: int = 64 * 1024**2
    max_scratch_bytes: int = 1024**3
    optics: PanelOptics = PanelOptics()
    total_seconds: float = DEFAULT_PANEL_SECONDS
    job_seconds: float | None = None
    revalidate: bool = False
    strict_edges: bool = False


@dataclass(frozen=True, slots=True)
class SolverAttempt:
    stage: Stage
    outcome: Literal["solved", "failed", "skipped", "timeout", "rejected", "budget-exhausted"]
    detail: str
    backend_version: str | None = None
    catalog: str | None = None
    matched_stars: int | None = None
    rms_arcsec: float | None = None
    catalog_selection: str | None = None
    method: str | None = None
    effective_position_deg: tuple[float, float] | None = None
    effective_scale_arcsec_px: float | None = None
    effective_fov_deg: float | None = None
    effective_scale_interval_arcsec_px: tuple[float, float] | None = None
    preparation_seconds: float = 0.0
    search_seconds: float = 0.0
    validation_seconds: float = 0.0
    remaining_at_search_seconds: float | None = None
    search_limit_seconds: float | None = None
    rejection_evidence: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class SolveResult:
    geometry: PanelGeometry | None
    stage: Stage | None
    attempts: tuple[SolverAttempt, ...]
    outcome: str = "unsolved"
    budget: dict[str, object] | None = None
    original_hints: dict[str, object] | None = None
    quality: dict[str, object] | None = None
    reason: str | None = None

    def report(self) -> dict[str, object]:
        return {
            "policy": "3.6",
            "status": "solved" if self.geometry is not None else self.outcome,
            "stage": self.stage,
            "attempts": [asdict(attempt) for attempt in self.attempts],
            "budget": self.budget,
            "original_hints": self.original_hints,
            "quality": self.quality,
            "reason": self.reason,
        }


def _pointing(
    source: PanelSource, options: SolveOptions
) -> tuple[tuple[float, float] | None, float | None, float | None]:
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
    scale = scale if scale is not None else positive_header_number(header.get("PIXSCALE"))
    if scale is not None:
        return position, scale, scale
    scale_x, scale_y = read_optics(header).with_overrides(options.optics).scales_arcsec()
    # Gaia takes a single scale. ASTAP takes the vertical field of view.
    gaia_scale = scale_y if scale_x == scale_y else None
    return position, gaia_scale, scale_y


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


def _validate_astap(
    candidate: AstapCandidate,
    directory: Path,
    size: tuple[int, int],
    coordinates: list[tuple[float, float, float]],
    strict_edges: bool,
    context: JobContext,
) -> tuple[fits.Header, dict[str, object]]:
    seed = read_panel_geometry(candidate.header, *size)
    epoch: float | None = None
    byte_limit = 64 * 1024**2
    tiles: set[str] = set()

    def query(center: tuple[float, float], radius: float, limit: int) -> tuple[CatalogStar, ...]:
        nonlocal epoch, byte_limit
        try:
            cone = query_astap_cone(
                directory,
                candidate.database,
                center,
                radius,
                max_stars=100_000,
                max_read_bytes=byte_limit,
                context=context,
            )
        except (OSError, ValueError) as error:
            raise QualityRejected(
                f"Could not verify ASTAP against its local catalog. {error}"
            ) from error
        if epoch is not None and epoch != cone.epoch_year:
            raise QualityRejected("The ASTAP validation regions have inconsistent catalog epochs.")
        tiles.update(cone.tiles)
        epoch = cone.epoch_year
        byte_limit -= cone.read_bytes
        return cone.stars

    xy = np.asarray(coordinates, dtype=np.float64)[:, :2]
    pairs = associate(seed, size, xy, query, context)
    geometry, quality = validate_models(seed, size, pairs, context, strict_edges=strict_edges)
    quality.update(
        {
            "catalog_epoch_year": epoch,
            "catalog_tiles": len(tiles),
            "catalog_read_bytes": 64 * 1024**2 - byte_limit,
            "native_seed_sip_order": int(seed.wcs.sip.a_order) if seed.wcs.sip is not None else 0,
        }
    )
    return geometry.wcs.to_header(relax=True), quality


def panel_budget(options: SolveOptions, parent: SolveBudget | None = None) -> SolveBudget:
    if parent is None and options.job_seconds is not None:
        parent = SolveBudget.begin(options.job_seconds, scope="job")
    return SolveBudget.begin(options.total_seconds, parent=parent)


class _PanelSolve:
    def __init__(
        self,
        source: PanelSource,
        options: SolveOptions,
        budget: SolveBudget,
        context: JobContext,
    ) -> None:
        self.source, self.options, self.budget = source, options, budget
        self.context = budget.context(context)
        self.size = source.descriptor.width, source.descriptor.height
        self.astap_setup: AstapSetup | None = None
        self.astap_problem: str | None = None
        self.gaia_available = False
        self._coordinates: list[tuple[float, float, float]] | None = None

    def coordinates(self) -> list[tuple[float, float, float]]:
        self.context.check_cancelled()
        if self._coordinates is None:
            field = measure_stars(self.source, self.options.max_working_bytes, self.context)
            self._coordinates = [(s.x, s.y, s.flux) for s in field.stars]
        if len(self._coordinates) < MIN_MATCHES:
            raise QualityRejected(f"Fewer than {MIN_MATCHES} isolated sky stars were measured.")
        return self._coordinates

    def astap_ready(self) -> AstapSetup | None:
        options = self.options
        if options.astap is None or options.astap_catalog is None:
            self.astap_problem = "No local ASTAP executable and catalog configured."
        if self.astap_setup is None and self.astap_problem is None:
            assert options.astap is not None and options.astap_catalog is not None
            try:
                self.astap_setup = check_astap_setup(
                    options.astap, options.astap_catalog, options.astap_database, self.context
                )
            except subprocess.TimeoutExpired:
                self.astap_problem = "The ASTAP CLI did not answer its help check in time."
            except (OSError, ValueError) as error:
                self.astap_problem = str(error)
        return self.astap_setup

    def attempt(
        self,
        stage: Stage,
        method: str,
        position: tuple[float, float] | None,
        gaia_scale: float | None,
        vertical_scale: float | None,
    ) -> tuple[PanelGeometry | None, SolverAttempt, dict[str, object] | None]:
        options, context, budget = self.options, self.context, self.budget
        started = budget.clock()
        search_started = validation_started = None
        remaining = search_limit = None
        attempt = SolverAttempt(stage, "skipped", "", method=method)
        geometry = None
        quality = None

        def start_search() -> float:
            nonlocal search_started, remaining, search_limit
            context.check_cancelled()
            remaining = budget.remaining()
            search_limit = budget.search_seconds(
                stage if stage.startswith("astap-") else f"gaia-{method}",
                options.timeout_seconds,
                astap_only=not self.gaia_available and method == "blind",
            )
            search_started = budget.clock()
            return search_limit

        try:
            context.check_cancelled()
            header = None
            if stage.startswith("astap-"):
                if method == "hinted" and position is None and vertical_scale is None:
                    attempt = replace(attempt, detail="No usable pointing or scale hint.")
                elif (setup := self.astap_ready()) is None:
                    attempt = replace(attempt, detail=self.astap_problem or "ASTAP unavailable.")
                else:
                    assert options.astap is not None and options.astap_catalog is not None
                    effective_position = position if method in ("hinted", "fov-recovery") else None
                    fov = (
                        degrees(2 * atan(radians(self.size[1] * vertical_scale / 3600) / 2))
                        if method == "hinted" and vertical_scale is not None
                        else 0.0
                    )
                    attempt = replace(
                        attempt,
                        backend_version=setup.version,
                        catalog_selection=setup.selection_reason,
                        effective_position_deg=effective_position,
                        effective_fov_deg=fov,
                    )
                    candidate = solve_astap(
                        options.astap,
                        options.astap_catalog,
                        lambda path: _stage_astap_input(self.source, path, options, context),
                        position=effective_position,
                        field_height_deg=fov,
                        setup=setup,
                        database=options.astap_database,
                        search_seconds=start_search,
                        sip=True,
                        context=context,
                    )
                    validation_started = budget.clock()
                    attempt = replace(
                        attempt, catalog=candidate.database, backend_version=candidate.version
                    )
                    header, quality = _validate_astap(
                        candidate,
                        options.astap_catalog,
                        self.size,
                        self.coordinates(),
                        options.strict_edges,
                        context,
                    )
            elif options.gaia_catalog is None or not options.gaia_catalog.is_file():
                attempt = replace(attempt, detail="Choose a readable local Seiza Gaia DR3 catalog.")
            elif method == "hinted" and (position is None or gaia_scale is None):
                attempt = replace(
                    attempt, detail="Gaia hinted solving requires pointing and scale."
                )
            elif method == "blind" and (
                options.gaia_index is None or not options.gaia_index.is_file()
            ):
                attempt = replace(attempt, detail="Choose the matching local Gaia blind index.")
            else:
                effective_position = position if method == "hinted" else None
                effective_scale = gaia_scale if method == "hinted" else None
                attempt = replace(
                    attempt,
                    effective_position_deg=effective_position,
                    effective_scale_arcsec_px=effective_scale,
                    effective_scale_interval_arcsec_px=GAIA_BROAD_SCALES
                    if method == "blind"
                    else None,
                )
                coordinates = self.coordinates()
                native = search_gaia(
                    options.gaia_catalog,
                    options.gaia_index,
                    self.size,
                    coordinates,
                    effective_position,
                    effective_scale,
                    start_search(),
                    context,
                )
                validation_started = budget.clock()
                attempt = replace(attempt, catalog=native.catalog, backend_version=native.version)
                header, quality = validate_gaia(
                    native,
                    options.gaia_catalog,
                    self.size,
                    coordinates,
                    options.strict_edges,
                    budget.remaining(),
                    context,
                )

            if header is not None:
                context.check_cancelled()
                geometry = read_panel_geometry(header, *self.size)
                assert quality is not None
                count, rms_arcsec = quality["unique_matches"], quality["rms_arcsec"]
                assert isinstance(count, int) and isinstance(rms_arcsec, float)
                attempt = replace(
                    attempt,
                    outcome="solved",
                    detail=f"Catalog-validated {quality['model']} WCS.",
                    matched_stars=count,
                    rms_arcsec=rms_arcsec,
                )
        except MosaicCancelled:
            raise
        except SolveBudgetExceeded as error:
            attempt = replace(attempt, outcome="budget-exhausted", detail=str(error))
        except (TimeoutError, subprocess.TimeoutExpired):
            attempt = replace(attempt, outcome="timeout", detail="The solver attempt timed out.")
        except QualityRejected as error:
            attempt = replace(
                attempt,
                outcome="rejected",
                detail=str(error),
                rejection_evidence=error.evidence,
            )
        except (OSError, RuntimeError, ValueError, OverflowError) as error:
            attempt = replace(attempt, outcome="failed", detail=str(error))

        # Cancellation wins even if a backend reports an ordinary error on exit.
        try:
            context.check_cancelled()
        except SolveBudgetExceeded as error:
            geometry = None
            attempt = replace(attempt, outcome="budget-exhausted", detail=str(error))
        now = budget.clock()
        return (
            geometry,
            replace(
                attempt,
                preparation_seconds=(search_started if search_started is not None else now)
                - started,
                search_seconds=(validation_started if validation_started is not None else now)
                - search_started
                if search_started is not None
                else 0.0,
                validation_seconds=now - validation_started
                if validation_started is not None
                else 0.0,
                remaining_at_search_seconds=remaining,
                search_limit_seconds=search_limit,
            ),
            quality if geometry is not None else None,
        )


def solve_panel(
    source: PanelSource,
    options: SolveOptions,
    context: JobContext = DEFAULT_JOB_CONTEXT,
    *,
    budget: SolveBudget | None = None,
    existing_sidecar: Path | None = None,
) -> SolveResult:
    """Run the ordered local policy under a deadline started by the caller."""
    if not isfinite(options.timeout_seconds) or options.timeout_seconds <= 0:
        raise ValueError("The solver timeout must be positive and finite.")
    if min(options.max_working_bytes, options.max_scratch_bytes) <= 0:
        raise ValueError("Solver resource budgets must be positive.")
    budget = budget if budget is not None else panel_budget(options)
    run = _PanelSolve(source, options, budget, context)
    attempts: list[SolverAttempt] = []
    hints: dict[str, object] | None = None

    def finish(
        geometry: PanelGeometry | None,
        stage: Stage | None,
        outcome: str,
        quality: dict[str, object] | None = None,
        reason: str | None = None,
    ) -> SolveResult:
        return SolveResult(
            geometry, stage, tuple(attempts), outcome, budget.report(), hints, quality, reason
        )

    try:
        run.context.check_cancelled()
        started = budget.clock()
        if options.revalidate or options.strict_edges:
            attempts.append(
                SolverAttempt("existing-wcs", "skipped", "Explicit revalidation requested.")
            )
        else:
            try:
                if existing_sidecar is not None:
                    geometry, detail = load_solution(existing_sidecar, source)
                else:
                    geometry = read_panel_geometry(source.header, *run.size)
                    detail = {
                        "tiff-description": "Validated embedded TIFF WCS.",
                        "xisf-fits-keywords": "Validated embedded XISF WCS.",
                        None: "Validated primary FITS WCS.",
                        "primary-header": "Validated primary FITS WCS.",
                    }[source.descriptor.wcs_provenance]
            except (OSError, ValueError, OverflowError) as error:
                attempts.append(SolverAttempt("existing-wcs", "failed", str(error)))
            else:
                run.context.check_cancelled()
                attempts.append(
                    SolverAttempt(
                        "existing-wcs",
                        "solved",
                        detail,
                        preparation_seconds=budget.clock() - started,
                    )
                )
                return finish(geometry, "existing-wcs", "solved", {"grade": "geometry-only"})

        position, scale, vertical_scale = _pointing(source, options)
        run.gaia_available = options.gaia_catalog is not None and options.gaia_catalog.is_file()
        scale_origin = None
        if scale is not None or vertical_scale is not None:
            if options.scale_arcsec is not None:
                scale_origin = "explicit scale"
            elif positive_header_number(source.header.get("PIXSCALE")) is not None:
                scale_origin = "embedded PIXSCALE"
            elif options.optics != PanelOptics():
                scale_origin = "optical metadata with project overrides"
            else:
                scale_origin = "embedded optical metadata"
        hints = {
            "position_deg": position,
            "position_source": (
                "explicit pointing" if options.position is not None else "embedded RA/DEC"
            )
            if position is not None
            else None,
            "gaia_scale_arcsec_px": scale,
            "astap_vertical_scale_arcsec_px": vertical_scale,
            "scale_source": scale_origin,
            "astap_requested_database": options.astap_database,
        }
        # In ASTAP-only setups a known pointing makes the native FOV scan useful.
        # Keep a full-sky blind path when there is no pointing or when Gaia can
        # recover from a stale hint independently.
        recovery = (
            "fov-recovery"
            if not run.gaia_available and position is not None and vertical_scale is not None
            else "blind"
        )
        selections: list[tuple[Stage, str]] = [
            ("astap-hinted", "hinted"),
            ("astap-blind", recovery),
        ]
        if options.gaia_catalog is not None and (position is not None and scale is not None):
            selections.append(("gaia-dr3", "hinted"))
        if (
            options.gaia_catalog is None
            or options.gaia_index is not None
            or (position is None or scale is None)
        ):
            selections.append(("gaia-dr3", "blind"))
        for stage, method in selections:
            solved, attempt, quality = run.attempt(stage, method, position, scale, vertical_scale)
            attempts.append(attempt)
            if solved is not None:
                return finish(solved, stage, "solved", quality)
            if attempt.outcome == "budget-exhausted":
                return finish(None, None, "budget-exhausted", reason=attempt.detail)
        run.context.check_cancelled()
    except SolveBudgetExceeded as error:
        return finish(None, None, "budget-exhausted", reason=str(error))
    if any(attempt.outcome == "rejected" for attempt in attempts):
        return finish(None, None, "quality-rejected")
    if all(a.outcome == "skipped" for a in attempts if a.stage != "existing-wcs"):
        return finish(None, None, "unavailable")
    return finish(None, None, "unsolved")


def _source_identity(source: PanelSource) -> dict[str, object]:
    descriptor = source.descriptor
    mask = source.sky_mask_fingerprint
    return {
        "fingerprint": asdict(descriptor.fingerprint),
        "size": [descriptor.width, descriptor.height],
        "sky_mask": asdict(mask) if isinstance(mask, SourceFingerprint) else mask,
    }


def write_solution(
    path: Path,
    source: PanelSource,
    solution: SolveResult,
    context: JobContext = DEFAULT_JOB_CONTEXT,
) -> None:
    context.check_cancelled()
    if solution.geometry is None:
        raise ValueError("A WCS sidecar requires a solved panel.")
    header = solution.geometry.wcs.to_header(relax=True)
    record = {
        "version": 2,
        "source": _source_identity(source),
        **solution.report(),
        "quality": solution.quality or {"grade": "geometry-only"},
        "wcs": header.tostring(sep="\n", padding=False),
    }
    payload = (json.dumps(record, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(payload) > 128 * 1024:
        raise ValueError("The generated WCS sidecar exceeds its size limit.")
    with atomic_binary_file(path, publish_check=context.check_cancelled) as stream:
        stream.write(payload)


def _read_solution_record(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        payload = stream.read(128 * 1024 + 1)
    if len(payload) > 128 * 1024:
        raise ValueError("The WCS sidecar exceeds its size limit.")
    record = json.loads(payload)
    if (
        not isinstance(record, dict)
        or record.get("version") not in (1, 2)
        or record.get("status") != "solved"
        or record.get("stage") not in _STAGES
        or not isinstance(record.get("wcs"), str)
    ):
        raise ValueError("Expected a supported solved AstroMosaic WCS sidecar.")
    if record["version"] == 2:
        quality = record.get("quality")
        if not isinstance(quality, dict) or quality.get("grade") not in (
            "geometry-only",
            "catalog-validated",
        ):
            raise ValueError("The WCS sidecar has an invalid quality grade.")
    return record


def read_solution_quality(path: Path) -> dict[str, object]:
    """Read diagnostics for an already verified sidecar."""
    record = _read_solution_record(path)
    if record["version"] == 1:
        return {"grade": "geometry-only"}
    quality: dict[str, object] = record["quality"]
    return quality


def load_solution(path: Path, source: PanelSource) -> tuple[PanelGeometry, str]:
    record = _read_solution_record(path)
    if record.get("source") != _source_identity(source):
        raise ValueError("The WCS sidecar belongs to a different input or sky mask revision.")
    header = fits.Header.fromstring(record["wcs"], sep="\n")
    return (
        read_panel_geometry(header, source.descriptor.width, source.descriptor.height),
        f"{record['stage']} WCS sidecar",
    )
