import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from time import monotonic

import numpy as np
import pytest
from astropy.io import fits

from astromosaic.core import Region
from astromosaic.geometry import tan_output_wcs
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.storage.project import FileReference, MosaicProject, ProjectPanel, save_project


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
        assert panel.isVisible() and str(directory) in panel.directory_label.text()
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
