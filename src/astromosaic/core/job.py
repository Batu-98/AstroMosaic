"""Cancellation and progress shared by headless jobs."""

from collections.abc import Callable
from dataclasses import dataclass


class MosaicCancelled(RuntimeError):
    """The job was cancelled before publishing its result."""


@dataclass(frozen=True, slots=True)
class JobContext:
    is_cancelled: Callable[[], bool] | None = None
    on_progress: Callable[[int, int], None] | None = None

    def check_cancelled(self) -> None:
        if self.is_cancelled is not None and self.is_cancelled():
            raise MosaicCancelled("The job was cancelled.")


DEFAULT_JOB_CONTEXT = JobContext()
