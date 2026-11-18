"""Entry point for running the CLI in an isolated desktop worker process."""

from __future__ import annotations

import os
from contextlib import redirect_stderr, redirect_stdout
from io import TextIOBase
from threading import Lock
from typing import TYPE_CHECKING

from astromosaic.cli import main
from astromosaic.cli.render_options import limited_render_progress

if TYPE_CHECKING:
    from multiprocessing.connection import Connection
    from multiprocessing.synchronize import Event
    from pathlib import Path


class _CommandOutput(TextIOBase):
    encoding = "utf-8"

    def __init__(self, connection: Connection) -> None:
        super().__init__()
        self._connection = connection
        self._pending = ""
        self._lock = Lock()

    def writable(self) -> bool:
        return True

    def write(self, text: str, /) -> int:
        with self._lock:
            self._pending += text
            if "\n" in text:
                self._connection.send(self._pending)
                self._pending = ""
        return len(text)

    def flush(self) -> None:
        with self._lock:
            if self._pending:
                self._connection.send(self._pending)
                self._pending = ""

    def progress(self, done: int, total: int) -> None:
        with self._lock:
            self._connection.send((done, total))


def run_command(argv: list[str], directory: Path, output: Connection, cancelled: Event) -> None:
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    with output, _CommandOutput(output) as stream:
        with redirect_stdout(stream), redirect_stderr(stream):
            try:
                os.chdir(directory)
                from astromosaic.core.job import JobContext

                job = JobContext(cancelled.is_set, limited_render_progress(stream.progress))
                status = main(argv, context=job)
            except Exception as error:
                print(f"astromosaic: {error}")
                status = 1
    raise SystemExit(status)
