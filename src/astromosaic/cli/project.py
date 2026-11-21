"""Create, prepare and export saved projects through the headless CLI."""

from __future__ import annotations

import json
import logging
import signal
import sys
import warnings
from argparse import ArgumentParser, Namespace
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import asdict, replace
from pathlib import Path
from tempfile import mkdtemp
from threading import current_thread, main_thread
from types import FrameType
from typing import TYPE_CHECKING, TextIO

from astromosaic.cli.ground_points import add_fit_command, fit_project_points
from astromosaic.cli.render_options import (
    add_render_options,
    panel_assignments,
    panel_files,
    render_options,
    with_render_reporting,
)
from astromosaic.cli.solve_options import add_solve_options, solve_options

if TYPE_CHECKING:
    from astromosaic.core.job import JobContext
    from astromosaic.core.masks import SourceMask
    from astromosaic.storage.project import MosaicProject

_REPORT_VERSION = 1


def add_project_commands(parser: ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="project_command", required=True)
    create = commands.add_parser("create", help="Save a new project from panel paths.")
    create.add_argument("panels", nargs="+", type=Path, help="Linear FITS, TIFF, or XISF panels.")
    create.add_argument(
        "-o", "--output", required=True, type=Path, help="A new .astromosaic project path."
    )
    add_render_options(create)
    create.add_argument(
        "--panel-band",
        action="append",
        default=[],
        metavar="PANEL=FILTER",
        help="Save an explicit filter label for the given one-based panel number.",
    )
    create.add_argument(
        "--label-mask",
        action="append",
        default=[],
        metavar="PANEL=PATH",
        help="Import a mono editor-grid mask with labels 0 unclassified, 1 sky, 2 foreground.",
    )
    create.add_argument(
        "--foreground-only",
        type=int,
        action="append",
        default=[],
        metavar="PANEL",
        help="Exclude this labeled panel from sky processing.",
    )
    relink = commands.add_parser("relink", help="Relink moved sources and save a project copy.")
    relink.add_argument(
        "--panel",
        action="append",
        required=True,
        metavar="PANEL=PATH",
        help="Relink the given one-based panel to a file with the saved fingerprint.",
    )
    solve = commands.add_parser("solve", help="Plate solve in a saved project and save a copy.")
    solve.add_argument(
        "--panel", type=int, action="append", default=[], help="Limit to this one-based sky panel."
    )
    solve.add_argument("--progress", action="store_true", help="Report completed panel counts.")
    add_solve_options(solve)
    align = commands.add_parser("align-foreground", help="Align saved foreground masks in a copy.")
    place = commands.add_parser(
        "propose-placement", help="Save a shared horizon placement in a copy."
    )
    set_placement = commands.add_parser("set-placement", help="Save numeric composition settings.")
    set_placement.add_argument("--offset", nargs=2, required=True, type=float, metavar=("X", "Y"))
    set_placement.add_argument("--seam", required=True, type=float, metavar="ROW")
    set_placement.add_argument("--rotation", type=float, default=0)
    set_placement.add_argument("--scale", type=float, default=1)
    set_placement.add_argument("--overlap", type=float, default=10, metavar="PERCENT")
    set_placement.add_argument("--crop-bottom", type=int, default=0, metavar="ROWS")
    for command in (relink, solve, align, place, set_placement):
        command.add_argument("path", type=Path, help="Saved .astromosaic project.")
        command.add_argument(
            "-o", "--output", required=True, type=Path, help="A new .astromosaic project path."
        )
    bands = commands.add_parser("bands", help="List the bands and sky panels in a saved project.")
    bands.add_argument("path", type=Path, help="Saved .astromosaic project.")
    validate = commands.add_parser("validate", help="Check a saved project's sky layer.")
    validate.add_argument("path", type=Path, help="Saved .astromosaic project.")
    validate.add_argument(
        "-o", "--output", type=Path, help="Check a proposed FITS, TIFF, or XISF output path."
    )
    export = commands.add_parser("export", help="Render a saved project layer.")
    export.add_argument("path", type=Path, help="Saved .astromosaic project.")
    export.add_argument(
        "-o", "--output", required=True, type=Path, help="A new FITS (mono), TIFF, or XISF path."
    )
    export.add_argument(
        "--layer",
        choices=("sky", "foreground", "composition"),
        default="sky",
        help="Saved layer to render (default: sky).",
    )
    export.add_argument("--progress", action="store_true", help="Report tile progress to stderr.")
    for command in (validate, export):
        command.add_argument("--band", metavar="FILTER", help="Select one saved sky band.")
    fit = commands.add_parser(
        "fit-foreground", help="Fit terrain control points and optionally save the alignment."
    )
    add_fit_command(fit)
    for command in (
        create,
        relink,
        solve,
        align,
        place,
        set_placement,
        bands,
        validate,
        export,
        fit,
    ):
        command.add_argument("--json", action="store_true", help="Emit a versioned JSON result.")


