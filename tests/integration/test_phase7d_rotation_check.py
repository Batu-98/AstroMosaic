"""Check the camera-model decision using the frozen PASSTA and Adirondack captures."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_FROZEN = _ROOT / "output/application-tests/phase7a"


def test_calibrated_replay_keeps_the_rotation_candidates_outside_the_pixel_gate() -> None:
    reports = ("reference-lock.json", "passta-orientation.json", "middlebury-depth.json")
    if not all((_FROZEN / name).is_file() for name in reports):
        pytest.skip("Prepare the frozen 7A observations documented in docs/phase-7.md.")
    references = json.loads((_FROZEN / "reference-lock.json").read_bytes())
    inputs = references["controls"]
    if not all(
        (_ROOT / path).is_file()
        for group in ("passta-calibrated-panning", "middlebury-depth-change")
        for path in inputs[group]
    ):
        pytest.skip("Prepare the original PASSTA and Adirondack reference files.")

    run = subprocess.run(
        [sys.executable, str(_ROOT / "tools/phase7d_rotation_check.py")],
        capture_output=True,
        check=True,
        timeout=60,
        env=os.environ | {"OPENBLAS_NUM_THREADS": "1"},
    )
    result = json.loads(run.stdout)
    passta = result["passta"]
    assert passta["capture_ids"] == ["01", "03", "05"]
    assert not passta["rotation_passed_pixel_and_geometry_gates"]
    fixed, radial = (passta["rotation"][name] for name in ("fixed", "radial"))
    assert all(fit["within_geometry_gate"] for fit in passta["rotation"].values())
    assert fixed["independent_loop_degrees"] == pytest.approx([0.0041], abs=0.0001)
    assert fixed["alternate_anchor_max_residual_delta_px"] < 0.001
    assert fixed["held_out_p95_max_px"] == pytest.approx(6.90, abs=0.03)
    assert radial["held_out_p95_max_px"] == pytest.approx(4.13, abs=0.03)
    assert all(fit["robust_held_out_p95_max_px"] > 2 for fit in passta["rotation"].values())
    assert fixed["camera_checks"]["max_diagonal_fov_deg"] == pytest.approx(107.13, abs=0.02)
    for edge in fixed["boundary_checks"].values():
        assert edge["sampled_boundary_pixels"] == 128
        assert edge["inside_target"] > 0
        assert edge["overlapping_boundary_roundtrip_max_px"] < 0.001

    depth = result["adirondack"]
    assert not depth["global_pose_supported"]
    assert not depth["far_subset_supported"]
    zones = depth["models"]["rotation"]["1-2"]["held_out_zones"]
    assert zones["near"]["bidirectional"]["p95_px"] > 160
    assert zones["far"]["bidirectional"]["p95_px"] > 15
