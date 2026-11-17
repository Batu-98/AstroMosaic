"""Headless command-line interface."""

import argparse
import json
import os
import sys
from collections.abc import Mapping
from dataclasses import asdict, replace
from importlib.metadata import version
from pathlib import Path


def _panel_files(values: list[str], count: int) -> dict[int, Path]:
    paths: dict[int, Path] = {}
    for value in values:
        index, _, path = value.partition("=")
        if not (index.isascii() and index.isdecimal() and path):
            raise ValueError("Expected PANEL=PATH with a one-based panel number.")
        number = int(index) - 1
        if not 0 <= number < count or number in paths:
            raise ValueError("Each PANEL=PATH must identify a distinct input panel.")
        paths[number] = Path(path)
    return paths


def _run_solve(arguments: argparse.Namespace) -> tuple[dict[str, object], int]:
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    from astromosaic.astrometry.solve import SolveOptions, solve_panel, write_solution
    from astromosaic.core.job import DEFAULT_JOB_CONTEXT
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
        max_working_bytes=arguments.memory_mib * 1024**2,
        max_scratch_bytes=arguments.scratch_mib * 1024**2,
    )
    if arguments.path.suffix.lower() == ".astromosaic":
        from astromosaic.storage.project import load_project, open_project_sky_panel

        if arguments.panel is None or arguments.sky_mask is not None:
            raise ValueError("For a project, use --panel and its saved sky mask.")
        project = load_project(arguments.path)
        if not 1 <= arguments.panel <= len(project.panels):
            raise ValueError("The panel number is outside the project.")
        project_panel = project.panels[arguments.panel - 1]
        options = replace(options, optics=project_panel.optics)
        opened = open_project_sky_panel(
            project_panel, options.max_working_bytes, DEFAULT_JOB_CONTEXT
        )
    else:
        if arguments.panel is not None:
            raise ValueError("Use --panel with an AstroMosaic project.")
        opened = open_panel(
            arguments.path, max_tile_bytes=options.max_working_bytes, sky_mask=arguments.sky_mask
        )
    with opened as panel:
        solution = solve_panel(panel, options)
        report = solution.report()
        if solution.geometry is None:
            return report, 1
        if arguments.output is not None:
            write_solution(arguments.output, panel, solution)
        return report, 0


