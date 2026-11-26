import json
import os
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from shutil import copy2
from threading import Event
from time import monotonic

import numpy as np
import pytest
from astropy.io import fits

from astromosaic.astrometry.solve import SolveOptions, solve_panel, write_solution
from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.core.masks import FOREGROUND, SKY, UNCLASSIFIED, SourceMask
from astromosaic.display import DisplayFrame
from astromosaic.io import open_panel
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.pipeline.smoke import write_smoke_panel
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    PanelInspection,
    ProjectPanel,
    load_project,
)


def test_panel_history_save_relink_and_session_lifetime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    window = ProjectWindow(
        use_gpu=False,
        preferences=QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat),
    )
    secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
    if secondary is not None:
        window.move(secondary.availableGeometry().center() - window.rect().center())
    window.show()
    window.activateWindow()
    app.processEvents()

    def wait_idle() -> None:
        deadline = monotonic() + 10
        while window.job is not None or window._inspection_job is not None:
            assert monotonic() < deadline, window.status.text()
            QTest.qWait(10)

    def run(command: str) -> str:
        terminal = window.command_panel
        terminal.entry.setText(command)
        terminal.run_button.click()
        return terminal.output.toPlainText().splitlines()[-1]

    def check_saved_state(path: Path, *, dirty: bool, panels: int) -> None:
        assert window.windowTitle().startswith(f"{path.name}{'*' if dirty else ''} — ")
        assert json.loads(run("session status")) == {
            "schema_version": 1, "project": str(path), "dirty": dirty, "panels": panels,
        }

    first, second = tmp_path / "First.fits", tmp_path / "Second.fits"
    for source in (first, second):
        write_smoke_panel(source)
    originals = first.read_bytes(), second.read_bytes()
    relinked = tmp_path / "Relinked.fits"
    copy2(second, relinked)
    manifest = tmp_path / "Saved.astromosaic"
    duplicate = tmp_path / "Save As.astromosaic"
    discard_prompts: list[str] = []
    open_errors: list[str] = []
    buttons = QMessageBox.StandardButton

    def cancel_discard(
        parent: object, title: str, text: str, offered: object, default: object
    ) -> QMessageBox.StandardButton:
        discard_prompts.append(title)
        return buttons.Cancel

    monkeypatch.setattr(QMessageBox, "question", cancel_discard)
    monkeypatch.setattr(window, "_error", lambda title, error: open_errors.append(title))
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: ([str(first), str(second)], ""))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(manifest), ""))
    try:
        assert not window.undo_action.isEnabled() and not window.redo_action.isEnabled()
        window.add_button.click()
        assert window.job is not None and not window.undo_action.isEnabled()
        wait_idle()
        added = window.project
        assert [panel.source.path for panel in added.panels] == [first, second]
        assert all(panel.foreground_suggestion is not None for panel in added.panels)
        assert window.undo_action.text() == "&Undo Add Panels"
        window.undo_action.trigger()
        assert not window.project.panels and not window.undo_action.isEnabled()
        window.redo_action.trigger()
        assert window.project is added and window.job is None
        wait_idle()

        assert window._save()
        check_saved_state(manifest, dirty=False, panels=2)
        assert load_project(manifest) == added
        window.panels.selectRow(1)
        window.remove_action.trigger()
        removed = window.project
        assert window.undo_action.text() == "&Undo Remove Panel"
        check_saved_state(manifest, dirty=True, panels=1)

        window.panels.setFocus()
        QTest.keyClick(window.panels, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        wait_idle()
        assert window.project is added
        check_saved_state(manifest, dirty=False, panels=2)
        assert window.redo_action.text() == "&Redo Remove Panel"

        terminal = window.command_panel
        window.command_panel_action.setChecked(True)
        terminal.entry.setFocus()
        QTest.keyClicks(terminal.entry, "draft")
        QTest.keyClick(terminal.entry, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        assert not terminal.entry.text() and window.project is added
        QTest.keyClick(terminal.entry, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        assert terminal.entry.text() == "draft" and window.project is added
        QTest.keyClick(terminal.entry, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(
            terminal.entry, Qt.Key.Key_Z,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        assert terminal.entry.text() == "draft" and window.project is added

        assert "already added" in run(f'session add "{first}"')
        assert "failed" in run(f'session add "{tmp_path / "absent.fits"}"')
        assert "failed" in run(f'session relink 2 "{tmp_path / "absent.fits"}"')
        run(f'session relink 2 "{second}"')
        assert "failed" in run(f'session save "{manifest}"')
        assert window.project is added and window.redo_action.isEnabled()
        check_saved_state(manifest, dirty=False, panels=2)
        run(f'session save "{duplicate}"')
        check_saved_state(duplicate, dirty=False, panels=2)
        assert window.redo_action.isEnabled() and load_project(duplicate) == added

        window.panels.setFocus()
        QTest.keyClick(window.panels, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        wait_idle()
        assert window.project is removed
        check_saved_state(duplicate, dirty=True, panels=1)
        assert not window.close() and window.isVisible()
        window._file_actions[0].trigger()
        assert discard_prompts == ["Unsaved project", "Unsaved project"]
        assert window.project is removed and window.undo_action.isEnabled()
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", lambda *args: (str(tmp_path / "missing.astromosaic"), "")
        )
        window._file_actions[1].trigger()
        assert open_errors == ["Open failed"] and len(discard_prompts) == 2
        assert window.project is removed and window.project_path == duplicate
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(duplicate), ""))
        window._file_actions[1].trigger()
        assert len(discard_prompts) == 3 and window.project is removed

        window.undo_action.trigger()
        wait_idle()
        window.panels.setFocus()
        QTest.keyClick(
            window.panels, Qt.Key.Key_Z,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        assert window.project is removed
        window.undo_action.trigger()
        wait_idle()
        run(f'session relink 2 "{relinked}"')
        wait_idle()
        assert window.project.panels[1].source.path == relinked
        assert window.project.panels[1].source.fingerprint == added.panels[1].source.fingerprint
        assert window.undo_action.text() == "&Undo Relink Panel"
        assert not window.redo_action.isEnabled()
        check_saved_state(duplicate, dirty=True, panels=2)
        window.undo_action.trigger()
        wait_idle()
        check_saved_state(duplicate, dirty=False, panels=2)
        assert window.redo_action.text() == "&Redo Relink Panel"
        run(f'session open "{duplicate}"')
        wait_idle()
        assert window.project == added
        assert not window.undo_action.isEnabled() and not window.redo_action.isEnabled()

        window.remove_action.trigger()
        run("session new --discard")
        wait_idle()
        assert not window.project.panels and window.project_path is None
        assert not window.undo_action.isEnabled() and not window.redo_action.isEnabled()
        run(f'session open "{duplicate}"')
        wait_idle()
        window.remove_action.trigger()
        saved_from_prompt = window.project
        monkeypatch.setattr(QMessageBox, "question", lambda *args: buttons.Save)
        window._file_actions[1].trigger()
        wait_idle()
        assert window.project == load_project(duplicate) == saved_from_prompt
        assert not window.undo_action.isEnabled() and not window.redo_action.isEnabled()

        window.remove_action.trigger()
        assert window.undo_action.isEnabled()
        run("session close --discard")
        app.processEvents()
        assert not window.isVisible()
        assert not window.undo_action.isEnabled() and not window.redo_action.isEnabled()
        assert (first.read_bytes(), second.read_bytes()) == originals
        assert relinked.read_bytes() == originals[1]
    finally:
        if window.job is not None:
            window.job.cancel()
        wait_idle()
        window.deleteLater()
        app.processEvents()


def test_mask_draft_history_and_external_wcs_restoration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEvent, QPoint, QSettings, Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QToolButton

    from astromosaic.ui.mask_editor import MaskEditor
    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    quit_on_close = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)
    window = ProjectWindow(
        use_gpu=False,
        preferences=QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat),
    )
    secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
    if secondary is not None:
        window.move(secondary.availableGeometry().center() - window.rect().center())

    source, mask_path, wcs_path = (
        tmp_path / "input.fits", tmp_path / "external-mask.fits", tmp_path / "solve.wcs.json"
    )
    write_smoke_panel(source)
    external = np.ones((12, 16), dtype=np.uint8)
    external[0, 0] = 0
    fits.writeto(mask_path, external)
    with open_panel(source, sky_mask=mask_path) as panel:
        write_solution(wcs_path, panel, solve_panel(panel, SolveOptions()))
    files = (source, mask_path, wcs_path)
    originals = tuple(path.read_bytes() for path in files)
    original_panel = ProjectPanel(
        FileReference.capture(source),
        sky_mask=FileReference.capture(mask_path),
        wcs_sidecar=FileReference.capture(wcs_path),
    )
    original = MosaicProject(panels=(original_panel,))
    left = Qt.MouseButton.LeftButton
    control = Qt.KeyboardModifier.ControlModifier
    applied: list[SourceMask] = []

    def wait_until_idle() -> None:
        deadline = monotonic() + 8
        while window.job is not None or window._inspection_job is not None:
            assert monotonic() < deadline, window.status.text()
            QTest.qWait(10)

    def edit_mask(edit: Callable[[MaskEditor], None]) -> None:
        timer = QTimer()
        results: list[Exception | None] = []

        def interact() -> None:
            dialog = app.activeModalWidget()
            if not isinstance(dialog, MaskEditor):
                return
            timer.stop()
            try:
                assert secondary is None or dialog.screen() == secondary
                edit(dialog)
            except Exception as error:
                results.append(error)
                dialog.reject()
            else:
                results.append(None)

        timer.timeout.connect(interact)
        timer.start(10)
        try:
            window.mask_action.trigger()
            wait_until_idle()
        finally:
            timer.stop()
        assert results
        if results[0] is not None:
            raise results[0]

    def stroke(dialog: MaskEditor, start: tuple[int, int], end: tuple[int, int]) -> None:
        rect = dialog.canvas.image_rect()

        def point(cell: tuple[int, int]) -> QPoint:
            x, y = cell
            return QPoint(
                round(rect.x() + (x + 0.5) * rect.width() / 16),
                round(rect.y() + (y + 0.5) * rect.height() / 12),
            )

        QTest.mousePress(dialog.canvas, left, pos=point(start))
        assert not dialog.undo_action.isEnabled() and not dialog.apply_button.isEnabled()
        QTest.mouseMove(dialog.canvas, point(end))
        QTest.mouseRelease(dialog.canvas, left, pos=point(end))

    def snapshot(dialog: MaskEditor) -> SourceMask:
        return SourceMask((16, 12), dialog.canvas.grid.tobytes())

    def edit(dialog: MaskEditor) -> None:
        base = snapshot(dialog)
        np.testing.assert_array_equal(base.grid(), np.where(external, SKY, UNCLASSIFIED))
        assert not dialog.undo_action.isEnabled()
        dialog.radius.setValue(1)
        dialog.tool.setCurrentIndex(2)
        stroke(dialog, (2, 3), (5, 3))
        first = snapshot(dialog)
        assert first.grid()[3, 4] == FOREGROUND and first.sky_fingerprint != base.sky_fingerprint
        dialog.tool.setCurrentIndex(3)
        stroke(dialog, (10, 8), (13, 8))
        second = snapshot(dialog)
        assert second.grid()[8, 12] == UNCLASSIFIED
        assert second.sky_fingerprint != first.sky_fingerprint

        dialog.activateWindow()
        dialog.canvas.setFocus()
        app.processEvents()
        QTest.keyClick(dialog.canvas, Qt.Key.Key_Z, control)
        assert snapshot(dialog) == first and dialog.redo_action.isEnabled()
        QTest.keyClick(dialog.canvas, Qt.Key.Key_Y, control)
        assert snapshot(dialog) == second
        dialog.undo_action.trigger()
        dialog.reset_button.click()
        assert snapshot(dialog) == base and not dialog.redo_action.isEnabled()
        undo_button = next(
            button for button in dialog.findChildren(QToolButton)
            if button.defaultAction() is dialog.undo_action
        )
        QTest.mouseClick(undo_button, left)
        assert snapshot(dialog) == first
        dialog.tool.setCurrentIndex(2)
        stroke(dialog, (2, 3), (5, 3))
        assert snapshot(dialog) == first and dialog.redo_action.isEnabled()
        QTest.keyClick(dialog.canvas, Qt.Key.Key_Z, control | Qt.KeyboardModifier.ShiftModifier)
        assert snapshot(dialog) == base
        dialog.undo_action.trigger()
        applied.append(snapshot(dialog))
        dialog.apply_button.click()

    def cancel(dialog: MaskEditor) -> None:
        dialog.tool.setCurrentIndex(2)
        stroke(dialog, (7, 5), (9, 5))
        assert dialog.undo_action.isEnabled()
        QTest.keyClick(dialog.canvas, Qt.Key.Key_Y, control)
        assert window.project == original and window.redo_action.isEnabled()
        dialog.reject()

    try:
        window.show()
        window._set_project(original, None)
        wait_until_idle()
        assert window.panels.cell(0, "WCS").data() == "Sidecar"
        edit_mask(edit)
        edited = replace(original_panel, sky_mask=None, source_mask=applied[0])
        assert window.project.panels == (edited,)
        assert window.panels.cell(0, "WCS").data() == "Invalid"
        assert not window.solve_details_action.isEnabled() and window.align_menu.isEnabled()
        assert window.undo_action.text() == "&Undo Edit Sky Mask"

        window.undo_action.trigger()
        wait_until_idle()
        assert window.project == original and window.panels.cell(0, "WCS").data() == "Sidecar"
        assert window.solve_details_action.isEnabled() and not window.undo_action.isEnabled()
        assert not window.align_menu.isEnabled()
        edit_mask(cancel)
        assert window.project == original and window.redo_action.isEnabled()
        window.redo_action.trigger()
        wait_until_idle()
        assert window.project.panels == (edited,)
        assert window.panels.cell(0, "WCS").data() == "Invalid"
        assert tuple(path.read_bytes() for path in files) == originals
    finally:
        if window.job is not None:
            window.job.cancel()
        wait_until_idle()
        window._saved = window.project
        window.close()
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.setQuitOnLastWindowClosed(quit_on_close)


def test_returning_to_a_revision_rejects_old_jobs_and_keeps_the_saved_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEvent, QSettings
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.edit_history import EditHistory
    from astromosaic.ui.mosaic_job import PanelInspectionJob, PreviewDetailJob, PreviewJob
    from astromosaic.ui.preview_state import PreviewResult
    from astromosaic.ui.project_window import ProjectWindow

    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    window = ProjectWindow(
        use_gpu=False,
        preferences=QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat),
    )
    secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
    if secondary is not None:
        window.move(secondary.availableGeometry().center() - window.rect().center())
    window.live_preview_action.setChecked(False)
    source, manifest = tmp_path / "sky.fits", tmp_path / "saved.astromosaic"
    write_smoke_panel(source)
    initial = MosaicProject(
        (ProjectPanel(FileReference.capture(source)),),
        RenderSpec((359.999, 20.0), (16, 12), 7.2),
    )
    inspection_ready, preview_ready, detail_ready, release = Event(), Event(), Event(), Event()
    inspect = PanelInspectionJob.perform
    build = PreviewJob.perform
    inspection_runs = []

    def inspect_delayed(job: PanelInspectionJob, context: JobContext) -> tuple[PanelInspection, ...]:
        inspection_runs.append(job.project)
        if len(inspection_runs) == 1:
            inspection_ready.set()
            assert release.wait(10)
            return (PanelInspection("Missing", "Obsolete metadata", filter_name="Obsolete"),)
        return inspect(job, context)

    def build_delayed(job: PreviewJob, context: JobContext) -> PreviewResult:
        result = build(job, context)
        preview_ready.set()
        assert release.wait(10)
        return result

    def detail_delayed(job: PreviewDetailJob, context: JobContext) -> DisplayFrame:
        detail_ready.set()
        assert release.wait(10)
        return job.overview.frame

    def until(check: Callable[[], bool]) -> None:
        deadline = monotonic() + 10
        while not check():
            assert monotonic() < deadline, window.status.text()
            QTest.qWait(10)

    try:
        window.show()
        with monkeypatch.context() as patch:
            patch.setattr(PanelInspectionJob, "perform", inspect_delayed)
            window._set_project(initial, None)
            until(inspection_ready.is_set)
            window._set_auto_frame(True)
            window.undo_action.trigger()
            assert window.project is initial
            release.set()
            until(lambda: window._inspection_job is None)
            assert len(inspection_runs) == 2 and window.band_box.findData("L") >= 0
            assert window.band_box.findData("Obsolete") == -1

        release.clear()
        with monkeypatch.context() as patch:
            patch.setattr(PreviewJob, "perform", build_delayed)
            window.redo_action.trigger()
            previewed = window.project
            until(lambda: window._inspection_job is None)
            window.preview_button.click()
            until(preview_ready.is_set)
            window.undo_action.trigger()
            window.redo_action.trigger()
            assert window.project is previewed
            release.set()
            until(lambda: window.job is None and window._inspection_job is None)
            assert window.viewport.frame is None and window.status.text() == "Redid Change Sky Framing."

        window.preview_button.click()
        until(lambda: window.job is None)
        assert window.viewport.frame is not None
        release.clear()
        with monkeypatch.context() as patch:
            patch.setattr(window.viewport, "visible_detail", lambda: Region(0, 0, 3, 3))
            patch.setattr(PreviewDetailJob, "perform", detail_delayed)
            window._request_detail()
            until(detail_ready.is_set)
            window.undo_action.trigger()
            window.redo_action.trigger()
            assert window.project is previewed
            release.set()
            until(lambda: window._detail_job is None and window._inspection_job is None)
            assert window.viewport.detail is None

        window._set_project(initial, None)
        window._history = EditHistory(initial, max_steps=2)
        window._save_project(manifest, replace_existing=False)
        for size in (20, 24, 32):
            assert window._commit_project(
                replace(window.project, render=replace(initial.render, size=(size, size))), "Resize"
            )
        window._refresh()
        assert window._history.steps == 2
        window.undo_action.trigger()
        window.undo_action.trigger()
        assert window.project.render.size == (20, 20) and not window.undo_action.isEnabled()
        assert window._saved == load_project(manifest) == initial
        assert window.windowTitle().startswith(f"{manifest.name}*")
        before_failure = window.project
        with pytest.raises(OSError):
            window._save_project(tmp_path / "missing" / manifest.name, replace_existing=False)
        assert window.project is before_failure and window.redo_action.isEnabled()
        assert window.project_path == manifest and window._saved is initial
        window._set_auto_frame(True)
        assert not window.redo_action.isEnabled()
        window._save_project(manifest, replace_existing=True)
        window.undo_action.trigger()
        assert window.windowTitle().startswith(f"{manifest.name}*")
        window.redo_action.trigger()
        assert window.windowTitle().startswith(f"{manifest.name} — ")
        window._history = EditHistory(window.project, max_bytes=256)
        window._set_auto_frame(False)
        assert not window.undo_action.isEnabled() and "history limit" in window.undo_action.text()
        assert window.windowTitle().startswith(f"{manifest.name}*")
        window._save_project(manifest, replace_existing=True)
        until(lambda: window._inspection_job is None)
        assert window.close() and window._history.steps == 0
        source.rename(tmp_path / "released.fits")
    finally:
        release.set()
        if window.job is not None:
            window.job.cancel()
        until(
            lambda: window.job is None and window._inspection_job is None
            and window._detail_job is None
        )
        window._saved = window.project
        window.close()
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
