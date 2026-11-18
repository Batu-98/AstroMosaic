"""Export a JSON list of saved AstroMosaic projects in order."""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import FrameType

_RESULT_STATUS = {0: "ok", 1: "error", 130: "cancelled"}


@dataclass(frozen=True, slots=True)
class ExportJob:
    project: Path
    output: Path
    layer: str
    band: str | None = None


def load_jobs(batch: Path) -> list[ExportJob]:
    items = json.loads(batch.read_text(encoding="utf-8-sig"))
    if not isinstance(items, list) or not items:
        raise ValueError("Expected a nonempty JSON list of export jobs.")
    directory = batch.absolute().parent
    jobs = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Job {index} must be a JSON object.")
        project, output, layer = item.get("project"), item.get("output"), item.get("layer", "sky")
        if not isinstance(project, str) or not project.strip():
            raise ValueError(f"Job {index} requires a project path.")
        if not isinstance(output, str) or not output.strip():
            raise ValueError(f"Job {index} requires an output path.")
        if not isinstance(layer, str) or layer not in ("sky", "foreground", "composition"):
            raise ValueError(f"Job {index} has an invalid layer.")
        band = item.get("band")
        if band is not None and (not isinstance(band, str) or not band.strip() or layer != "sky"):
            raise ValueError(f"Job {index} requires a nonempty band and the sky layer.")
        jobs.append(ExportJob(directory / project, directory / output, layer, band))
    return jobs


def _diagnostic(message: str) -> None:
    event = {"schema_version": 1, "event": "diagnostic", "level": "error", "message": message}
    print(json.dumps(event), file=sys.stderr, flush=True)


def run_batch(launcher: list[str], jobs: list[ExportJob]) -> int:
    interrupted = False

    def interrupt(_signum: int, _frame: FrameType | None) -> None:
        nonlocal interrupted
        interrupted = True

    signals = [signal.SIGINT]
    if sys.platform == "win32":
        signals.append(signal.SIGBREAK)
    handlers = {}
    failed = False
    try:
        for signum in signals:
            handlers[signum] = signal.signal(signum, interrupt)
        for job in jobs:
            if interrupted:
                return 130
            # The child shares the console and receives the same interrupt. Waiting
            # lets it remove the temporary export and report its final result.
            result = subprocess.run(
                [
                    *launcher,
                    "project",
                    "export",
                    str(job.project),
                    "-o",
                    str(job.output),
                    "--layer",
                    job.layer,
                    *((f"--band={job.band}",) if job.band is not None else ()),
                    "--json",
                    "--progress",
                ],
                stdout=subprocess.PIPE,
                encoding="utf-8",
                check=False,
            )
            if interrupted and not result.stdout.strip():
                return 130
            report = json.loads(result.stdout)
            expected_status = _RESULT_STATUS.get(result.returncode)
            if (
                expected_status is None
                or not isinstance(report, dict)
                or report.get("schema_version") != 1
                or report.get("command") != "project export"
                or report.get("status") != expected_status
            ):
                raise ValueError("The CLI returned an unexpected project export result.")
            print(json.dumps(report, sort_keys=True), flush=True)
            if interrupted or result.returncode == 130:
                return 130
            failed |= result.returncode != 0
    finally:
        for signum, previous in handlers.items():
            signal.signal(signum, previous)
    return int(failed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path, help="UTF-8 JSON list of saved export jobs.")
    parser.add_argument("--cli", type=Path, help="Path to the portable console executable.")
    args = parser.parse_args()
    try:
        jobs = load_jobs(args.batch)
    except (OSError, ValueError) as error:
        _diagnostic(str(error))
        return 2

    launcher = [str(args.cli.absolute())] if args.cli else [sys.executable, "-m", "astromosaic"]
    try:
        return run_batch(launcher, jobs)
    except (OSError, ValueError) as error:
        _diagnostic(f"Batch export stopped. {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
