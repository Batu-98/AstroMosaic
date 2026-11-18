import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from threading import Event, get_ident

import pytest

from astromosaic.astrometry.solve import SolveOptions
from astromosaic.core.job import JobContext


def test_desktop_saves_solver_paths_and_reopens_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEventLoop, QSettings, QTimer
    from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton

    from astromosaic.ui import plate_solve_settings
    from astromosaic.ui.plate_solve_settings import PlateSolveSettings
    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)

    preferences = tmp_path / "user settings.ini"
    monkeypatch.setattr(
        plate_solve_settings,
        "_settings",
        lambda: QSettings(str(preferences), QSettings.Format.IniFormat),
    )
    catalog = tmp_path / "Gaia yıldızları.bin"
    index = tmp_path / "matched index.idx"
    executable = tmp_path / "astap_cli.exe"
    catalog_folder = tmp_path / "star database"
    choices = {
        "Star catalog": catalog,
        "Blind index (optional)": index,
        "CLI executable": executable,
    }

    def choose_file(parent: object, title: str, start: str, filters: str) -> tuple[str, str]:
        return str(choices[title]), ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", choose_file)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(catalog_folder))
    expected = SolveOptions(
        gaia_catalog=catalog,
        gaia_index=index,
        astap=executable,
        astap_catalog=catalog_folder,
        astap_database="d50",
        timeout_seconds=18,
        total_seconds=90,
        job_seconds=230,
        strict_edges=True,
    )
    main_thread = get_ident()
    entered, release = Event(), Event()

    def check_paths(options: SolveOptions, context: JobContext) -> tuple[str, str]:
        assert get_ident() != main_thread and options == expected
        entered.set()
        while not release.wait(0.01):
            context.check_cancelled()
        return "Catalog and blind index open.", "ASTAP CLI responds."

    monkeypatch.setattr(plate_solve_settings, "check_solver_paths", check_paths)
    window = ProjectWindow(use_gpu=False)

    def until(condition: Callable[[], bool]) -> None:
        loop = QEventLoop()
        poll, timeout = QTimer(), QTimer()
        poll.timeout.connect(lambda: loop.quit() if condition() else None)
        timeout.setSingleShot(True)
        timeout.timeout.connect(loop.quit)
        poll.start(10)
        timeout.start(5000)
        loop.exec()
        poll.stop()
        timeout.stop()
        assert condition()

    def drive_dialog(dialog: PlateSolveSettings) -> int:
        dialog.show()
        try:
            browse = {
                button.accessibleName(): button for button in dialog.findChildren(QPushButton)
            }
            for label in (*choices, "Catalog folder"):
                browse[f"Browse for {label.lower()}"].click()
            assert dialog.astap_database.currentText() == "Automatic"
            dialog.astap_database.setCurrentText("D50")
            dialog.timeout_seconds.setValue(18)
            dialog.total_seconds.setValue(90)
            dialog.job_seconds.setValue(230)
            dialog.strict_edges.setChecked(True)
            dialog.check_button.click()
            until(entered.is_set)
            assert not dialog.save_button.isEnabled()
            release.set()
            until(dialog.save_button.isEnabled)
            assert "Catalog and blind index open." in dialog.message.text()
            assert "ASTAP CLI responds." in dialog.message.text()
            dialog.save_button.click()
            return dialog.result()
        finally:
            release.set()
            if dialog._job is not None:
                assert dialog._job.wait(5000)

    window.show()
    try:
        with monkeypatch.context() as scoped:
            scoped.setattr(PlateSolveSettings, "exec", drive_dialog)
            window.plate_solve_settings_action.trigger()
        assert window.status.text() == "Saved local plate solve settings."
        assert plate_solve_settings.load_plate_solve_settings() == expected
        assert window.project == window._saved

        reopened = PlateSolveSettings(window)
        assert reopened.gaia_index.text() == str(index)
        assert reopened.astap_database.currentText() == "D50"
        release.clear()
        entered.clear()
        reopened.show()
        try:
            reopened.check_button.click()
            until(entered.is_set)
            reopened.close()
            until(lambda: not reopened.isVisible())
            assert reopened._job is None
        finally:
            release.set()
            if reopened._job is not None:
                assert reopened._job.wait(5000)
            reopened.deleteLater()
        assert plate_solve_settings.load_plate_solve_settings() == expected
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()

    code = """
import json
import sys
from PySide6.QtCore import QSettings
from astromosaic.ui import plate_solve_settings
plate_solve_settings._settings = lambda: QSettings(sys.argv[1], QSettings.Format.IniFormat)
options = plate_solve_settings.load_plate_solve_settings()
print(json.dumps([
    str(options.gaia_catalog), str(options.gaia_index), str(options.astap),
    str(options.astap_catalog), options.astap_database,
    options.timeout_seconds, options.total_seconds, options.job_seconds, options.strict_edges,
]))
"""
    restarted = subprocess.run(
        [sys.executable, "-c", code, str(preferences)],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert json.loads(restarted.stdout) == [
        str(catalog),
        str(index),
        str(executable),
        str(catalog_folder),
        "d50",
        18.0,
        90.0,
        230.0,
        True,
    ]
