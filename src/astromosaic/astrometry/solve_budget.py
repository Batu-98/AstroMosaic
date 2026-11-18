"""Monotonic budgets shared by panel preparation, searching and publication."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from math import isfinite
from time import monotonic

from astromosaic.core.job import JobContext

DEFAULT_PANEL_SECONDS = 120.0
VALIDATION_RESERVE_SECONDS = 10.0
CLEANUP_ALLOWANCE_SECONDS = 5.0
SEARCH_CAPS = {"astap-hinted": 20.0, "astap-blind": 25.0, "gaia-hinted": 20.0, "gaia-blind": 30.0}
ASTAP_ONLY_BLIND_CAP_SECONDS = 60.0


class SolveBudgetExceeded(RuntimeError):
    """The remaining panel or batch budget does not permit more solve work."""


@dataclass(slots=True)
class SolveBudget:
    requested_seconds: float
    start: float
    deadline: float
    scope: str
    clock: Callable[[], float]
    cleanup_seconds: float = 0.0

    @classmethod
    def begin(
        cls,
        seconds: float,
        *,
        scope: str = "panel",
        parent: "SolveBudget | None" = None,
        clock: Callable[[], float] = monotonic,
    ) -> "SolveBudget":
        if not isfinite(seconds) or seconds <= 0:
            raise ValueError(f"The {scope} solve budget must be positive and finite.")
        if parent is not None:
            clock = parent.clock
        now = clock()
        deadline = now + seconds
        if parent is not None and parent.deadline <= deadline:
            deadline, scope = parent.deadline, parent.scope
        return cls(seconds, now, deadline, scope, clock)

    def remaining(self) -> float:
        return max(0.0, self.deadline - self.clock())

    def check(self) -> None:
        if self.remaining() <= 0:
            raise SolveBudgetExceeded(f"The {self.scope} solve budget elapsed.")

    def search_seconds(
        self, stage: str, attempt_limit: float, *, astap_only: bool = False
    ) -> float:
        remaining = self.remaining() - VALIDATION_RESERVE_SECONDS
        if remaining <= 0:
            raise SolveBudgetExceeded(
                f"The {self.scope} solve budget has no search time after the validation reserve."
            )
        cap = (
            ASTAP_ONLY_BLIND_CAP_SECONDS
            if stage == "astap-blind" and astap_only
            else SEARCH_CAPS[stage]
        )
        return min(remaining, attempt_limit, cap)

    def _record_cleanup(self, seconds: float) -> None:
        self.cleanup_seconds += seconds

    def context(self, context: JobContext) -> JobContext:
        return replace(context, checkpoint=self.check, on_cleanup=self._record_cleanup)

    def report(self) -> dict[str, object]:
        now = self.clock()
        overrun = max(0.0, now - self.deadline)
        return {
            "requested_seconds": self.requested_seconds,
            "effective_seconds": max(0.0, self.deadline - self.start),
            "limiting_scope": self.scope,
            "elapsed_seconds": now - self.start,
            "remaining_seconds": max(0.0, self.deadline - now),
            "cleanup_seconds": self.cleanup_seconds,
            "overrun_seconds": overrun,
            "cleanup_allowance_exceeded": overrun > CLEANUP_ALLOWANCE_SECONDS,
        }
