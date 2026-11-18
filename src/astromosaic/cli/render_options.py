"""Render and attachment options shared by the mosaic and project commands."""

from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astromosaic.core.job import JobContext
    from astromosaic.pipeline.mosaic import RenderSpec
    from astromosaic.pipeline.refinement import RefinementSpec


def limited_render_progress(
    emit: Callable[[int, int], None] | None = None,
) -> Callable[[int, int], None]:
    """Report the first tile, each new five-percent interval and the completed tile count."""
    last_interval = -1

    def report(done: int, total: int) -> None:
        nonlocal last_interval
        interval = (20 * done) // total
        if interval == last_interval:
            return
        last_interval = interval
        if emit is not None:
            emit(done, total)
        else:
            print(
                f"Rendering: {done}/{total} pixels ({(100 * done) // total}%)",
                file=sys.stderr,
                flush=True,
            )

    return report


def with_render_reporting(
    context: JobContext, enabled: bool, emit: Callable[[int, int], None] | None = None
) -> JobContext:
    if not enabled:
        return context
    report = limited_render_progress(emit)
    progress = context.on_progress
    if progress is None:
        return replace(context, on_progress=report)

    def report_both(done: int, total: int) -> None:
        progress(done, total)
        report(done, total)

    return replace(context, on_progress=report_both)


def panel_assignments(values: list[str], count: int, kind: str) -> dict[int, str]:
    assignments: dict[int, str] = {}
    for value in values:
        index, _, assigned = value.partition("=")
        if not (index.isascii() and index.isdecimal() and assigned):
            raise ValueError(f"Expected PANEL={kind} with a one-based panel number.")
        number = int(index) - 1
        if not 0 <= number < count or number in assignments:
            raise ValueError(f"Each PANEL={kind} must identify a distinct input panel.")
        assignments[number] = assigned
    return assignments


def panel_files(values: list[str], count: int) -> dict[int, Path]:
    return {index: Path(value) for index, value in panel_assignments(values, count, "PATH").items()}


def add_render_options(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--center",
        required=True,
        type=float,
        nargs=2,
        metavar=("RA", "DEC"),
        help="ICRS reference position in degrees.",
    )
    parser.add_argument(
        "--projection",
        type=str.upper,
        choices=("TAN", "ZEA"),
        default="TAN",
        help="Sky projection, gnomonic or zenithal equal area (default: TAN).",
    )
    parser.add_argument(
        "--scale",
        required=True,
        type=float,
        metavar="ARCSEC",
        help="Output pixel scale in arcseconds per pixel.",
    )
    parser.add_argument(
        "--size",
        required=True,
        type=int,
        nargs=2,
        metavar=("WIDTH", "HEIGHT"),
        help="Uncropped output dimensions in pixels.",
    )
    parser.add_argument(
        "--rotation",
        type=float,
        default=0,
        metavar="DEGREES",
        help="Rotation of the positive x axis from west toward north.",
    )
    parser.add_argument(
        "--crop",
        type=int,
        nargs=4,
        metavar=("X", "Y", "WIDTH", "HEIGHT"),
        help="Optional zero-based crop within the output grid.",
    )
    parser.add_argument("--weights", type=float, nargs="+", help="Positive weights in panel order.")
    parser.add_argument("--filter", help="Common filter for inputs with missing FILTER metadata.")
    parser.add_argument(
        "--wcs",
        action="append",
        default=[],
        metavar="PANEL=PATH",
        help="Use a saved WCS sidecar for the given one-based input number.",
    )
    parser.add_argument(
        "--sky-mask",
        action="append",
        default=[],
        metavar="PANEL=PATH",
        help="Use a binary FITS sky mask for the given one-based input number.",
    )
    parser.add_argument(
        "--refine",
        action="store_true",
        help="Fit relative stellar shifts and gains for mono inputs.",
    )
    parser.add_argument(
        "--match-radius",
        type=float,
        metavar="PIXELS",
        help="Relative star matching radius in output pixels (6 with --refine).",
    )
    parser.add_argument(
        "--background",
        choices=("none", "offset", "plane"),
        help="Relative background model (offset with --refine).",
    )
    parser.add_argument(
        "--assume-surface-brightness",
        action="store_true",
        help="Declare a common surface-brightness scale for ambiguous BUNIT values.",
    )
    parser.add_argument("--tile-size", type=int, metavar="PIXELS", help="Maximum tile side (128).")
    parser.add_argument(
        "--memory-mib", type=int, metavar="MIB", help="Estimated working buffer budget (64 MiB)."
    )
    parser.add_argument(
        "--output-limit-mib", type=int, metavar="MIB", help="Maximum output file size (2048 MiB)."
    )


def render_options(arguments: Namespace) -> tuple[RenderSpec, RefinementSpec | None]:
    from astromosaic.core import Region
    from astromosaic.pipeline.mosaic import (
        DEFAULT_OUTPUT_BYTES,
        DEFAULT_TILE_SIZE,
        DEFAULT_WORKING_BYTES,
        MIB,
        RenderSpec,
    )
    from astromosaic.pipeline.refinement import RefinementSpec

    spec = RenderSpec(
        center=tuple(arguments.center),
        size=tuple(arguments.size),
        scale_arcsec=arguments.scale,
        rotation_deg=arguments.rotation,
        projection=arguments.projection,
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
    elif arguments.match_radius is not None or arguments.background is not None:
        raise ValueError("Use --refine with --match-radius or --background.")
    return spec, refinement