def _label_mask(path: Path, panel: Path, budget: int, context: JobContext) -> SourceMask:
    import numpy as np

    from astromosaic.core import Region
    from astromosaic.core.masks import (
        FOREGROUND,
        MASK_EDGE,
        SKY,
        UNCLASSIFIED,
        SourceMask,
        bounded_grid,
    )
    from astromosaic.io import open_panel

    with open_panel(panel, max_tile_bytes=budget) as source:
        source_size = (source.descriptor.width, source.descriptor.height)
    width, height = bounded_grid(source_size, MASK_EDGE)
    with open_panel(path, max_tile_bytes=budget) as mask:
        descriptor = mask.descriptor
        if descriptor.channel_layout != "mono" or (descriptor.width, descriptor.height) != (
            width,
            height,
        ):
            raise ValueError(f"Expected a mono label mask with {width} x {height} editor cells.")
        context.check_cancelled()
        tile = mask.read_tile(Region(0, 0, width, height))
        if not tile.valid.all() or not np.isin(tile.pixels, (UNCLASSIFIED, SKY, FOREGROUND)).all():
            raise ValueError("Label masks require valid samples with values 0, 1 or 2.")
        return SourceMask(source_size, tile.pixels.astype(np.uint8).tobytes())


def _create(arguments: Namespace, context: JobContext) -> int:
    from astromosaic.astrometry.solve import load_solution
    from astromosaic.core.masks import FOREGROUND
    from astromosaic.storage.project import (
        FileReference,
        MosaicProject,
        ProjectPanel,
        open_project_sky_panel,
        save_project,
    )

    spec, refinement = render_options(arguments)
    paths: list[Path] = arguments.panels
    weights = [1.0] * len(paths) if arguments.weights is None else arguments.weights
    if len(weights) != len(paths):
        raise ValueError("Supply one positive finite weight per input panel.")
    masks = panel_files(arguments.sky_mask, len(paths))
    labels = panel_files(arguments.label_mask, len(paths))
    solutions = panel_files(arguments.wcs, len(paths))
    bands = panel_assignments(arguments.panel_band, len(paths), "FILTER")
    ground_only = {number - 1 for number in arguments.foreground_only}
    if ground_only.difference(labels):
        raise ValueError("Each --foreground-only panel needs a --label-mask.")
    if masks.keys() & labels.keys():
        raise ValueError("Choose one mask input per panel.")
    panels = []
    for index, (path, weight) in enumerate(zip(paths, weights, strict=True)):
        context.check_cancelled()
        reference = FileReference.capture(path)
        label = (
            _label_mask(labels[index], path, spec.max_working_bytes, context)
            if index in labels
            else None
        )
        if index in ground_only and (label is None or FOREGROUND not in label.labels):
            raise ValueError("A foreground-only panel needs foreground cells in its label mask.")
        panel = ProjectPanel(
            source=reference,
            weight=weight,
            sky_mask=FileReference.capture(masks[index]) if index in masks else None,
            wcs_sidecar=FileReference.capture(solutions[index]) if index in solutions else None,
            foreground_override="sky-only" if label is None else "mixed",
            source_mask=label,
            include_sky=index not in ground_only,
            band_override=bands[index].strip() if index in bands else None,
        )
        with open_project_sky_panel(panel, spec.max_working_bytes, context) as source:
            if panel.wcs_sidecar is not None:
                load_solution(panel.wcs_sidecar.path, source)
        panels.append(panel)
    project = MosaicProject(
        tuple(panels), spec, arguments.filter, arguments.assume_surface_brightness, refinement
    )
    save_project(arguments.output, project, context=context)
    return len(panels)


