"""Create, check and export saved projects through the headless CLI."""

from __future__ import annotations

import json
import logging
import signal
import sys
import warnings
from argparse import ArgumentParser, Namespace
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import asdict
from pathlib import Path
from threading import current_thread, main_thread
from types import FrameType
from typing import TYPE_CHECKING, TextIO

from astromosaic.cli.render_options import (
    add_render_options,
    panel_files,
    render_options,
    with_render_reporting,
)

if TYPE_CHECKING:
    from astromosaic.core.job import JobContext

_REPORT_VERSION = 1


def add_project_commands(parser: ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="project_command", required=True)
    create = commands.add_parser("create", help="Save a new sky project.")
    create.add_argument("panels", nargs="+", type=Path, help="Linear FITS or TIFF input panels.")
    create.add_argument(
        "-o", "--output", required=True, type=Path, help="A new .astromosaic project path."
    )
    add_render_options(create)
    validate = commands.add_parser("validate", help="Check a saved project's sky layer.")
    validate.add_argument("path", type=Path, help="Saved .astromosaic project.")
    validate.add_argument(
        "-o", "--output", type=Path, help="Check a proposed FITS or TIFF output path."
    )
    export = commands.add_parser("export", help="Render a saved project layer.")
    export.add_argument("path", type=Path, help="Saved .astromosaic project.")
    export.add_argument(
        "-o", "--output", required=True, type=Path, help="A new FITS (mono) or TIFF output path."
    )
    export.add_argument(
        "--layer",
        choices=("sky", "foreground", "composition"),
        default="sky",
        help="Saved layer to render (default: sky).",
    )
    export.add_argument("--progress", action="store_true", help="Report tile progress to stderr.")
    for command in (create, validate, export):
        command.add_argument("--json", action="store_true", help="Emit a versioned JSON result.")


def _create(arguments: Namespace, context: JobContext) -> int:
    from astromosaic.astrometry.solve import load_solution
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
    solutions = panel_files(arguments.wcs, len(paths))
    panels = []
    for index, (path, weight) in enumerate(zip(paths, weights, strict=True)):
        context.check_cancelled()
        panel = ProjectPanel(
            source=FileReference.capture(path),
            weight=weight,
            sky_mask=FileReference.capture(masks[index]) if index in masks else None,
            wcs_sidecar=FileReference.capture(solutions[index]) if index in solutions else None,
            foreground_override="sky-only",
        )
        with open_project_sky_panel(panel, spec.max_working_bytes, context) as source:
            if panel.wcs_sidecar is not None:
                load_solution(panel.wcs_sidecar.path, source)
        panels.append(panel)
    project = MosaicProject(
        tuple(panels), spec, arguments.filter, arguments.assume_surface_brightness, refinement
    )
    context.check_cancelled()
    save_project(arguments.output, project)
    return len(panels)


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


@contextmanager
def _export_context() -> Iterator[JobContext]:
    from astromosaic.core.job import DEFAULT_JOB_CONTEXT, JobContext

    if current_thread() is not main_thread():
        yield DEFAULT_JOB_CONTEXT
        return

    interrupted = False

    def request_cancellation(_signum: int, _frame: FrameType | None) -> None:
        nonlocal interrupted
        interrupted = True

    # Let the renderer finish its cleanup even when the console sends repeated signals.
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


def _export(arguments: Namespace, result: dict[str, object], context: JobContext | None) -> str:
    from astromosaic.pipeline.refinement import RefinementRejected
    from astromosaic.storage.project import load_project, render_project_layer

    result.update(layer=arguments.layer, output=str(arguments.output))
    reporter = _render_progress_event if arguments.json else None
    with _export_context() if context is None else nullcontext(context) as job:
        job = with_render_reporting(job, arguments.progress, reporter)
        job.check_cancelled()
        project = load_project(arguments.path)
        job.check_cancelled()
        try:
            mosaic = render_project_layer(project, arguments.layer, arguments.output, job)
        except RefinementRejected as error:
            result["refinement"] = asdict(error.report)
            raise
    result.update(asdict(mosaic))
    return f"Exported {arguments.layer} layer with {mosaic.width} x {mosaic.height} pixels."


def run_project(arguments: Namespace, *, context: JobContext | None = None) -> int:
    from astromosaic.core.job import DEFAULT_JOB_CONTEXT, MosaicCancelled

    action = arguments.project_command
    path = arguments.output if action == "create" else arguments.path
    result: dict[str, object] = {
        "schema_version": _REPORT_VERSION,
        "command": f"project {action}",
        "status": "ok",
        "project": str(path),
    }
    job = context or DEFAULT_JOB_CONTEXT
    exit_code = 0
    with _json_diagnostics() if arguments.json else nullcontext():
        try:
            if action == "create":
                job.check_cancelled()
                count = _create(arguments, job)
                result["panels"] = count
                message = f"Created project with {count} panel(s)."
            elif action == "validate":
                from astromosaic.storage.project import load_project, validate_project_sky

                job.check_cancelled()
                project = load_project(path)
                sky = validate_project_sky(project, job, arguments.output)
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
            else:
                message = _export(arguments, result, context)
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
