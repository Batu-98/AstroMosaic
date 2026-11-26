"""Replay the Phase 8 overlap measurements on real sky observations."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PROJECT = _ROOT / ".tooling/desktop-0.1.0b11/final-owner-cpu/Owner.astromosaic"
_PHOTO = _ROOT / "output/phase8b13/Photo-mosaic-preserved-transparent.tiff"
_ORIGINALS = (_ROOT / "tests/20.TIF", _ROOT / "tests/21.TIF")
_ALPACA = _ROOT / "output/application-tests/phase6b-work/alpaca-mixed/mixed.astromosaic"


def _measure(*paths: Path) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(_ROOT / "tools/phase8_photo_overlap.py"), *map(str, paths)],
        cwd=_ROOT,
        env=os.environ | {"OPENBLAS_NUM_THREADS": "1"},
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr
    return cast(dict[str, Any], json.loads(result.stdout))


def test_owner_photo_overlap_reports_held_out_alignment_and_both_panel_edges() -> None:
    if not all(path.is_file() for path in (_PROJECT, _PHOTO, *_ORIGINALS)):
        pytest.skip("Prepare the frozen photo project and export documented in docs/phase-8.md.")

    report = _measure(_PROJECT, _PHOTO)
    assert report["size"] == [8917, 10259]
    reference = report["preserve_tone_reference"]
    assert reference["sampled_pixels"] == 9951
    assert reference["covered_pixels"] == 4764
    assert reference["max_rgb_error"] <= 2

    alignment = report["alignment"]
    assert alignment["unclipped_matches"] > 200
    assert alignment["candidates"] > alignment["unclipped_matches"]
    assert alignment["held_out_matches"] > 50
    assert alignment["held_out"]["p95_px"] == pytest.approx(0.751, abs=0.025)
    assert alignment["held_out_with_translation"]["p95_px"] == pytest.approx(0.662, abs=0.025)
    assert not alignment["translation_meets_geometry_target"]

    spatial = alignment["spatial_holdout"]
    assert spatial["status"] == "complete"
    assert spatial["all"]["compared_matches"] == alignment["unclipped_matches"]
    assert spatial["outer_either_detector"]["matches"] >= 150
    p95_by_model = [
        spatial["all"][name]["p95_px"] for name in ("saved_wcs", "translation", "similarity")
    ]
    assert p95_by_model == pytest.approx([0.692, 0.713, 0.757], abs=0.025)
    assert p95_by_model[0] < min(p95_by_model[1:])
    supported = [block for block in spatial["blocks"] if block["saved_wcs"] is not None]
    worst_block = max(supported, key=lambda block: block["saved_wcs"]["p95_px"])
    assert (worst_block["row"], worst_block["column"]) == (0, 2)
    assert worst_block["saved_wcs"]["p95_px"] == pytest.approx(0.941, abs=0.025)

    background = report["background"]
    assert background["paired_coverage_samples"] == 1001
    assert 670 <= background["paired_background_samples"] <= 720
    left, right = report["edge_steps_in_panel_order"]
    assert left["left"]["strips"] >= 70
    assert right["right"]["strips"] >= 50
    assert right["right"]["median_added_step_linear_y"] == pytest.approx(0.00301, abs=0.0002)


def test_alpaca_archive_control_retains_its_saved_alignment_in_outer_regions() -> None:
    if not _ALPACA.is_file():
        pytest.skip("Prepare the calibrated ALPACA project documented in docs/phase-6.md.")

    report = _measure(_ALPACA)
    assert report["size"] == [586, 550]
    assert "preserve_tone_reference" not in report
    spatial = report["alignment"]["spatial_holdout"]
    assert spatial["status"] == "complete"
    assert spatial["all"]["compared_matches"] == 30
    edge = spatial["outer_either_detector"]
    assert edge["compared_matches"] == 18
    p95_by_model = [edge[name]["p95_px"] for name in ("saved_wcs", "translation", "similarity")]
    assert p95_by_model == pytest.approx([0.209, 0.213, 0.223], abs=0.01)
    assert sum(block["compared_matches"] for block in spatial["blocks"]) == 30
    assert any(block["matches"] < 5 and block["saved_wcs"] is None for block in spatial["blocks"])
