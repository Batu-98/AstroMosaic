"""Protect the Advanced matching controls on the frozen real owner crop."""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[2]


def test_advanced_reference_recovers_injected_terms_and_preserves_disconnected_group() -> None:
    owner = _ROOT / "tests/20.TIF"
    if not owner.is_file():
        pytest.skip("Install the frozen owner reference documented in docs/phase-8d.md.")
    outcome = subprocess.run(
        [sys.executable, "-m", "tools.phase8d_overlap_reference", str(owner)],
        cwd=_ROOT,
        env=os.environ | {"OPENBLAS_NUM_THREADS": "1"},
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert outcome.returncode == 0, outcome.stderr
    report = json.loads(outcome.stdout)
    assert report["chain"]["scored_edges"] == [["A", "B"], ["B", "C"]]
    assert report["cycle"]["scored_edges"] == [["A", "B"], ["A", "C"], ["B", "C"]]
    for case, choice in (("chain", "standard"), ("cycle", "gain-plane")):
        result = report[case]
        assert result["selected"] == choice
        assert result["verified_order_independence"]
        assert result["components"] == [["A", "B", "C"], ["D", "E"]]
        for coefficients in result["coefficients"].values():
            assert coefficients["A"] == coefficients["D"] == coefficients["E"] == [1, 0, 0, 0]
        expected = np.asarray(result["known_coefficients"][:3])
        recovered = np.array([result["coefficients"][choice][panel] for panel in "ABC"])
        np.testing.assert_allclose(recovered[:, 0], expected[:, 0], rtol=0.01)
        np.testing.assert_allclose(recovered[:, 1:], expected[:, 1:], atol=2e-4)
        assert max(result["test_rgb_p95"][choice]) <= 3e-5
        assert result["metrics"]["covered_diffuse_test_rgb_p95"] <= 3e-5
        assert result["metrics"]["stellar_aperture_fractional_error"] <= 0.01
