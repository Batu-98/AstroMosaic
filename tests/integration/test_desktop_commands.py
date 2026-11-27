import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from time import monotonic

import numpy as np
import pytest
from astropy.io import fits

from astromosaic.core import Region
from astromosaic.core.job import DEFAULT_JOB_CONTEXT
from astromosaic.geometry import tan_output_wcs
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    load_project,
    preview_project,
    save_project,
)


def test_command_panel_fits_a_short_window_with_large_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings, QSize
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)

    system_font = QFontDatabase.systemFont

    def large_system_font(role: QFontDatabase.SystemFont) -> QFont:
        font = system_font(role)
        font.setPointSize(14)
        return font

    monkeypatch.setattr(QFontDatabase, "systemFont", staticmethod(large_system_font))
    original_font = app.font()
    app.setFont(large_system_font(QFontDatabase.SystemFont.GeneralFont))
    preferences = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = ProjectWindow(use_gpu=False, preferences=preferences)
    screens = app.screens()
    if len(screens) > 1:
        window.move(screens[1].availableGeometry().center() - window.rect().center())
    window.show()

    try:
        panel = window.command_panel
        panel.set_project_path(tmp_path / "A long working folder" / "Project.astromosaic")
        assert panel.entry.font().pointSize() == 14
        assert panel.directory_field.text() == str(tmp_path / "A long working folder")
        assert panel.directory_field.isReadOnly()

        window.resize(800, 650)
        app.processEvents()
        assert window.size() == QSize(800, 650)

        window.status.setText("Building preview…")
        window._show_job_progress(True, timed=True)
        window.progress_elapsed.setText("Elapsed 0:59")
        window.progress.setValue(67)
        window.cancel_button.show()
        app.processEvents()

        assert window.size() == QSize(800, 650)
        assert window.progress.isVisible() and window.cancel_button.isVisible()
        assert window.progress_percent.text() == "67%"
        assert window.viewport.canvas.height() >= 100
        assert panel.entry.isVisible() and panel.directory_field.isVisible()
        assert panel.output.height() >= panel.output.minimumSizeHint().height()
        assert panel.output.viewport().height() >= 2 * panel.output.fontMetrics().lineSpacing()
    finally:
        window.close()
        app.setFont(original_font)


def test_command_panel_runs_saved_projects_and_cleans_cancelled_exports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)

    directory = tmp_path / "Gökyüzü session"
    directory.mkdir()
    results = Path("Night run") / "mosaic.fits"
    (directory / results.parent).mkdir()
    startup = Path.cwd()
    manifest = directory / "Saved project.astromosaic"
    source = directory / "Panel.fits"
    spec = RenderSpec((359.999, 20.0), (416, 332), 2.0, tile_size=8)
    region = Region(0, 0, *spec.size)
    y, x = np.indices((region.height, region.width), dtype=np.float32)
    header = tan_output_wcs(spec.center, spec.size, spec.scale_arcsec, 0, region).to_header()
    header["FILTER"], header["BUNIT"] = "L", "MJy/sr"
    fits.writeto(source, x - y, header)
    project = MosaicProject((ProjectPanel(FileReference.capture(source)),), spec)
    save_project(manifest, project)
    originals = manifest.read_bytes(), source.read_bytes()

    window = ProjectWindow(use_gpu=False)
    panel = window.command_panel
    timer = QTimer()
    ticks: list[str] = []
    timer.timeout.connect(lambda: ticks.append(panel.status.text()))

    def until(condition: Callable[[], bool]) -> None:
        deadline = monotonic() + 20
        while not condition():
            assert monotonic() < deadline, panel.output.toPlainText()
            QTest.qWait(10)

    def cli(*arguments: str) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, "-m", "astromosaic", *arguments, "--json"],
            cwd=directory,
            capture_output=True,
            encoding="utf-8",
            check=True,
            timeout=20,
        )
        return dict(json.loads(result.stdout))

    def reports() -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in panel.output.toPlainText().splitlines()
            if line.startswith("{")
        ]

    def run(command: str) -> None:
        panel.entry.setText(command)
        QTest.keyClick(panel.entry, Qt.Key.Key_Return)
        assert panel.is_running

    window.show()
    try:
        assert panel.isVisible() and window.command_panel_action.isChecked()
        window.command_panel_action.trigger()
        assert not panel.isVisible() and not window.command_panel_action.isChecked()
        new, *_ = window._file_actions
        new.trigger()
        window._set_project(project, manifest)
        window.command_panel_action.trigger()
        assert panel.isVisible() and panel.directory_field.text() == str(directory)
        assert panel.output.toPlainText().splitlines() == ["New project."]
        window.activateWindow()
        panel.entry.setFocus()

        validate = f'astromosaic-cli.exe project validate "{manifest}" --json'
        run(validate)
        until(lambda: not panel.is_running)
        assert reports()[-1] == cli("project", "validate", str(manifest))
        assert panel.status.text() == "Command completed."
        panel.entry.setText("--help")
        QTest.keyClick(panel.entry, Qt.Key.Key_Up)
        assert panel.entry.text() == validate
        QTest.keyClick(panel.entry, Qt.Key.Key_Down)
        assert panel.entry.text() == "--help"

        run("echo unsupported")
        until(lambda: not panel.is_running)
        assert (
            "exit code 2" in panel.status.text() and "invalid choice" in panel.output.toPlainText()
        )
        assert window.start_button.isEnabled()

        export = f'project export "{manifest.name}" -o "{results}" --json --progress'
        run(export)
        assert not window.start_button.isEnabled() and not panel.run_button.isEnabled()
        timer.start(5)
        until(lambda: any(text.startswith("Rendering ") for text in ticks))
        assert list((directory / results.parent).glob("*.part"))
        assert not (directory / results).exists()
        panel.cancel_button.click()
        assert "Cancelling" in panel.status.text()
        until(lambda: not panel.is_running)
        timer.stop()
        assert reports()[-1]["status"] == "cancelled" and "exit code 130" in panel.status.text()
        assert not (directory / results).exists() and not list(directory.rglob("*.part"))

        run(export)
        until(lambda: not panel.is_running)
        report = reports()[-1]
        reference = cli("project", "export", manifest.name, "-o", "reference.fits", "--progress")
        assert report == {**reference, "output": str(results)}
        assert any(event.get("event") == "progress" for event in reports())
        assert panel.progress.value() == 100 and window.start_button.isEnabled()
        assert (directory / results).read_bytes() == (directory / "reference.fits").read_bytes()

        run(f'project export "{manifest.name}" -o "closing.fits"')
        until(lambda: panel.status.text().startswith("Rendering "))
        window.close()
        assert window.isVisible()
        until(lambda: not window.isVisible())
        assert "exit code 130" in panel.status.text()
        assert not (directory / "closing.fits").exists() and not list(directory.rglob("*.part"))
        assert Path.cwd() == startup and (manifest.read_bytes(), source.read_bytes()) == originals
    finally:
        timer.stop()
        panel.cancel()
        until(lambda: not panel.is_running and window._inspection_job is None)
        window.deleteLater()
        app.processEvents()


