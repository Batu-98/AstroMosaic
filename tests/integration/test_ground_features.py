"""Phase 7C checks on real terrain observations and frozen independent points."""

import json
from dataclasses import asdict, replace
from itertools import product
from math import ceil, floor
from pathlib import Path
from types import ModuleType

import pytest

from astromosaic.cli import main
from astromosaic.core.job import JobContext
from astromosaic.core.masks import SourceMask, grid_cells
from astromosaic.pipeline import ground_features
from astromosaic.pipeline.control_points import GroundControlPoint
from astromosaic.storage.project import (
    fit_project_foreground_features,
    fit_project_foreground_points,
    load_project,
)

_ROOT = Path(__file__).resolve().parents[2]
_DATA = _ROOT / "data/application-tests"
_EVIDENCE = _ROOT / "output/application-tests/phase7b"
_ALPACA = _DATA / "phase6a-alpaca/positive.astromosaic"
_DISJOINT = _ALPACA.with_name("negative.astromosaic")
_BOAT = _DATA / "phase7a/oxford-affine/foreground-three.astromosaic"
_LASILLA = _DATA / "phase7a/eso-lasilla/foreground.astromosaic"
_ADIRONDACK = _DATA / "phase7a/middlebury-adirondack/foreground.astromosaic"


def _require(*paths: Path) -> None:
    if not all(path.is_file() for path in paths):
        pytest.skip("Prepare the local real-observation references in docs/phase-7.md.")


def _observations(name: str) -> tuple[GroundControlPoint, ...]:
    path = _EVIDENCE / f"{name}-points.json"
    _require(path)
    rows = json.loads(path.read_bytes())["points"]
    return tuple(
        GroundControlPoint(
            row["id"],
            (row["panels"][0] - 1, row["panels"][1] - 1),
            tuple(row["left_xy"]),
            tuple(row["right_xy"]),
            row["held_out"],
        )
        for row in rows
    )


def _audit(name: str) -> tuple[GroundControlPoint, ...]:
    return tuple(point for point in _observations(name) if point.held_out)


