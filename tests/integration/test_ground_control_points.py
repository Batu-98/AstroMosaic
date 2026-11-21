"""Phase 7B integration on separate real exposures and frozen terrain landmarks."""

import json
import subprocess
import sys
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import fitsio
import numpy as np
import pytest
import tifffile

from astromosaic.cli import main
from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.pipeline import layers
from astromosaic.pipeline.control_points import GroundControlPoint
from astromosaic.storage.project import (
    align_project_foreground,
    fit_project_foreground_points,
    load_project,
    propose_project_composition,
    render_project_layer,
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


def test_alpaca_saved_translation_preserves_the_legacy_fit_and_exports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _require(_ALPACA)
    context = JobContext()
    project = replace(load_project(_ALPACA), assume_surface_brightness=True)
    legacy = align_project_foreground(project, context)
    before = tmp_path / "legacy-before.fits"
    render_project_layer(legacy, "foreground", before, context)
    original = tmp_path / "legacy.astromosaic"
    save_project(original, legacy)
    manifest = original.read_bytes()
    raw = json.loads(manifest)
    assert raw["version"] == 4
    assert raw["foreground"]["alignment"]["panels"][1]["shift"] == [48, 16]
    after = tmp_path / "legacy-after.fits"
    render_project_layer(load_project(original), "foreground", after, context)
    assert before.read_bytes() == after.read_bytes()
    assert int(fitsio.read(after, ext="COVERAGE").sum()) == 80_158

    rows = _rows("alpaca")
    points = _write_points(tmp_path / "points.json", rows)
    destination = tmp_path / "translation.astromosaic"
    args = [*_args(original, points), "-o", str(destination)]
    cancelled = False

    def stop(done: int, total: int) -> None:
        nonlocal cancelled
        cancelled = done == total

    assert main(args, context=JobContext(is_cancelled=lambda: cancelled, on_progress=stop)) == 130
    assert not destination.exists()
    _write_points(points, rows[:1])
    assert main(args) == 1
    assert not destination.exists()
    _write_points(points, rows)
    assert main(args) == 0
    saved = load_project(destination)
    assert saved.foreground is not None and saved.foreground.terrain is not None
    assert saved.foreground.terrain.model == "translation"
    assert saved.current_foreground() is not None
    translation = tmp_path / "translation.fits"
    render_project_layer(saved, "foreground", translation, context)
    assert int(fitsio.read(translation, ext="COVERAGE").sum()) > 75_000
    assert main(args) == 1
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["status"] == "error"
    assert original.read_bytes() == manifest


def test_oxford_saved_similarity_samples_original_pixels_and_invalidates_edits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require(_BOAT)
    source = load_project(_BOAT)
    paths = [_BOAT, *(panel.source.path for panel in source.panels)]
    hashes = [sha256(path.read_bytes()).digest() for path in paths]
    original = tmp_path / "relative.astromosaic"
    save_project(original, replace(source, assume_surface_brightness=True))
    points = _write_points(tmp_path / "points.json", _rows("boat"))
    destination = tmp_path / "similarity.astromosaic"
    assert main([*_args(original, points), "--anchor", "2", "-o", str(destination)]) == 0
    assert json.loads(destination.read_bytes())["version"] == 7
    saved = load_project(destination)
    registration = saved.foreground
    assert registration is not None and registration.terrain is not None
    assert registration.terrain.model == "similarity"
    assert registration.terrain.held_out_p95_px == pytest.approx(1.15, abs=0.03)
    alignment = saved.current_foreground()
    assert alignment is not None and alignment.anchor == 1

    context = JobContext()
    output = tmp_path / "ground.fits"
    render_project_layer(saved, "foreground", output, context)
    assert "CTYPE1" not in fitsio.read_header(output)
    pixels = fitsio.read(output)
    coverage = fitsio.read(output, ext="COVERAGE")
    assert np.count_nonzero(coverage) > 580_000
    canvas = alignment.canvas
    y, x = np.indices(pixels.shape, dtype=np.float64)
    x += canvas.x
    y += canvas.y
    summed, counts = np.zeros_like(x), np.zeros(x.shape, dtype=np.uint8)
    for panel, transform in zip(saved.panels, alignment.panels, strict=True):
        data = tifffile.imread(panel.source.path)
        height, width = data.shape
        angle = np.deg2rad(transform.rotation_deg)
        u, v = x - transform.shift[0], y - transform.shift[1]
        sx = (np.cos(angle) * u + np.sin(angle) * v) / transform.scale
        sy = (-np.sin(angle) * u + np.cos(angle) * v) / transform.scale
        valid = (sx >= -0.5) & (sx < width - 0.5) & (sy >= -0.5) & (sy < height - 0.5)
        sx, sy = np.clip(sx[valid], 0, width - 1), np.clip(sy[valid], 0, height - 1)
        x0, y0 = sx.astype(int), sy.astype(int)
        x1, y1 = np.minimum(x0 + 1, width - 1), np.minimum(y0 + 1, height - 1)
        dx, dy = sx - x0, sy - y0
        summed[valid] += (data[y0, x0] * (1 - dx) + data[y0, x1] * dx) * (1 - dy) + (
            data[y1, x0] * (1 - dx) + data[y1, x1] * dx
        ) * dy
        counts[valid] += 1
    valid = counts > 0
    np.testing.assert_array_equal(coverage, valid)
    np.testing.assert_allclose(pixels[valid], summed[valid] / counts[valid], rtol=1e-6, atol=1e-7)
    assert np.isnan(pixels[~valid]).all()

    monkeypatch.setattr(layers, "_footprint_reservation", lambda panels, budget: 0)
    unpruned = tmp_path / "unpruned.fits"
    render_project_layer(saved, "foreground", unpruned, context)
    assert output.read_bytes() == unpruned.read_bytes()
    cancelled = tmp_path / "cancelled.fits"
    with pytest.raises(MosaicCancelled):
        render_project_layer(saved, "foreground", cancelled, JobContext(is_cancelled=lambda: True))
    assert not cancelled.exists()
    edited = replace(registration.terrain, points=registration.terrain.points[:-1])
    assert (
        replace(saved, foreground=replace(registration, terrain=edited)).current_foreground()
        is None
    )
    first, second = saved.panels
    assert first.source_mask is not None
    mask = first.source_mask
    changed_mask = replace(mask, labels=b"\x00" + mask.labels[1:])
    assert (
        replace(
            saved, panels=(replace(first, source_mask=changed_mask), second)
        ).current_foreground()
        is None
    )
    assert [sha256(path.read_bytes()).digest() for path in paths] == hashes


def test_paranal_control_point_placement_retains_the_independent_sky(tmp_path: Path) -> None:
    case = _DATA / "mix02-paranal/project.astromosaic"
    _require(case)
    original = load_project(case)
    # Both crops come from the same real panorama. Their origins differ by 510 px in X.
    rows = [
        {"id": f"{x}-{y}", "panels": [1, 2], "left_xy": [x, y], "right_xy": [x - 510, y]}
        for x, y in ((610, 848), (690, 878), (780, 894), (970, 875), (1010, 892))
    ]
    points = _write_points(tmp_path / "points.json", rows)
    context = JobContext()
    sky_before = tmp_path / "sky-before.tiff"
    render_project_layer(original, "sky", sky_before, context)
    destination = tmp_path / "paranal.astromosaic"
    assert main([*_args(case, points), "--anchor", "2", "-o", str(destination)]) == 0
    saved = load_project(destination)
    sky_after = tmp_path / "sky-after.tiff"
    render_project_layer(saved, "sky", sky_after, context)
    assert sky_before.read_bytes() == sky_after.read_bytes()
    placement = propose_project_composition(saved, context)
    assert placement.placement_rms_px is not None and placement.placement_rms_px < 1
    output = tmp_path / "composition.tiff"
    render_project_layer(replace(saved, composition=placement), "composition", output, context)
    with tifffile.TiffFile(output) as tiff:
        page = tiff.pages[0]
        pages = page.pages
        assert pages is not None
        coverage = pages[0].asarray()
        contributions = pages[1].asarray()
        assert set(np.unique(contributions)) >= {0, 1, 2}
        np.testing.assert_array_equal(coverage != 0, contributions != 0)


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


def test_disabled_terrain_observation_is_preserved_without_influencing_the_fit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _require(_BOAT)
    rows = _rows("boat")
    wrong = rows[0] | {
        "id": "disabled mismatched landmark",
        "right_xy": rows[1]["right_xy"],
        "enabled": False,
    }
    evidence = _write_points(tmp_path / "points.json", rows)
    args = [*_args(_BOAT, evidence), "--anchor", "2"]
    assert main(args) == 0
    original = json.loads(capsys.readouterr().out)["fit"]
    _write_points(evidence, [*rows, wrong])
    output = tmp_path / "reviewed.astromosaic"
    assert main([*args, "-o", str(output)]) == 0
    edited = json.loads(capsys.readouterr().out)["fit"]
    assert edited["poses"] == original["poses"] and edited["edges"] == original["edges"]
    assert edited["points"][-1]["status"] == "disabled"
    assert json.loads(output.read_bytes())["version"] == 8
    project = load_project(output)
    assert project.current_foreground() is not None
    terrain = project.reviewable_terrain()
    assert terrain is not None and not terrain.points[-1].enabled


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