def _solve_copy(
    project: MosaicProject, arguments: Namespace, result: dict[str, object], context: JobContext
) -> str:
    from astromosaic.astrometry.solve_budget import SolveBudget, SolveBudgetExceeded
    from astromosaic.storage.project import panels_needing_wcs, save_project, solve_project_panel

    options = solve_options(arguments)
    batch = (
        SolveBudget.begin(options.job_seconds, scope="job")
        if options.job_seconds is not None
        else None
    )
    job = context if batch is None else batch.context(context)
    sky = project.sky_indices()
    selected = tuple(number - 1 for number in arguments.panel) if arguments.panel else sky
    if not selected:
        raise ValueError("The project has no sky panels to solve.")
    if len(set(selected)) != len(selected) or any(index not in sky for index in selected):
        raise ValueError("Each --panel must identify a distinct sky panel in the project.")
    if options.revalidate or options.strict_edges:
        indices = selected
    else:
        pending = set(panels_needing_wcs(project, job))
        indices = tuple(index for index in selected if index in pending)
    reused = [index + 1 for index in selected if index not in indices]
    outcomes: list[dict[str, object]] = []
    result.update(panels=len(selected), reused=reused, outcomes=outcomes)

    def report_progress(completed: int) -> None:
        if arguments.progress and arguments.json:
            _write_event(
                "progress", stage="solve", completed_panels=completed, total_panels=len(indices)
            )
        elif arguments.progress:
            print(f"Plate solve: {completed}/{len(indices)} panels", file=sys.stderr, flush=True)

    job.check_cancelled()
    destination: Path = arguments.output
    panels = list(project.panels)
    # Each run owns its sidecar directory so interrupted work and concurrent copies stay separate.
    directory = (
        Path(mkdtemp(prefix="astromosaic-wcs-", dir=destination.absolute().parent))
        if indices
        else None
    )
    published = False
    failed = 0
    try:
        if directory is not None:
            report_progress(0)
            for index in indices:
                job.check_cancelled()
                outcome = solve_project_panel(
                    index, panels[index], options, directory, job, job_budget=batch
                )
                outcomes.append(
                    {
                        "panel": index + 1,
                        "status": outcome.status,
                        "stage": outcome.stage,
                        "message": outcome.error,
                        "budget": outcome.budget,
                        "quality": outcome.quality,
                        "attempts": [
                            {
                                key: value
                                for key, value in asdict(attempt).items()
                                if key != "catalog_regions"
                            }
                            for attempt in outcome.attempts
                        ],
                    }
                )
                if outcome.sidecar is None:
                    failed += 1
                else:
                    panels[index] = replace(panels[index], wcs_sidecar=outcome.sidecar)
                report_progress(len(outcomes))
                if batch is not None and outcome.status == "budget-exhausted":
                    batch.check()
                    if outcome.budget is not None and outcome.budget["limiting_scope"] == "job":
                        raise SolveBudgetExceeded(outcome.error or "The job solve budget elapsed.")
        if failed:
            job.check_cancelled()
            raise ValueError(f"Plate solve failed for {failed} panel(s). See the panel outcomes.")
        for index in selected:
            job.check_cancelled()
            for role, reference in panels[index].references():
                if reference.status() != "Ready":
                    raise ValueError(f"{role} changed during the solve: {reference.path.name}")
        save_project(destination, replace(project, panels=tuple(panels)), context=job)
        published = True
    finally:
        if directory is not None and not published:
            for path in directory.glob("panel-*.wcs.json"):
                path.unlink()
            directory.rmdir()
    return f"Saved project copy with {len(outcomes)} new and {len(reused)} reused WCS solution(s)."