def test_automatic_oxford_fit_replays_after_cancel_and_accepts_unordered_views(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _require(_BOAT)
    pytest.importorskip("cv2")
    holdouts = _audit("boat-three")
    path = tmp_path / "audit.json"
    rows = [asdict(row) | {"panels": [n + 1 for n in row.panels]} for row in holdouts]
    path.write_text(json.dumps({"schema_version": 1, "points": rows}), encoding="utf-8")
    args = [
        "project",
        "fit-foreground",
        str(_BOAT),
        "--automatic",
        "--holdout",
        str(path),
        "--anchor",
        "2",
        "--json",
    ]
    original = _BOAT.read_bytes()
    progress: list[tuple[int, int]] = []
    job = JobContext(
        is_cancelled=lambda: bool(progress),
        on_progress=lambda done, total: progress.append((done, total)),
    )
    assert main(args, context=job) == 130
    assert json.loads(capsys.readouterr().out)["status"] == "cancelled"
    assert progress == [(1, 7)]

    assert main(args) == 0
    first = capsys.readouterr().out
    assert main([*args, "--progress"]) == 0
    final = capsys.readouterr()
    assert final.out == first
    updates = [json.loads(line) for line in final.err.splitlines()]
    assert [event["completed"] for event in updates] == list(range(1, 8))
    assert all(event["stage"] == "foreground-fit" and event["total"] == 7 for event in updates)
    replay = json.loads(first)
    fit, matching = replay["fit"], replay["matching"]
    assert fit["model"] == "similarity" and fit["groups"] == [[1, 2, 3]]
    assert all(e["status"] == "accepted" and e["held_out_p95_px"] <= 2 for e in fit["edges"])
    assert all(e["inliers"] >= 8 for e in fit["edges"])
    assert matching["reserved_peak_bytes"] <= load_project(_BOAT).render.max_working_bytes
    assert all(0 < p["outside_footprint"] and p["features"] <= 512 for p in matching["panels"])
    assert all(p["patch_trials"] <= 64 and p["submitted"] <= 32 for p in matching["pairs"])
    for point in matching["points"]:
        for row in rows:
            for i, key in enumerate(("left_xy", "right_xy")):
                for j, other in enumerate(("left_xy", "right_xy")):
                    if point["panels"][i] == row["panels"][j]:
                        assert abs(complex(*point[key]) - complex(*row[other])) > 24
    assert _BOAT.read_bytes() == original

    project = load_project(_BOAT)
    order = (2, 0, 1)
    shuffled = replace(project, panels=tuple(project.panels[index] for index in order))
    remapped = tuple(
        replace(p, panels=(order.index(p.panels[0]), order.index(p.panels[1]))) for p in holdouts
    )
    result = fit_project_foreground_features(shuffled, JobContext(), holdouts=remapped, anchor=2)
    assert result.fit.status == "accepted" and result.fit.groups == ((0, 1, 2),)
    assert len(result.fit.edges) == 3
    assert all(
        edge.held_out_p95_px is not None and edge.held_out_p95_px <= 2 for edge in result.fit.edges
    )


def test_real_nightscape_keeps_fixed_viewpoint_with_audited_ground_only() -> None:
    _require(_LASILLA)
    pytest.importorskip("cv2")
    result = fit_project_foreground_features(
        load_project(_LASILLA), JobContext(), holdouts=_audit("lasilla")
    )
    assert result.fit.status == "accepted" and result.fit.model == "translation"
    assert max(abs(x) for x in result.fit.poses[1].shift) < 0.25
    edge = result.fit.edges[0]
    assert edge.held_out_p95_px is not None and edge.held_out_p95_px <= 2
    assert any(panel.near_audit > 0 for panel in result.panels)


def test_real_depth_conflict_and_disjoint_group_produce_no_false_links() -> None:
    _require(_ALPACA, _DISJOINT, _ADIRONDACK)
    pytest.importorskip("cv2")
    depth = fit_project_foreground_features(
        load_project(_ADIRONDACK), JobContext(), holdouts=_audit("adirondack")
    )
    assert depth.fit.status == "disconnected" and depth.fit.groups == ((0,), (1,))
    pair = depth.pairs[0]
    assert pair.status == "no-coherent-model" and pair.mutual_matches >= 8
    assert pair.coarse_inliers < 0.60 * pair.mutual_matches and pair.submitted == 0

    connected = load_project(_ALPACA)
    disjoint = load_project(_DISJOINT)
    project = replace(connected, panels=(*connected.panels, disjoint.panels[1]))
    result = fit_project_foreground_features(project, JobContext())
    assert result.fit.status == "disconnected" and result.fit.groups == ((0, 1), (2,))
    assert [link.panels for link in result.fit.edges if link.status == "accepted"] == [(0, 1)]
    assert all(link.submitted == 0 for link in result.pairs if 2 in link.panels)


def test_manual_points_recover_sparse_real_ground_support() -> None:
    _require(_ALPACA)
    pytest.importorskip("cv2")
    observations = _observations("alpaca")
    project = load_project(_ALPACA)
    panels = []
    for index, panel in enumerate(project.panels):
        mask = panel.source_mask
        assert mask is not None
        labels = mask.grid()
        reduced = labels.copy()
        reduced.fill(0)
        width, height = mask.size
        for point in observations:
            x, y = point.left_xy if index == 0 else point.right_xy
            for col, row in product(range(floor(x), ceil(x) + 1), range(floor(y), ceil(y) + 1)):
                c = int(grid_cells(col, col + 1, mask.source_size[0], width)[0])
                r = int(grid_cells(row, row + 1, mask.source_size[1], height)[0])
                reduced[r - 1 : r + 2, c - 1 : c + 2] = labels[r - 1 : r + 2, c - 1 : c + 2]
        panels.append(replace(panel, source_mask=SourceMask(mask.source_size, reduced.tobytes())))
    restricted = replace(project, panels=tuple(panels))
    automatic = fit_project_foreground_features(restricted, JobContext())
    assert automatic.fit.status == "disconnected"
    assert automatic.pairs[0].status == "insufficient-features"
    manual = fit_project_foreground_points(restricted, observations, JobContext())
    assert manual.status == "accepted" and manual.model == "translation"
    held_out = manual.edges[0].held_out_p95_px
    assert held_out is not None and held_out <= 2


def test_optional_backend_failure_leaves_the_manual_cli_available(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _require(_ALPACA, _EVIDENCE / "alpaca-points.json")

    def missing(name: str) -> ModuleType:
        raise ImportError(name)

    monkeypatch.setattr(ground_features, "import_module", missing)
    args = ["project", "fit-foreground", str(_ALPACA), "--json"]
    assert main([*args, "--automatic"]) == 1
    message = json.loads(capsys.readouterr().out)["message"]
    assert "optional OpenCV SIFT backend" in message and "--points" in message
    assert main([*args, "--points", str(_EVIDENCE / "alpaca-points.json")]) == 0
    assert json.loads(capsys.readouterr().out)["fit"]["status"] == "accepted"
