from functools import partial
from multiprocessing import get_context
from pathlib import Path
from time import monotonic, sleep

import numpy as np
import pytest
from astropy.io import fits

from astromosaic.astrometry import solve
from astromosaic.astrometry.astap_probe import AstapCandidate
from astromosaic.astrometry.solve_budget import SolveBudget, SolveBudgetExceeded
from astromosaic.astrometry.solver_worker import _run, run_solver_worker
from astromosaic.core import Region
from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.geometry import tan_output_wcs
from astromosaic.io import open_panel
from astromosaic.io.atomic import atomic_binary_file


def test_batch_deadline_spans_panel_preparation_and_searches() -> None:
    now = [100.0]
    job = SolveBudget.begin(70, scope="job", clock=lambda: now[0])
    now[0] += 8
    first = SolveBudget.begin(120, parent=job)
    assert first.search_seconds("astap-hinted", 60) == 20
    assert first.search_seconds("astap-blind", 60) == 25
    assert first.search_seconds("astap-blind", 60, astap_only=True) == 52
    assert first.search_seconds("gaia-blind", 18) == 18
    now[0] += 50
    second = SolveBudget.begin(120, parent=job)
    assert second.search_seconds("astap-blind", 60) == 2
    now[0] += 3
    with pytest.raises(SolveBudgetExceeded, match="validation reserve"):
        second.search_seconds("gaia-blind", 30)
    now[0] += 10
    with pytest.raises(SolveBudgetExceeded, match="job"):
        second.context(JobContext()).check_cancelled()
    assert second.report()["overrun_seconds"] == 1


def test_late_candidate_does_not_start_validation_or_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stub_solve_evidence: None,
) -> None:
    size = (32, 24)
    header = tan_output_wcs((250, 36), size, 2, 0, Region(0, 0, *size)).to_header()
    source = tmp_path / "unsolved.fits"
    fits.writeto(source, np.ones(size[::-1], dtype=np.float32))
    now = [0.0]
    budget = SolveBudget.begin(40, clock=lambda: now[0])
    calls = []

    def late_astap(*args: object, **kwargs: object) -> AstapCandidate:
        calls.append(kwargs["position"])
        now[0] = 41
        return AstapCandidate(header, "test", "d05")

    monkeypatch.setattr(solve, "solve_astap", late_astap)
    monkeypatch.setattr(solve, "_validate_astap", lambda *args: pytest.fail("Validated late WCS"))
    options = solve.SolveOptions(
        astap=tmp_path / "astap.exe", astap_catalog=tmp_path, position=(250, 36)
    )
    with open_panel(source) as opened:
        result = solve.solve_panel(opened, options, budget=budget)
    assert result.geometry is None and result.outcome == "budget-exhausted"
    assert calls == [(250, 36)]


def test_deadline_at_publication_removes_only_new_sidecar(tmp_path: Path) -> None:
    published = tmp_path / "late.wcs.json"
    earlier = tmp_path / "earlier.wcs.json"
    earlier.write_bytes(b"previous WCS")
    now = [0.0]
    budget = SolveBudget.begin(10, clock=lambda: now[0])

    def check() -> None:
        if published.exists():
            now[0] = 10
        budget.check()

    with (
        pytest.raises(SolveBudgetExceeded),
        atomic_binary_file(published, publish_check=check) as out,
    ):
        out.write(b"new WCS")
    assert not published.exists() and not list(tmp_path.glob("*.part"))
    assert earlier.read_bytes() == b"previous WCS"


@pytest.mark.parametrize("cancel", [False, True])
def test_nonresponsive_native_task_is_reaped(cancel: bool) -> None:
    started = monotonic()
    context = JobContext(is_cancelled=lambda: cancel and monotonic() - started >= 0.7)
    expected = MosaicCancelled if cancel else TimeoutError
    with pytest.raises(expected):
        run_solver_worker(partial(sleep, 20), 0.9, context)
    assert monotonic() - started < 2.0


def test_timeout_reply_can_race_with_parent_closing_the_pipe() -> None:
    reading, writing = get_context("spawn").Pipe(duplex=False)
    reading.close()

    def native_timeout() -> None:
        raise TimeoutError("Native deadline reached.")

    _run(native_timeout, writing)
    assert writing.closed