def _prepare_copy(arguments: Namespace, result: dict[str, object], job: JobContext) -> str:
    from astromosaic.geometry.image import CompositionSpec, LayerPlacement
    from astromosaic.storage.project import (
        align_project_foreground,
        load_project,
        propose_project_composition,
        save_project,
        validate_composition,
    )

    destination: Path = arguments.output
    result["output"] = str(destination)
    if destination.suffix.lower() != ".astromosaic":
        raise ValueError("The project filename must end in .astromosaic.")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"The output file already exists: {destination}")
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"The output directory does not exist: {destination.parent}")
    job.check_cancelled()
    project = load_project(arguments.path)
    action = arguments.project_command
    if action == "solve":
        return _solve_copy(project, arguments, result, job)
    if action == "relink":
        paths = panel_files(arguments.panel, len(project.panels))
        for index, path in paths.items():
            job.check_cancelled()
            project = project.relink_panel(index, path)
        result["relinked"] = [index + 1 for index in paths]
        message = f"Relinked {len(paths)} panel(s)."
    elif action == "align-foreground":
        project = align_project_foreground(project, replace(job, on_progress=None))
        assert project.foreground is not None
        alignment = project.foreground.alignment
        result.update(panels=len(alignment.panels), overlaps=len(alignment.overlaps))
        message = f"Aligned {len(alignment.panels)} foreground panel(s)."
    else:
        if action == "propose-placement":
            placement = propose_project_composition(project, job)
            message = "Proposed a shared horizon placement."
        else:
            placement = CompositionSpec(
                LayerPlacement(tuple(arguments.offset), arguments.rotation, arguments.scale),
                arguments.seam,
                arguments.overlap,
                arguments.crop_bottom,
            )
            validate_composition(project, placement)
            message = "Set the composition placement."
        project = replace(project, composition=placement)
        result["placement"] = asdict(placement)
    save_project(destination, project, context=job)
    return f"{message} Saved project copy."


def _write_event(event: str, **fields: object) -> None:
    payload = {"schema_version": _REPORT_VERSION, "event": event, **fields}
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)


def _diagnostic(level: str, message: str) -> None:
    _write_event("diagnostic", level=level, message=message)


def _json_warning(
    message: Warning | str,
    category: type[Warning],
    filename: str,
    lineno: int,
    file: TextIO | None = None,
    line: str | None = None,
) -> None:
    _diagnostic("warning", f"{category.__name__}: {message}")


class _DiagnosticHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _diagnostic(record.levelname.lower(), record.getMessage().strip())


@contextmanager
def _json_diagnostics() -> Iterator[None]:
    from astropy import log

    # Astropy's default handler writes WCS informational messages to stdout.
    handlers, propagate = log.handlers, log.propagate
    log.handlers, log.propagate = [_DiagnosticHandler()], False
    try:
        with warnings.catch_warnings():
            warnings.showwarning = _json_warning
            yield
    finally:
        log.handlers, log.propagate = handlers, propagate


def _render_progress_event(done: int, total: int) -> None:
    _write_event("progress", stage="render", completed_pixels=done, total_pixels=total)


def _foreground_progress(done: int, total: int, json_output: bool) -> None:
    if json_output:
        _write_event("progress", stage="foreground-fit", completed=done, total=total)
    else:
        print(f"Foreground fit: {done}/{total}", file=sys.stderr, flush=True)


@contextmanager
def _interruptible_context() -> Iterator[JobContext]:
    from astromosaic.core.job import DEFAULT_JOB_CONTEXT, JobContext

    if current_thread() is not main_thread():
        yield DEFAULT_JOB_CONTEXT
        return

    interrupted = False

    def request_cancellation(_signum: int, _frame: FrameType | None) -> None:
        nonlocal interrupted
        interrupted = True

    # Let the job finish its cleanup even when the console sends repeated signals.
    signals = [signal.SIGINT]
    if sys.platform == "win32":
        signals.append(signal.SIGBREAK)
    handlers = {}
    try:
        for signum in signals:
            handlers[signum] = signal.signal(signum, request_cancellation)
        yield JobContext(is_cancelled=lambda: interrupted)
    finally:
        for signum, handler in handlers.items():
            signal.signal(signum, handler)


