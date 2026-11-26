"""Check the WCS comparison on the original wide-angle owner observations."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PROJECT = _ROOT / ".tooling/desktop-0.1.0b11/final-owner-cpu/Owner.astromosaic"
_CATALOG = _ROOT / ".tooling/phase2-gaia/stars-deep-gaia17.bin"


def test_owner_wcs_candidates_keep_catalog_and_overlap_holdouts_separate() -> None:
    inputs = (_PROJECT, _CATALOG, _ROOT / "tests/20.TIF", _ROOT / "tests/21.TIF")
    if not all(path.is_file() for path in inputs) or importlib.util.find_spec("seiza") is None:
        pytest.skip(
            "Install the original photo project and local Gaia evidence from docs/phase-8.md."
        )
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.phase8_wcs_validation",
            str(_PROJECT),
            "--catalog",
            str(_CATALOG),
        ],
        cwd=_ROOT,
        env=os.environ | {"OPENBLAS_NUM_THREADS": "1"},
        capture_output=True,
        text=True,
        timeout=150,
    )
    assert run.returncode == 0, run.stderr
    report = json.loads(run.stdout)
    assert report["output_size"] == [8917, 10259]
    assert [panel["name"] for panel in report["sources"]] == ["20.TIF", "21.TIF"]
    for panel in report["sources"]:
        candidates = panel["catalog_candidates"]
        saved = candidates["saved_wcs"]["held_out_source_pixels"]
        sip3 = candidates["sip3"]["held_out_source_pixels"]
        cells = panel["held_out_matches_by_detector_cell"]
        assert panel["raw_solver_detections"] == 1500
        assert min(cells) >= 20
        assert sip3["matches"] == saved["matches"] == sum(cells)
        assert sip3["p95_px"] < saved["p95_px"]
        assert candidates["sip3"]["maximum_inverse_error_source_px"] < 1e-5

    overlap = report["overlap_candidates"]
    baseline = overlap["saved_wcs"]
    candidate = overlap["sip3"]
    assert baseline["all_matches"]["matches"] == candidate["all_matches"]["matches"] == 221
    assert baseline["held_out"]["matches"] == candidate["held_out"]["matches"] == 42
    assert sum(region["held_out_matches"] for region in candidate["regions"]) == 42
    assert baseline["held_out"]["p95_px"] == pytest.approx(0.748, abs=0.025)
    assert candidate["held_out"]["p95_px"] == pytest.approx(0.700, abs=0.025)
    assert candidate["independent_overlap_supported"]
    assert not candidate["meets_overlap_target"]
    assert not any(model["eligible"] for model in overlap.values())
