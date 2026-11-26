"""Phase 7F regressions on the frozen real foreground observations."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from dataclasses import replace
from hashlib import file_digest
from pathlib import Path
from time import monotonic, sleep
from typing import TYPE_CHECKING, Any

import fitsio
import numpy as np
import pytest
import tifffile

from astromosaic.core.job import JobContext
from astromosaic.core.masks import UNCLASSIFIED
from astromosaic.pipeline.control_points import XY, GroundControlPoint
from astromosaic.pipeline.foreground import ForegroundAlignmentRejected
from astromosaic.storage.project import (
    align_project_foreground,
    apply_project_ground_fit,
    fit_project_foreground_points,
    load_project,
    render_project_layer,
    save_project,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.project_window import ProjectWindow
    from astromosaic.ui.terrain_editor import TerrainPointEditor
    from astromosaic.ui.terrain_view import TerrainView

_ROOT = Path(__file__).resolve().parents[2]
_DATA = _ROOT / "data/application-tests"
_EVIDENCE = _ROOT / "output/application-tests"
_BOAT = _DATA / "phase7a/oxford-affine/foreground.astromosaic"
_MIXED = _DATA / "mix02-paranal/project.astromosaic"
_ALPACA = _DATA / "phase6a-alpaca/positive.astromosaic"
_LASILLA = _DATA / "phase7a/eso-lasilla/foreground.astromosaic"
_ADIRONDACK = _DATA / "phase7a/middlebury-adirondack/foreground.astromosaic"
_PA4 = _DATA / "owner01-pa4/foreground-check.astromosaic"


def _require(*paths: Path) -> None:
    if not all(path.is_file() for path in paths):
        pytest.skip("Prepare the real-observation references documented in docs/phase-7.md.")


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def _xy(values: list[float]) -> XY:
    return values[0], values[1]


def _observations(case: str) -> list[GroundControlPoint]:
    path = _EVIDENCE / f"phase7b/{case}-points.json"
    _require(path)
    return [
        GroundControlPoint(
            row["id"],
            (row["panels"][0] - 1, row["panels"][1] - 1),
            _xy(row["left_xy"]),
            _xy(row["right_xy"]),
            row["held_out"],
        )
        for row in json.loads(path.read_bytes())["points"]
    ]


def _wait(app: QApplication, condition: Callable[[], bool]) -> None:
    deadline = monotonic() + 45
    while not condition():
        assert monotonic() < deadline, "Timed out waiting for the desktop operation."
        app.processEvents()
        sleep(0.005)
    app.processEvents()


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> QApplication:
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


@pytest.fixture
def window(app: QApplication, tmp_path: Path) -> Iterator[ProjectWindow]:
    from PySide6.QtCore import QEvent, QSettings

    from astromosaic.ui.project_window import ProjectWindow

    previous = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)
    window = ProjectWindow(
        use_gpu=os.environ.get("ASTROMOSAIC_TEST_OPENGL") == "1",
        preferences=QSettings(str(tmp_path / "editor.ini"), QSettings.Format.IniFormat),
    )
    secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
    if secondary is not None:
        window.move(secondary.availableGeometry().center() - window.rect().center())
    window.show()
    try:
        yield window
    finally:
        window._saved = window.project
        window.close()
        _wait(app, lambda: not window.isVisible())
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.setQuitOnLastWindowClosed(previous)


def _review(
    app: QApplication, window: ProjectWindow, interaction: Callable[[TerrainPointEditor], None]
) -> None:
    from PySide6.QtCore import QTimer

    from astromosaic.ui.terrain_editor import TerrainPointEditor

    errors: list[BaseException] = []
    called = False

    def interact() -> None:
        nonlocal called
        dialog = app.activeModalWidget()
        try:
            assert isinstance(dialog, TerrainPointEditor)
            called = True
            secondary = next((s for s in app.screens() if s != app.primaryScreen()), None)
            assert secondary is None or dialog.screen() == secondary
            interaction(dialog)
        except BaseException as error:
            errors.append(error)
        finally:
            if isinstance(dialog, TerrainPointEditor) and dialog.isVisible():
                dialog.reject()

    assert window.review_points_action.isEnabled()
    QTimer.singleShot(0, interact)
    window.review_points_action.trigger()
    if errors:
        raise errors[0]
    assert called


def _click_image(view: TerrainView, xy: XY, *, detail: bool = False) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    scene = view.scene_position(xy)
    assert scene is not None
    position = view.mapFromScene(scene)
    assert view.viewport().rect().contains(position)
    button = Qt.MouseButton.RightButton if detail else Qt.MouseButton.LeftButton
    QTest.mouseClick(view.viewport(), button, pos=position)


def _enable_flag(dialog: TerrainPointEditor, row: int, column: int, enabled: bool) -> None:
    from PySide6.QtCore import Qt

    value = Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
    assert dialog.point_model.setData(
        dialog.point_model.index(row, column), value, Qt.ItemDataRole.CheckStateRole
    )


def _enter_points(
    app: QApplication, dialog: TerrainPointEditor, points: list[GroundControlPoint]
) -> None:
    for point in points:
        for panel, selector in zip(point.panels, dialog.selectors, strict=True):
            selector.setCurrentIndex(dialog._panels.index(panel))
            _wait(app, lambda: dialog._job is None)
        assert dialog.add_pair.isEnabled(), dialog.status.text()
        dialog.add_pair.click()
        dialog.views[0].picked.emit(point.left_xy)
        dialog.views[1].picked.emit(point.right_xy)
        if point.held_out:
            _enable_flag(dialog, dialog.points_table.currentIndex().row(), 2, True)


def _export(
    app: QApplication, window: ProjectWindow, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QFileDialog

    with monkeypatch.context() as patch:
        patch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(path), ""))
        window.start_button.click()
    _wait(app, lambda: window.job is None)
    assert window.status.text().startswith(f"Saved {path.name}"), window.status.text()


def test_oxford_editor_adds_moves_disables_and_reopens_real_pairs(
    app: QApplication, window: ProjectWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require(_BOAT)
    measurements = _observations("boat")
    new, *seed = measurements
    context = JobContext()
    project = replace(load_project(_BOAT), assume_surface_brightness=True)
    originals = {_BOAT: _digest(_BOAT)}
    originals.update({panel.source.path: _digest(panel.source.path) for panel in project.panels})
    with pytest.raises(ForegroundAlignmentRejected):
        align_project_foreground(project, context)
    fit = fit_project_foreground_points(project, seed, context, model="similarity", anchor=1)
    saved = apply_project_ground_fit(project, fit, seed, "manual", context)
    path = tmp_path / "Oxford Boat.astromosaic"
    save_project(path, saved)
    assert json.loads(path.read_bytes())["version"] == 7
    before = _digest(path)
    window._open_project(path)

    def edit(dialog: TerrainPointEditor) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        _wait(app, lambda: dialog._job is None)
        assert dialog.model.currentText() == "Similarity"
        assert dialog.anchor.currentIndex() == 1
        assert dialog.point_model.rowCount() == len(seed)
        initial = tuple(dialog.point_model.rows)
        assert not dialog.undo_action.isEnabled()
        dialog.add_pair.click()
        for side, (view, xy) in enumerate(
            zip(dialog.views, (new.left_xy, new.right_xy), strict=True)
        ):
            _click_image(view, xy, detail=True)
            _wait(app, lambda: dialog._job is None)
            _click_image(view, xy)
            if side == 0:
                assert tuple(dialog.point_model.rows) == initial
                assert not dialog.undo_action.isEnabled()
        added = dialog._selected()
        assert added is not None and added.id.startswith("Point ")
        np.testing.assert_allclose(added.left_xy, new.left_xy, atol=1, rtol=0)
        np.testing.assert_allclose(added.right_xy, new.right_xy, atol=1, rtol=0)
        after_add = tuple(dialog.point_model.rows)
        dialog.points_table.setFocus()
        QTest.keyClick(dialog.points_table, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        assert tuple(dialog.point_model.rows) == initial and dialog.redo_action.isEnabled()
        QTest.keyClick(dialog.points_table, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        assert tuple(dialog.point_model.rows) == after_add

        dialog.points_table.selectRow(len(after_add) - 1)
        dialog.move_point.click()
        revised_xy = (new.right_xy[0] + 0.125, new.right_xy[1])
        dialog.views[1].picked.emit(revised_xy)
        moved = dialog._selected()
        assert (
            moved is not None and moved.right_xy == revised_xy and moved.left_xy == added.left_xy
        )
        dialog.undo_action.trigger()
        assert tuple(dialog.point_model.rows) == after_add
        dialog.redo_action.trigger()
        assert dialog.point_model.rows[-1] == moved
        dialog.points_table.selectRow(0)
        removed_id = dialog.point_model.rows[0].id
        dialog.remove_pair.click()
        assert all(point.id != removed_id for point in dialog.point_model.rows)
        dialog.undo_action.trigger()
        assert dialog.point_model.rows[0].id == removed_id
        dialog.redo_action.trigger()
        assert all(point.id != removed_id for point in dialog.point_model.rows)
        disabled = dialog.point_model.rows[0]
        assert not disabled.held_out
        _enable_flag(dialog, 0, 1, False)
        _enable_flag(dialog, 0, 2, True)
        assert dialog.point_model.rows[0] == replace(disabled, enabled=False, held_out=True)
        dialog.undo_action.trigger()
        assert dialog.point_model.rows[0] == replace(disabled, enabled=False)
        _enable_flag(dialog, 0, 2, False)
        assert dialog.redo_action.isEnabled()
        dialog.undo_action.trigger()
        assert dialog.point_model.rows[0] == disabled
        dialog.redo_action.trigger()
        assert dialog.point_model.rows[0] == replace(disabled, enabled=False)

        dialog.model.setCurrentText("Translation")
        dialog.fit_button.click()
        _wait(app, lambda: dialog._job is None)
        assert "Panel groups 1 | 2" in dialog.status.text()
        assert not dialog.apply_button.isEnabled()
        assert window.project == saved and _digest(path) == before

        dialog.model.setCurrentText("Similarity")
        dialog.fit_button.click()
        assert dialog.cancel_job.isEnabled()
        assert not dialog.undo_action.isEnabled() and not dialog.redo_action.isEnabled()
        dialog.cancel_job.click()
        _wait(app, lambda: dialog._job is None)
        assert "cancelled" in dialog.status.text()
        assert not dialog.apply_button.isEnabled()
        assert _digest(path) == before and window.project == saved

        dialog.fit_button.click()
        _wait(app, lambda: dialog._job is None)
        assert dialog.apply_button.isEnabled(), dialog.status.text()
        assert "Similarity · Anchor panel 2 · Accepted." in dialog.status.text()
        outcome, residual = dialog.links.item(0, 1), dialog.links.item(0, 4)
        assert outcome is not None and outcome.text() == "Accepted"
        assert residual is not None and float(residual.text()) < 2
        assert any(
            row.status == "disabled" and row.id == disabled.id
            for row in dialog.point_model.diagnostics.values()
        )
        candidate = dialog._candidate
        dialog.undo_action.trigger()
        assert dialog.point_model.rows[0] == disabled and dialog.links.rowCount() == 0
        assert not dialog.apply_button.isEnabled() and not dialog.point_model.diagnostics
        dialog.redo_action.trigger()
        assert dialog.point_model.rows[0] == replace(disabled, enabled=False)
        assert not dialog.apply_button.isEnabled()
        dialog.fit_button.click()
        _wait(app, lambda: dialog._job is None)
        assert dialog.apply_button.isEnabled() and dialog._candidate == candidate
        dialog.apply_button.click()

    _review(app, window, edit)
    assert window.layer_box.currentText() == "Foreground"
    assert "Applied foreground similarity" in window.status.text()
    aligned = window.project
    assert window.undo_action.text() == "&Undo Apply Terrain Alignment"
    window.undo_action.trigger()
    assert window.project == saved and window.project.current_foreground() is not None

    def cancel_draft(dialog: TerrainPointEditor) -> None:
        _wait(app, lambda: dialog._job is None)
        dialog.points_table.selectRow(0)
        dialog.remove_pair.click()
        assert dialog.undo_action.isEnabled()
        dialog.reject()

    _review(app, window, cancel_draft)
    assert window.project == saved and window.redo_action.isEnabled()
    window.redo_action.trigger()
    assert window.project == aligned and window.project.reviewable_terrain() is not None
    assert window._save()
    assert json.loads(path.read_bytes())["version"] == 8
    window._open_project(path)
    reopened = window.project
    evidence = reopened.reviewable_terrain()
    assert evidence is not None and evidence.held_out_p95_px is not None
    assert evidence.held_out_p95_px < 2 and sum(not point.enabled for point in evidence.points) == 1
    assert reopened.current_foreground() is not None

    first, second = reopened.panels
    mask = first.source_mask
    assert mask is not None
    changed = replace(mask, labels=bytes([UNCLASSIFIED]) + mask.labels[1:])
    revised = replace(reopened, panels=(replace(first, source_mask=changed), second))
    assert revised.current_foreground() is None
    assert revised.reviewable_terrain() == evidence

    # Close while the real image job is still owned by the editor, then reopen for rendering.
    def close_editor(dialog: TerrainPointEditor) -> None:
        dialog.close()

    _review(app, window, close_editor)
    assert window.project == reopened
    window.preview_button.click()
    _wait(app, lambda: window.job is None)
    frame = window.viewport.frame
    assert frame is not None and frame.has_coverage
    expected_backend = "OpenGL" if os.environ.get("ASTROMOSAIC_TEST_OPENGL") == "1" else "CPU"
    assert window.viewport.backend == expected_backend
    desktop = tmp_path / "desktop.fits"
    _export(app, window, desktop, monkeypatch)
    independent = tmp_path / "source.fits"
    render_project_layer(reopened, "foreground", independent, context)
    assert _digest(desktop) == _digest(independent)
    assert int(fitsio.read(desktop, ext="COVERAGE").sum()) > 580_000
    assert "CTYPE1" not in fitsio.read_header(desktop)
    assert {_path: _digest(_path) for _path in originals} == originals


@pytest.mark.parametrize(
    ("path", "case", "expected", "model"),
    [
        (_ALPACA, "alpaca", "accepted", "translation"),
        (_LASILLA, "lasilla", "accepted", "auto"),
        (_ADIRONDACK, "adirondack", "disconnected", "similarity"),
        (_PA4, "pa4", "disconnected", "auto"),
    ],
    ids=["alpaca", "lasilla", "adirondack", "pa4"],
)
def test_real_controls_show_positive_and_disconnected_fits(
    app: QApplication, window: ProjectWindow, path: Path, case: str, expected: str, model: str
) -> None:
    _require(path)
    points = _pa4_points() if case == "pa4" else _observations(case)
    original = _digest(path)
    window._open_project(path)

    def evaluate(dialog: TerrainPointEditor) -> None:
        _wait(app, lambda: dialog._job is None)
        _enter_points(app, dialog, points)
        dialog.model.setCurrentText(model.capitalize())
        dialog.fit_button.click()
        _wait(app, lambda: dialog._job is None)
        fit = dialog._fit
        assert fit is not None and fit.status == expected, dialog.status.text()
        if expected == "accepted":
            assert dialog.apply_button.isEnabled()
            held_out = fit.edges[0].held_out_p95_px
            assert held_out is not None and held_out < 2
            if case == "alpaca":
                np.testing.assert_allclose(fit.poses[1].shift, (48, 16), atol=1.5, rtol=0)
            dialog.apply_button.click()
        else:
            assert not dialog.apply_button.isEnabled()
            assert "Panel groups" in dialog.status.text()
            assert fit.groups == tuple((index,) for index in dialog._panels)
            assert dialog.links.rowCount() == len(fit.edges)
            if case == "pa4":
                assert any(point.status == "outside-valid-ground" for point in fit.points)

    _review(app, window, evaluate)
    assert (window.project.current_foreground() is not None) == (expected == "accepted")
    assert _digest(path) == original


def _pa4_points() -> list[GroundControlPoint]:
    checked = _EVIDENCE / "phase7a/landmark-comparison-checked.json"
    followup = _EVIDENCE / "phase7a/pa4-followup.json"
    _require(checked, followup)
    review = json.loads(followup.read_bytes())
    controls: tuple[tuple[tuple[int, int], list[dict[str, Any]]], ...] = (
        ((0, 1), review["02-03"]["measurements"]),
        ((2, 3), json.loads(checked.read_bytes())["measurements"]["pa4-04-05-visible-terrain"]),
        ((3, 4), review["05-06"]["measurements"]),
    )
    return [
        GroundControlPoint(
            f"{pair[0]}-{pair[1]}-{row['id']}",
            pair,
            _xy(row["reference_xy"]),
            _xy(row["primary"]["moving_xy"]),
            row["split"] == "held-out",
        )
        for pair, rows in controls
        for row in rows
        if row["usable"]
    ]


def test_mixed_editor_composition_preserves_the_real_sky_product(
    app: QApplication, window: ProjectWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _require(_MIXED)
    original = load_project(_MIXED)
    before = tmp_path / "sky-before.tiff"
    render_project_layer(original, "sky", before, JobContext())
    window._open_project(_MIXED)

    def fit(dialog: TerrainPointEditor) -> None:
        _wait(app, lambda: dialog._job is None)
        _enter_points(
            app,
            dialog,
            [
                GroundControlPoint(f"{x}-{y}", (0, 1), (x, y), (x - 510, y))
                for x, y in ((610, 848), (690, 878), (780, 894), (970, 875), (1010, 892))
            ],
        )
        dialog.anchor.setCurrentIndex(1)
        dialog.fit_button.click()
        _wait(app, lambda: dialog._job is None)
        assert dialog.apply_button.isEnabled(), dialog.status.text()
        dialog.apply_button.click()

    _review(app, window, fit)
    assert window.project.composition is None
    aligned = window.project
    window.layer_box.setCurrentText("Composition")
    assert not window.start_button.isEnabled()
    window.undo_action.trigger()
    assert window.project == original and window.start_button.isEnabled()
    window.redo_action.trigger()
    assert window.project == aligned and not window.start_button.isEnabled()
    window.placement_action.trigger()
    _wait(app, lambda: window.job is None)
    assert window.layer_box.currentText() == "Composition"
    mosaic = tmp_path / "composed.tiff"
    _export(app, window, mosaic, monkeypatch)
    with tifffile.TiffFile(mosaic) as tiff:
        pages = tiff.pages[0].pages
        assert pages is not None
        coverage = pages[0].asarray()
        layers = pages[1].asarray()
        np.testing.assert_array_equal(coverage != 0, layers != 0)
        assert set(np.unique(layers)) == {0, 1, 2}
    window.layer_box.setCurrentText("Sky")
    after = tmp_path / "sky-after.tiff"
    _export(app, window, after, monkeypatch)
    assert _digest(before) == _digest(after)
