"""Headless command-line interface."""

import argparse
import json
import os
import sys
from collections.abc import Mapping
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path


def _run_mosaic(arguments: argparse.Namespace) -> dict[str, object]:
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
    return asdict(
        render_mosaic(
            arguments.panels,
            arguments.output,
            spec,
            weights=arguments.weights,
            filter_name=arguments.filter,
            assume_surface_brightness=arguments.assume_surface_brightness,
            context=JobContext(on_progress=report if arguments.progress else None),
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="astromosaic", description="Work with linear FITS panels."
    )
    parser.add_argument("--version", action="version", version=version("astromosaic"))
    commands = parser.add_subparsers(dest="command", required=True)

    inspect = commands.add_parser("inspect", help="Read primary FITS image metadata.")
    inspect.add_argument("path", type=Path)
    smoke = commands.add_parser("smoke", help="Run a small synthetic FITS/WCS processing job.")
    smoke.add_argument("--spawn", action="store_true", help="Run the job in a spawned worker.")
    mosaic = commands.add_parser("mosaic", help="Render a linear FITS mosaic using existing WCS.")
    mosaic.add_argument("panels", nargs="+", type=Path, help="Calibrated monochrome FITS inputs.")
    mosaic.add_argument("-o", "--output", required=True, type=Path, help="A new FITS output path.")
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
        "--assume-surface-brightness",
        action="store_true",
        help="Declare a common surface-brightness scale for ambiguous BUNIT values.",
    )
    mosaic.add_argument("--tile-size", type=int, metavar="PIXELS", help="Maximum tile side (128).")
    mosaic.add_argument(
        "--memory-mib", type=int, metavar="MIB", help="Estimated working buffer budget (64 MiB)."
    )
    mosaic.add_argument(
        "--output-limit-mib", type=int, metavar="MIB", help="Maximum FITS file size (2048 MiB)."
    )
    mosaic.add_argument("--progress", action="store_true", help="Report tile progress to stderr.")
    arguments = parser.parse_args(argv)

    result: Mapping[str, object]
    try:
        if arguments.command == "inspect":
            from astromosaic.io.fits import open_fits_panel

            with open_fits_panel(arguments.path) as panel:
                result = asdict(panel.descriptor)
        elif arguments.command == "mosaic":
            result = _run_mosaic(arguments)
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
    return 0
