"""Bound native solver calls that cannot always stop at a Python checkpoint."""

import sys
from collections.abc import Callable
from contextlib import suppress
from multiprocessing import get_context
from time import monotonic
from typing import cast

from astromosaic.core.job import JobContext

if sys.platform == "win32":
    from multiprocessing.connection import PipeConnection as ReplyConnection
else:
    from multiprocessing.connection import Connection as ReplyConnection


def _run[R](task: Callable[[], R], output: ReplyConnection) -> None:
    # The parent may close its end as a reply reaches the deadline.
    with output, suppress(BrokenPipeError):
        try:
            result = task()
        except TimeoutError as error:
            output.send(("timeout", str(error)))
        except (OSError, RuntimeError, ValueError) as error:
            output.send(("failed", error))
        else:
            output.send(("ok", result))


def run_solver_worker[R](task: Callable[[], R], seconds: float, context: JobContext) -> R:
    """Run an isolated native task and reap it on timeout or cancellation."""
    context.check_cancelled()
    spawn = get_context("spawn")
    reading, writing = spawn.Pipe(duplex=False)
    process = spawn.Process(target=_run, args=(task, writing))
    deadline = monotonic() + seconds
    try:
        process.start()
        writing.close()
        while True:
            context.check_cancelled()
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError("The native solver attempt timed out.")
            if not reading.poll(min(remaining, 0.05)):
                if not process.is_alive():
                    raise ValueError("The native solver worker exited without returning a result.")
                continue
            try:
                status, payload = reading.recv()
            except EOFError as error:
                raise ValueError(
                    "The native solver worker exited without returning a result."
                ) from error
            context.check_cancelled()
            if monotonic() >= deadline or status == "timeout":
                raise TimeoutError("The native solver attempt timed out.")
            if status == "failed":
                raise cast(Exception, payload)
            return cast(R, payload)
    finally:
        started = monotonic()
        reading.close()
        writing.close()
        if process.pid is not None:
            process.join(0.15)
            if process.is_alive():
                process.terminate()
                process.join(0.5)
            if process.is_alive():
                process.kill()
                process.join(0.5)
            if process.is_alive():
                raise RuntimeError("The native solver worker could not be reaped.")
            process.close()
        if context.on_cleanup is not None:
            context.on_cleanup(monotonic() - started)