def _run_mosaic(arguments: argparse.Namespace) -> tuple[dict[str, object], int]:
    # The synchronous renderer needs no BLAS pool. Configure the CLI before native imports.
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

    from astromosaic.core import Region
    from astromosaic.pipeline.mosaic import (
        DEFAULT_OUTPUT_BYTES,
        DEFAULT_TILE_SIZE,
        DEFAULT_WORKING_BYTES,
        MIB,
        JobContext,
        RenderSpec,
        render_mosaic,
    )
    from astromosaic.pipeline.refinement import RefinementRejected, RefinementSpec

    last_interval = -1

    def report(done: int, total: int) -> None:
        nonlocal last_interval
        interval = (20 * done) // total
        if interval != last_interval:
            print(f"Rendering: {done}/{total} pixels ({(100 * done) // total}%)", file=sys.stderr)
            last_interval = interval

    spec = RenderSpec(
        center=tuple(arguments.center),
        size=tuple(arguments.size),
        scale_arcsec=arguments.scale,
        rotation_deg=arguments.rotation,
        crop=Region(*arguments.crop) if arguments.crop else None,
        tile_size=DEFAULT_TILE_SIZE if arguments.tile_size is None else arguments.tile_size,
        max_working_bytes=(
            DEFAULT_WORKING_BYTES if arguments.memory_mib is None else arguments.memory_mib * MIB
        ),
        max_output_bytes=(
            DEFAULT_OUTPUT_BYTES
            if arguments.output_limit_mib is None
            else arguments.output_limit_mib * MIB
        ),
    )
    refinement = None
    if arguments.refine:
        refinement = RefinementSpec(
            max_shift_px=6.0 if arguments.match_radius is None else arguments.match_radius,
            background=arguments.background or "offset",
        )
        if arguments.progress:
            print("Measuring sky stars and fitting overlaps.", file=sys.stderr)
    elif arguments.match_radius is not None or arguments.background is not None:
        raise ValueError("Use --refine with --match-radius or --background.")
    try:
        result = render_mosaic(
            arguments.panels,
            arguments.output,
            spec,
            weights=arguments.weights,
            filter_name=arguments.filter,
            assume_surface_brightness=arguments.assume_surface_brightness,
            sky_masks=_panel_files(arguments.sky_mask, len(arguments.panels)),
            wcs_sidecars=_panel_files(arguments.wcs, len(arguments.panels)),
            refinement=refinement,
            context=JobContext(on_progress=report if arguments.progress else None),
        )
    except RefinementRejected as error:
        return {"status": error.report.status, "refinement": asdict(error.report)}, 1
    payload = asdict(result)
    del payload["common_pixels"]
    if result.refinement is None:
        del payload["refinement"]
    return payload, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="astromosaic", description="Work with linear FITS and TIFF panels."
    )
    parser.add_argument("--version", action="version", version=version("astromosaic"))
    commands = parser.add_subparsers(dest="command", required=True)

    inspect = commands.add_parser("inspect", help="Read FITS or TIFF image metadata.")
    inspect.add_argument("path", type=Path)
    smoke = commands.add_parser("smoke", help="Run a small synthetic FITS/WCS processing job.")
    smoke.add_argument("--spawn", action="store_true", help="Run the job in a spawned worker.")
    solve = commands.add_parser("solve", help="Resolve a FITS or TIFF panel with local astrometry.")
    solve.add_argument(
        "path", type=Path, help="Linear FITS or TIFF panel, or an AstroMosaic project."
    )
    solve.add_argument("--panel", type=int, help="One-based panel number in the saved project.")
    solve.add_argument("-o", "--output", type=Path, help="Save a new JSON WCS sidecar on success.")
    solve.add_argument("--sky-mask", type=Path, help="Binary FITS sky mask in source coordinates.")
    solve.add_argument("--gaia-catalog", type=Path, help="Local Seiza Gaia DR3 catalog file.")
    solve.add_argument("--gaia-index", type=Path, help="Matching local Gaia DR3 blind index.")
    solve.add_argument("--astap", type=Path, help="Local ASTAP executable.")
    solve.add_argument("--astap-catalog", type=Path, help="Local ASTAP star catalog directory.")
    solve.add_argument("--astap-database", default="d05", choices=("d05", "d20", "d50", "d80"))
    solve.add_argument("--hint", nargs=2, type=float, metavar=("RA", "DEC"), help="ICRS degrees.")
    solve.add_argument("--scale", type=float, metavar="ARCSEC", help="Approximate pixel scale.")
    solve.add_argument(
        "--timeout", type=float, default=60, help="Solve time limit per stage, in seconds."
    )
    solve.add_argument("--memory-mib", type=int, default=64, help="Working buffer budget in MiB.")
    solve.add_argument("--scratch-mib", type=int, default=1024, help="ASTAP staging limit in MiB.")
    mosaic = commands.add_parser("mosaic", help="Render a linear mosaic with resolved WCS.")
    mosaic.add_argument(
        "panels", nargs="+", type=Path, help="Linear inputs with a common channel layout."
    )
    mosaic.add_argument(
        "-o", "--output", required=True, type=Path, help="A new FITS (mono) or TIFF output path."
    )
    mosaic.add_argument(
        "--center",
        required=True,
        type=float,
        nargs=2,
        metavar=("RA", "DEC"),
        help="ICRS tangent point in degrees.",
    )
    mosaic.add_argument(
        "--scale",
        required=True,
        type=float,
        metavar="ARCSEC",
        help="Output pixel scale in arcseconds per pixel.",
    )
    mosaic.add_argument(
        "--size",
        required=True,
        type=int,
        nargs=2,
        metavar=("WIDTH", "HEIGHT"),
        help="Uncropped output dimensions in pixels.",
    )
    mosaic.add_argument(
        "--rotation",
        type=float,
        default=0,
        metavar="DEGREES",
        help="Rotation of the positive x axis from west toward north.",
    )
    mosaic.add_argument(
        "--crop",
        type=int,
        nargs=4,
        metavar=("X", "Y", "WIDTH", "HEIGHT"),
        help="Optional zero-based crop within the output grid.",
    )
    mosaic.add_argument("--weights", type=float, nargs="+", help="Positive weights in panel order.")
    mosaic.add_argument("--filter", help="Common filter for inputs with missing FILTER metadata.")
    mosaic.add_argument(
        "--wcs",
        action="append",
        default=[],
        metavar="PANEL=PATH",
        help="Use a saved WCS sidecar for the given one-based input number.",
    )
    mosaic.add_argument(
        "--sky-mask",
        action="append",
        default=[],
        metavar="PANEL=PATH",
        help="Use a binary FITS sky mask for the given one-based input number.",
    )
    mosaic.add_argument(
        "--refine",
        action="store_true",
        help="Fit relative stellar shifts and gains for mono inputs.",
    )
    mosaic.add_argument(
        "--match-radius",
        type=float,
        metavar="PIXELS",
        help="Relative star matching radius in output pixels (6 with --refine).",
    )
    mosaic.add_argument(
        "--background",
        choices=("none", "offset", "plane"),
        help="Relative background model (offset with --refine).",
    )
    mosaic.add_argument(
        "--assume-surface-brightness",
        action="store_true",
        help="Declare a common surface-brightness scale for ambiguous BUNIT values.",
    )
    mosaic.add_argument("--tile-size", type=int, metavar="PIXELS", help="Maximum tile side (128).")
    mosaic.add_argument(
        "--memory-mib", type=int, metavar="MIB", help="Estimated working buffer budget (64 MiB)."
    )
    mosaic.add_argument(
        "--output-limit-mib", type=int, metavar="MIB", help="Maximum output file size (2048 MiB)."
    )
    mosaic.add_argument("--progress", action="store_true", help="Report tile progress to stderr.")
    arguments = parser.parse_args(argv)

    result: Mapping[str, object]
    status = 0
    try:
        if arguments.command == "inspect":
            from astromosaic.io import open_panel

            with open_panel(arguments.path) as panel:
                result = asdict(panel.descriptor)
        elif arguments.command == "mosaic":
            result, status = _run_mosaic(arguments)
        elif arguments.command == "solve":
            result, status = _run_solve(arguments)
        else:
            from astromosaic.pipeline.smoke import run_smoke

            result = run_smoke(spawn=arguments.spawn)
    except KeyboardInterrupt:
        print("astromosaic: Job interrupted.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError) as error:
        print(f"astromosaic: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return status
