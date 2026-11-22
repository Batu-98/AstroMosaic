"""Protect the Advanced matching controls on the frozen real owner crop."""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from tools.phase8d_overlap_reference import PanelSamples, measure

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


def test_calibrated_comparison_recovers_background_without_changing_gain() -> None:
    y, x = np.mgrid[0:256:4, 0:384:4].reshape(2, -1)
    xy = np.column_stack((2 * x / 383 - 1, 2 * y / 255 - 1))
    signal = 0.025 + 0.009 * np.sin(x / 13) * np.cos(y / 21)
    rgb = signal[:, None] * np.array([0.9, 1.0, 1.1])
    truth = np.array([[0.0, 0.0, 0.0], [0.002, -0.008, 0.004], [-0.001, 0.004, -0.005]])
    panels = [
        PanelSamples(name, rgb - (offset + xy @ np.array([dx, dy]))[:, None], xy)
        for name, (offset, dx, dy) in zip("ABC", truth, strict=True)
    ]
    result = measure(panels, x, y, preserve_calibrated_scale=True)
    assert result == measure(panels[::-1], x, y, preserve_calibrated_scale=True)
    assert result["fixed_gain_selected"] == "fixed-gain-plane"
    models = result["coefficients"]
    assert isinstance(models, dict)
    measured = np.asarray(list(models["fixed-gain-plane"].values()))
    np.testing.assert_array_equal(measured[:, 0], 1.0)
    np.testing.assert_allclose(measured[:, 1:], truth, atol=1e-12, rtol=0)
