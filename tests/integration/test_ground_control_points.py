"""Phase 7B integration on separate real exposures and frozen terrain landmarks."""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from astromosaic.cli import main
from astromosaic.core.job import JobContext
from astromosaic.pipeline.control_points import GroundControlPoint
from astromosaic.storage.project import (
    align_project_foreground,
    fit_project_foreground_points,
    load_project,
    save_project,
)

_ROOT = Path(__file__).resolve().parents[2]
_DATA = _ROOT / "data/application-tests"
_EVIDENCE = _ROOT / "output/application-tests/phase7a"
_ALPACA = _DATA / "phase6a-alpaca/positive.astromosaic"
_BOAT = _DATA / "phase7a/oxford-affine/foreground.astromosaic"
_ADIRONDACK = _DATA / "phase7a/middlebury-adirondack/foreground.astromosaic"
_BOAT_THREE = _BOAT.with_name("foreground-three.astromosaic")
_BOAT_THREE_POINTS = _EVIDENCE.parent / "phase7b/boat-three-points.json"


def _require(*paths: Path) -> None:
    if not all(path.is_file() for path in paths):
        pytest.skip("Prepare the real-observation references documented in docs/phase-7.md.")


def _rows(name: str) -> list[dict[str, Any]]:
    report = {
        "alpaca": "landmark-comparison-checked.json",
        "boat": "oxford-boat.json",
        "adirondack": "middlebury-depth.json",
    }[name]
    path = _EVIDENCE / report
    _require(path)
    data = json.loads(path.read_bytes())
    if name == "alpaca":
        return [
            {
                "id": r["id"],
                "panels": [1, 2],
                "left_xy": r["reference_xy"],
                "right_xy": r["primary"]["moving_xy"],
                "held_out": r["split"] == "held-out",
            }
            for r in data["measurements"]["alpaca-a-b"]
            if r["usable"]
        ]
    return [
        {
            "id": r["id"],
            "panels": [1, 2],
            "left_xy": r["xy"] if name == "boat" else r["left_xy"],
            "right_xy": r["primary"]["moving_xy"],
            "held_out": r["split"] == "held-out",
        }
        for r in data["marks"]
        if r["use" if name == "boat" else "used"]
    ]


def _write_points(path: Path, points: list[dict[str, Any]]) -> Path:
    path.write_text(json.dumps({"schema_version": 1, "points": points}), encoding="utf-8")
    return path


def _args(project: Path, points: Path) -> list[str]:
    return ["project", "fit-foreground", str(project), "--points", str(points), "--json"]