def _export(arguments: Namespace, result: dict[str, object], context: JobContext) -> str:
    from astromosaic.pipeline.refinement import RefinementRejected
    from astromosaic.storage.project import load_project, render_project_layer

    result.update(layer=arguments.layer, output=str(arguments.output))
    band = arguments.band.strip() if arguments.band is not None else None
    if band is not None:
        result["band"] = band
    reporter = _render_progress_event if arguments.json else None
    job = with_render_reporting(context, arguments.progress, reporter)
    job.check_cancelled()
    project = load_project(arguments.path)
    job.check_cancelled()
    try:
        mosaic = render_project_layer(project, arguments.layer, arguments.output, job, band=band)
    except RefinementRejected as error:
        result["refinement"] = asdict(error.report)
        raise
    result.update(asdict(mosaic))
    label = f"sky band {band!r}" if band is not None else f"{arguments.layer} layer"
    return f"Exported {label} with {mosaic.width} x {mosaic.height} pixels."


def run_project(arguments: Namespace, *, context: JobContext | None = None) -> int:
    from astromosaic.core.job import MosaicCancelled

    action = arguments.project_command
    path = arguments.output if action == "create" else arguments.path
    result: dict[str, object] = {
        "schema_version": _REPORT_VERSION,
        "command": f"project {action}",
        "status": "ok",
        "project": str(path),
    }
    exit_code = 0
    with (
        _json_diagnostics() if arguments.json else nullcontext(),
        _interruptible_context() if context is None else nullcontext(context) as job,
    ):
        try:
            if action == "create":
                job.check_cancelled()
                count = _create(arguments, job)
                result["panels"] = count
                message = f"Created project with {count} panel(s)."
            elif action == "bands":
                from astromosaic.storage.project import load_project, project_sky_bands

                job.check_cancelled()
                bands = project_sky_bands(load_project(path), job)
                job.check_cancelled()
                result["bands"] = [
                    {"band": label, "panels": [index + 1 for index in indices]}
                    for label, indices in bands.items()
                ]
                message = "\n".join(
                    f"{label} ({len(indices)} panels)" for label, indices in bands.items()
                )
            elif action == "validate":
                from astromosaic.storage.project import load_project, validate_project_sky

                job.check_cancelled()
                project = load_project(path)
                band = arguments.band.strip() if arguments.band is not None else None
                if band is not None:
                    result["band"] = band
                sky = validate_project_sky(project, job, arguments.output, band=band)
                job.check_cancelled()
                result.update(
                    layer="sky",
                    panels=sky.panels,
                    width=sky.width,
                    height=sky.height,
                    channels=sky.channels,
                )
                message = (
                    f"Validated {sky.panels} sky panel(s) for {sky.width} x {sky.height} pixels."
                )
            elif action == "fit-foreground":
                fit_job = with_render_reporting(
                    job,
                    arguments.progress,
                    lambda done, total: _foreground_progress(done, total, arguments.json),
                )
                message = fit_project_points(arguments, result, fit_job)
            elif action in {
                "relink",
                "solve",
                "align-foreground",
                "propose-placement",
                "set-placement",
            }:
                message = _prepare_copy(arguments, result, job)
            else:
                message = _export(arguments, result, job)
        except (KeyboardInterrupt, MosaicCancelled):
            result["status"] = "cancelled"
            message = "Job interrupted."
            exit_code = 130
        except (OSError, RuntimeError, ValueError, OverflowError) as error:
            result["status"] = "error"
            message = str(error)
            exit_code = 1

    if exit_code:
        result["message"] = message
        if arguments.json:
            _diagnostic("error", message)
        else:
            print(f"astromosaic: {message}", file=sys.stderr)
    if arguments.json:
        print(json.dumps(result, sort_keys=True))
    elif exit_code == 0:
        print(message)
    return exit_code