def test_session_commands_use_the_live_project_without_modal_dialogs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

    from astromosaic.pipeline.smoke import write_smoke_panel
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
    panel = window.command_panel
    prompts: list[str] = []

    def unexpected_dialog(*args: object, **kwargs: object) -> None:
        prompts.append("A dialog opened")
        raise AssertionError(prompts[-1])

    for method in ("getOpenFileName", "getOpenFileNames", "getSaveFileName"):
        monkeypatch.setattr(QFileDialog, method, unexpected_dialog)
    monkeypatch.setattr(QMessageBox, "question", unexpected_dialog)
    monkeypatch.setattr(QMessageBox, "exec", unexpected_dialog)

    def run(command: str) -> None:
        panel.entry.setText(command)
        panel.run_button.click()
        assert not prompts

    def wait_until(condition: Callable[[], bool]) -> None:
        deadline = monotonic() + 15
        while not condition():
            assert monotonic() < deadline, panel.output.toPlainText()
            QTest.qWait(10)

    def idle() -> bool:
        return window.job is None and window._inspection_job is None

    source = tmp_path / "Gökyüzü panel.fits"
    write_smoke_panel(source)
    original = source.read_bytes()
    saved = tmp_path / "Night session.astromosaic"
    taken = tmp_path / "Occupied.astromosaic"
    taken.write_bytes(b"existing bytes")
    spec = RenderSpec((359.999, 20.0), (16, 12), 7.2)
    window._set_project(MosaicProject(render=spec), None)
    window.show()
    try:
        run("session save --help")
        assert "--replace" in panel.output.toPlainText()
        run("session save")
        assert "Supply a project filename" in panel.output.toPlainText()
        run(f'session add "{source}"')
        wait_until(idle)
        assert len(window.project.panels) == 1
        run("session status")
        assert '"dirty": true' in panel.output.toPlainText()
        run("session close")
        run("session new")
        run(f'session open "{tmp_path / "absent.astromosaic"}" --discard')
        assert window.isVisible() and window.project.panels[0].source.path == source
        assert "The active project has unsaved changes" in panel.output.toPlainText()

        run(f'session save "{taken}"')
        assert taken.read_bytes() == b"existing bytes" and window.project_path is None
        run(f'session save "{saved.with_suffix("")}"')
        assert window.project_path == saved and load_project(saved) == window.project

        window._commit_project(
            replace(window.project, render=replace(spec, crop=Region(1, 1, 9, 7))), "Apply Crop"
        )
        run('session export -o "Live sky.fits"')
        wait_until(idle)
        assert fits.getdata(tmp_path / "Live sky.fits").shape == (7, 9)
        assert load_project(saved).render.crop is None
        run("session save")
        assert load_project(saved).render.crop == Region(1, 1, 9, 7)

        run("session use-preview-grid")
        assert "Build an automatically framed sky preview first." in panel.output.toPlainText()
        saved_grid = window.project.render
        run("session preview --grid auto")
        wait_until(idle)
        fitted_grid = preview_project(window.project, DEFAULT_JOB_CONTEXT).fitted_grid
        assert fitted_grid is not None and fitted_grid != saved_grid
        assert window.viewport.frame is not None and window.viewport.frame.has_coverage
        assert window.project.render == saved_grid
        run("session save")
        assert load_project(saved).auto_frame_preview
        assert load_project(saved).render == saved_grid
        run("session use-preview-grid")
        assert window.project.render == fitted_grid and not window.project.auto_frame_preview
        assert window.viewport.frame is not None and window.viewport.frame.has_coverage
        run("session save")
        assert load_project(saved).render == fitted_grid

        moved = source.with_name("Moved panel.fits")
        source.rename(moved)
        run(f'session open "{saved.name}"')
        run(f'session relink 1 "{moved.name}"')
        wait_until(idle)
        assert window.project.panels[0].source.path == moved
        run("session save")
        assert load_project(saved).panels[0].source.path == moved
        run("session close")
        wait_until(lambda: not window.isVisible())
        assert not prompts and moved.read_bytes() == original
        assert not list(tmp_path.rglob("*.part"))
    finally:
        if window.job is not None:
            window.job.cancel()
        wait_until(idle)
        window.deleteLater()
        app.processEvents()