def test_alpaca_translation_and_cancel_leave_legacy_registration_available(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _require(_ALPACA)
    aligned = align_project_foreground(load_project(_ALPACA), JobContext())
    project = tmp_path / "control.astromosaic"
    save_project(project, aligned)
    original = project.read_bytes()
    rows = _rows("alpaca")
    raw = json.loads((_EVIDENCE / "landmark-comparison-checked.json").read_bytes())
    excluded = next(r for r in raw["measurements"]["alpaca-a-b"] if r["id"] == "enclosure-6")
    extra = {
        "id": "excluded landmark",
        "panels": [1, 2],
        "left_xy": excluded["reference_xy"],
        "right_xy": excluded["primary"]["moving_xy"],
    }
    duplicate = rows[0] | {"id": "duplicate landmark"}
    points = _write_points(tmp_path / "points.json", [*rows, extra, duplicate])
    args = _args(project, points)

    progress: list[tuple[int, int]] = []
    context = JobContext(
        is_cancelled=lambda: bool(progress),
        on_progress=lambda done, total: progress.append((done, total)),
    )
    assert main(args, context=context) == 130
    assert progress == [(1, len(rows) + 3)]
    assert json.loads(capsys.readouterr().out)["status"] == "cancelled"
    assert project.read_bytes() == original
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    assert capsys.readouterr().out == first
    fit = json.loads(first)["fit"]
    assert fit["anchor"] == 1 and fit["model"] == "translation"
    assert fit["groups"] == [[1, 2]]
    assert fit["poses"][0]["shift"] == [0, 0]
    np.testing.assert_allclose(fit["poses"][1]["shift"], [48, 16], atol=1.5, rtol=0)
    assert fit["edges"][0]["held_out_p95_px"] <= 2
    assert fit["edges"][0]["inliers"] == 5
    assert fit["points"][-2]["status"] == "outside-valid-ground"
    assert fit["points"][-1]["status"] == "duplicate-correspondence"
    _write_points(points, rows[:1])
    assert main(args) == 1
    assert json.loads(capsys.readouterr().out)["fit"]["status"] == "disconnected"
    assert project.read_bytes() == original
    assert load_project(project).current_foreground() == aligned.current_foreground()


def test_real_boat_similarity_is_headless_and_ignores_wrong_training_match(
    tmp_path: Path,
) -> None:
    _require(_BOAT)
    rows = _rows("boat")
    training = [row for row in rows if not row["held_out"]]
    outlier = training[0] | {"right_xy": training[-1]["right_xy"]}
    rows[rows.index(training[0])] = outlier
    points = _write_points(tmp_path / "points.json", rows)
    original = _BOAT.read_bytes()
    script = """
import sys

class NoQt:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('PySide', 'PyQt')):
            raise AssertionError(fullname)

sys.meta_path.insert(0, NoQt())
from astromosaic.cli import main
raise SystemExit(main(sys.argv[1:]))
"""
    process = subprocess.run(
        [sys.executable, "-c", script, *_args(_BOAT, points)],
        check=True,
        capture_output=True,
        encoding="utf-8",
        timeout=60,
    )
    fit = json.loads(process.stdout)["fit"]
    assert process.stderr == ""
    assert fit["model"] == "similarity" and fit["status"] == "accepted"
    assert fit["poses"][1]["scale"] == pytest.approx(1 / 0.88191, abs=0.005)
    assert fit["poses"][1]["rotation_deg"] == pytest.approx(14.01, abs=0.2)
    assert fit["edges"][0]["held_out_p95_px"] <= 2
    assert fit["edges"][0]["inliers"] == 9
    point = next(row for row in fit["points"] if row["id"] == outlier["id"])
    assert point["status"] == "outlier" and point["residual_basis"] == "anchored"
    assert point["forward_error_px"] > 2
    assert _BOAT.read_bytes() == original


def test_depth_change_rejects_far_only_fit_and_reports_the_held_out_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _require(_ADIRONDACK)
    points = _write_points(tmp_path / "points.json", _rows("adirondack"))
    original = _ADIRONDACK.read_bytes()
    assert main(_args(_ADIRONDACK, points)) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "error"
    assert report["fit"]["status"] == "disconnected"
    assert report["fit"]["groups"] == [[1], [2]]
    assert report["fit"]["poses"] == []
    assert report["fit"]["edges"][0]["status"] == "held-out-error"
    assert report["fit"]["edges"][0]["held_out_p95_px"] > 100
    assert _ADIRONDACK.read_bytes() == original


def test_three_real_boat_views_refine_a_redundant_graph_with_an_explicit_anchor(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _require(_BOAT_THREE, _BOAT_THREE_POINTS)
    args = [*_args(_BOAT_THREE, _BOAT_THREE_POINTS), "--anchor", "2"]
    assert main(args) == 0
    fit = json.loads(capsys.readouterr().out)["fit"]
    assert fit["model"] == "similarity" and fit["anchor"] == 2
    assert fit["groups"] == [[1, 2, 3]]
    assert fit["poses"][1] == {"panel": 2, "rotation_deg": 0, "scale": 1, "shift": [0, 0]}
    assert fit["poses"][0]["rotation_deg"] == pytest.approx(-14.01, abs=0.2)
    assert fit["poses"][2]["rotation_deg"] == pytest.approx(25.75, abs=0.2)
    assert len(fit["edges"]) == 3
    assert all(row["status"] == "accepted" and row["held_out_p95_px"] <= 2 for row in fit["edges"])


def test_underconstrained_and_nonfinite_real_correspondences_are_reported() -> None:
    _require(_ALPACA)
    project = load_project(_ALPACA)
    row = _rows("alpaca")[0]
    valid = GroundControlPoint("landmark", (0, 1), tuple(row["left_xy"]), tuple(row["right_xy"]))
    nonfinite = replace(valid, id="nonfinite", right_xy=(float("nan"), valid.right_xy[1]))
    report = fit_project_foreground_points(
        project, (valid, nonfinite), JobContext(), model="similarity"
    )
    assert report.status == "disconnected" and report.groups == ((0,), (1,))
    assert report.poses == () and report.edges[0].status == "insufficient-points"
    assert [row.status for row in report.points] == ["insufficient-points", "nonfinite-position"]


def test_inconsistent_cycle_between_real_boat_views_rejects_the_anchored_fit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _require(_BOAT_THREE, _BOAT_THREE_POINTS)
    rows = json.loads(_BOAT_THREE_POINTS.read_bytes())["points"]
    # Assign one set of real landmarks to the wrong project panel. It fits
    # that pair alone but conflicts with the correctly assigned third edge.
    first_edge = [r for r in rows if r["panels"] == [1, 2]]
    wrong_edge = [r | {"id": "wrong-" + r["id"], "panels": [1, 3]} for r in first_edge]
    loop = [r for r in rows if r["panels"] != [1, 3]] + wrong_edge
    points = _write_points(tmp_path / "points.json", loop)
    assert main([*_args(_BOAT_THREE, points), "--model", "similarity"]) == 1
    fit = json.loads(capsys.readouterr().out)["fit"]
    assert fit["status"] == "graph-disagreement"
    assert fit["groups"] == [[1, 2, 3]]
    assert fit["poses"] == []
    assert any(row["status"] == "graph-disagreement" for row in fit["edges"])
