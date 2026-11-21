"""Headless command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from dataclasses import asdict, replace
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING

from astromosaic.cli.project import add_project_commands, run_project
from astromosaic.cli.render_options import (
    add_render_options,
    panel_files,
    render_options,
    with_render_reporting,
)

if TYPE_CHECKING:
    from astromosaic.core.job import JobContext


def _run_solve(arguments: argparse.Namespace, job: JobContext) -> tuple[dict[str, object], int]:
    from astromosaic.astrometry.solve import (
        SolveOptions,
        SolveResult,
        panel_budget,
        solve_panel,
        write_solution,
    )
    from astromosaic.astrometry.solve_budget import SolveBudgetExceeded
    from astromosaic.core import SourceFingerprint
    from astromosaic.io import open_panel

    options = SolveOptions(
        gaia_catalog=arguments.gaia_catalog,
        gaia_index=arguments.gaia_index,
        astap=arguments.astap,
        astap_catalog=arguments.astap_catalog,
        astap_database=arguments.astap_database,
        position=tuple(arguments.hint) if arguments.hint is not None else None,
        scale_arcsec=arguments.scale,
        timeout_seconds=arguments.timeout,
        total_seconds=arguments.total_budget,
        job_seconds=arguments.job_budget,
        revalidate=arguments.revalidate,
        strict_edges=arguments.require_edge_validation,
        max_working_bytes=arguments.memory_mib * 1024**2,
        max_scratch_bytes=arguments.scratch_mib * 1024**2,
    )
    budget = panel_budget(options)
    context = budget.context(job)
    solution = SolveResult(None, None, ())
    existing = None
    source_path, mask_path = arguments.path, arguments.sky_mask
    try:
        context.check_cancelled()
        if arguments.path.suffix.lower() == ".astromosaic":
            from astromosaic.storage.project import load_project, open_project_sky_panel

            if arguments.panel is None or arguments.sky_mask is not None:
                raise ValueError("For a project, use --panel and its saved sky mask.")
            project = load_project(arguments.path)
            panel_index = arguments.panel - 1
            if not 0 <= panel_index < len(project.panels):
                raise ValueError("The panel number is outside the project.")
            if panel_index not in project.sky_indices():
                raise ValueError("The selected panel is excluded from the sky layer.")
            project_panel = project.panels[panel_index]
            options = replace(options, optics=project_panel.optics)
            if (
                project_panel.wcs_sidecar is not None
                and project_panel.wcs_sidecar.status() == "Ready"
            ):
                existing = project_panel.wcs_sidecar.path
            source_path = project_panel.source.path
            mask_path = project_panel.sky_mask.path if project_panel.sky_mask is not None else None
            opened = open_project_sky_panel(project_panel, options.max_working_bytes, context)
        else:
            if arguments.panel is not None:
                raise ValueError("Use --panel with an AstroMosaic project.")
            opened = open_panel(
                arguments.path,
                max_tile_bytes=options.max_working_bytes,
                sky_mask=arguments.sky_mask,
            )
        with opened as panel:
            context.check_cancelled()
            solution = solve_panel(
                panel, options, context, budget=budget, existing_sidecar=existing
            )
            if solution.geometry is not None and arguments.output is not None:
                for path, fingerprint in (
                    (source_path, panel.descriptor.fingerprint),
                    (mask_path, panel.sky_mask_fingerprint),
                ):
                    if path is not None and isinstance(fingerprint, SourceFingerprint):
                        stat = path.stat()
                        if SourceFingerprint(stat.st_size, stat.st_mtime_ns) != fingerprint:
                            raise ValueError("The source or sky mask changed during the solve.")
                write_solution(arguments.output, panel, solution, context)
    except SolveBudgetExceeded as error:
        solution = replace(
            solution,
            geometry=None,
            stage=None,
            quality=None,
            outcome="budget-exhausted",
            reason=str(error),
        )
    budget_report = budget.report()
    report = replace(solution, budget=budget_report).report()
    if solution.geometry is not None and arguments.output is not None:
        report["sidecar"] = arguments.output.name
    return report, int(solution.geometry is None)


def _run_mosaic(
    arguments: argparse.Namespace, context: JobContext
) -> tuple[dict[str, object], int]:
    from astromosaic.pipeline.mosaic import render_mosaic
    from astromosaic.pipeline.refinement import RefinementRejected

    spec, refinement = render_options(arguments)
    if refinement is not None and arguments.progress:
        print("Measuring sky stars and fitting overlaps.", file=sys.stderr)
    try:
        result = render_mosaic(
            arguments.panels,
            arguments.output,
            spec,
            weights=arguments.weights,
            filter_name=arguments.filter,
            assume_surface_brightness=arguments.assume_surface_brightness,
            sky_masks=panel_files(arguments.sky_mask, len(arguments.panels)),
            wcs_sidecars=panel_files(arguments.wcs, len(arguments.panels)),
            refinement=refinement,
            context=with_render_reporting(context, arguments.progress),
        )
    except RefinementRejected as error:
        return {"status": error.report.status, "refinement": asdict(error.report)}, 1
    payload = asdict(result)
    del payload["common_pixels"]
    if result.refinement is None:
        del payload["refinement"]
    return payload, 0


def main(argv: list[str] | None = None, *, context: JobContext | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="astromosaic", description="Work with linear FITS, TIFF, and XISF panels."
    )
    parser.add_argument("--version", action="version", version=version("astromosaic"))
    commands = parser.add_subparsers(dest="command", required=True)

    inspect = commands.add_parser("inspect", help="Read FITS, TIFF, or XISF image metadata.")
    inspect.add_argument("path", type=Path)
    smoke = commands.add_parser("smoke", help="Run a small synthetic FITS/WCS processing job.")
    smoke.add_argument("--spawn", action="store_true", help="Run the job in a spawned worker.")
    solve = commands.add_parser("solve", help="Resolve a panel with local astrometry.")
    solve.add_argument(
        "path", type=Path, help="Linear FITS, TIFF, or XISF panel, or an AstroMosaic project."
    )
    solve.add_argument("--panel", type=int, help="One-based panel number in the saved project.")
    solve.add_argument("-o", "--output", type=Path, help="Save a new JSON WCS sidecar on success.")
    solve.add_argument("--sky-mask", type=Path, help="Binary FITS sky mask in source coordinates.")
    solve.add_argument("--gaia-catalog", type=Path, help="Local Seiza Gaia DR3 catalog file.")
    solve.add_argument("--gaia-index", type=Path, help="Matching local Gaia DR3 blind index.")
    solve.add_argument("--astap", type=Path, help="Local ASTAP executable.")
    solve.add_argument("--astap-catalog", type=Path, help="Local ASTAP star catalog directory.")
    solve.add_argument(
        "--astap-database",
        default="auto",
        choices=("auto", "d05", "d20", "d50", "d80"),
        help="Use Automatic selection or pin an installed D-series catalog.",
    )
    solve.add_argument("--hint", nargs=2, type=float, metavar=("RA", "DEC"), help="ICRS degrees.")
    solve.add_argument("--scale", type=float, metavar="ARCSEC", help="Approximate pixel scale.")
    solve.add_argument(
        "--timeout", type=float, default=60, help="Upper limit per native attempt, in seconds."
    )
    solve.add_argument(
        "--total-budget",
        type=float,
        default=120,
        metavar="SECONDS",
        help="Panel time budget including preparation, validation and sidecar publication (120).",
    )
    solve.add_argument(
        "--job-budget",
        type=float,
        metavar="SECONDS",
        help="Optional overall job deadline. Takes precedence if it expires first.",
    )
    solve.add_argument(
        "--revalidate", action="store_true", help="Require a new catalog-validated WCS."
    )
    solve.add_argument(
        "--require-edge-validation",
        action="store_true",
        help="Require a new WCS with supported held-out field-edge accuracy.",
    )
    solve.add_argument("--memory-mib", type=int, default=64, help="Working buffer budget in MiB.")
    solve.add_argument("--scratch-mib", type=int, default=1024, help="ASTAP staging limit in MiB.")
    mosaic = commands.add_parser("mosaic", help="Render a linear mosaic with resolved WCS.")
    mosaic.add_argument(
        "panels", nargs="+", type=Path, help="Linear inputs with a common channel layout."
    )
    mosaic.add_argument(
        "-o", "--output", required=True, type=Path, help="A new FITS (mono), TIFF, or XISF path."
    )
    add_render_options(mosaic)
    mosaic.add_argument("--progress", action="store_true", help="Report tile progress to stderr.")
    add_project_commands(
        commands.add_parser(
            "project", help="Create, inspect, fit or export saved AstroMosaic projects."
        )
    )
    arguments = parser.parse_args(argv)

    # Set the BLAS default before importing native modules for command execution.
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    if arguments.command == "project":
        return run_project(arguments, context=context)

    from astromosaic.core.job import DEFAULT_JOB_CONTEXT, MosaicCancelled

    job = context or DEFAULT_JOB_CONTEXT
    result: Mapping[str, object]
    status = 0
    try:
        job.check_cancelled()
        if arguments.command == "inspect":
            from astromosaic.astrometry.hints import positive_header_number, read_optics
            from astromosaic.io import open_panel
            from astromosaic.io.fits import optional_header_text

            with open_panel(arguments.path) as panel:
                header = panel.header
                optics = read_optics(header)
                result = {
                    **asdict(panel.descriptor),
                    "camera_model": optional_header_text(header, "INSTRUME"),
                    "telescope_model": optional_header_text(header, "TELESCOP"),
                    "optics": asdict(optics),
                    "optical_scale_arcsec": optics.scales_arcsec(),
                    "embedded_scale_arcsec": positive_header_number(header.get("PIXSCALE")),
                }
            job.check_cancelled()
        elif arguments.command == "mosaic":
            result, status = _run_mosaic(arguments, job)
        elif arguments.command == "solve":
            result, status = _run_solve(arguments, job)
        else:
            from astromosaic.pipeline.smoke import run_smoke

            result = run_smoke(spawn=arguments.spawn)
            job.check_cancelled()
    except (KeyboardInterrupt, MosaicCancelled):
        print("astromosaic: Job interrupted.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError) as error:
        print(f"astromosaic: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return status
