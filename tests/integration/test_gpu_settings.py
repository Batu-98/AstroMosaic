"""Exercise the GPU preference and the CPU fallback through the desktop workflow."""

import os
from pathlib import Path
from time import monotonic, sleep
from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.project_window import ProjectWindow


def _app(monkeypatch: pytest.MonkeyPatch) -> "QApplication":
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = cast(QApplication | None, QApplication.instance()) or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def _choose(
    window: "ProjectWindow", monkeypatch: pytest.MonkeyPatch, *, before: bool, after: bool,
    enabled: bool = True, accept: bool = True,
) -> None:
    from PySide6.QtWidgets import QCheckBox, QDialog

    def choose(dialog: QDialog) -> int:
        assert dialog.windowTitle() == "GPU Acceleration"
        checkbox = dialog.findChild(QCheckBox)
        assert checkbox is not None
        assert checkbox.isChecked() == before and checkbox.isEnabled() == enabled
        checkbox.setChecked(after)
        return int(QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected)

    with monkeypatch.context() as patch:
        patch.setattr(QDialog, "exec", choose)
        window.gpu_settings_action.trigger()


def test_gpu_preference_defaults_on_and_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    from PySide6.QtCore import QEvent, QSettings

    from astromosaic.ui.project_window import ProjectWindow

    filename = str(tmp_path / "settings.ini")
    for use_gpu, before, after, accept in (
        (True, True, False, False),  # Cancel preserves the default.
        (True, True, False, True),
        (True, False, True, True),
        (False, True, False, True),  # The startup override leaves the saved choice intact.
        (True, True, True, True),
    ):
        settings = QSettings(filename, QSettings.Format.IniFormat)
        window = ProjectWindow(use_gpu=use_gpu, preferences=settings)
        try:
            assert window._use_gpu_preview == (use_gpu and before)
            _choose(window, monkeypatch, before=before, after=after, enabled=use_gpu, accept=accept)
            assert window._use_gpu_preview == (use_gpu and (after if accept else before))
            assert window.project == window._saved
            settings.sync()
        finally:
            window.close()
            window.deleteLater()
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_gpu_preference_switches_preview_and_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(monkeypatch)
    from PySide6.QtCore import QEvent, QSettings
    from PySide6.QtGui import QOpenGLContext

    from astromosaic.ui.mosaic_job import PreviewJob
    from astromosaic.ui.preview_gl import OpenGLPreview
    from astromosaic.ui.project_window import ProjectWindow

    manifest = Path(__file__).resolve().parents[2] / "data/application-tests/sky01-m17-atlas/project.astromosaic"
    if not manifest.is_file():
        pytest.skip("Prepare the real M17 reference in docs/phase-6.md.")
    native = app.platformName() not in {"minimal", "offscreen"}
    if native and os.environ.get("ASTROMOSAIC_TEST_OPENGL") != "1":
        pytest.skip("Set ASTROMOSAIC_TEST_OPENGL=1 for native GPU verification.")
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = ProjectWindow(preferences=settings)

    def wait_idle() -> None:
        deadline = monotonic() + 25
        while window.job is not None or window._inspection_job is not None:
            assert monotonic() < deadline, window.status.text()
            app.processEvents()
            sleep(0.005)
        app.processEvents()

    def build(*, gpu: bool) -> None:
        window.preview_button.click()
        job = window.job
        assert isinstance(job, PreviewJob)
        wait_idle()
        assert job.result is not None, job.error
        assert job.gpu_sampled == gpu
        assert ("OpenGL GPU sampling" if gpu else "CPU sampling") in window.status.text()

    try:
        secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
        if secondary is not None:
            window.move(secondary.availableGeometry().center() - window.rect().center())
        window.show()
        window._open_project(manifest)
        wait_idle()
        build(gpu=native)
        assert window.viewport.backend == ("OpenGL" if native else "CPU")

        frame = window.viewport.frame
        _choose(window, monkeypatch, before=True, after=False)
        assert window.viewport.backend == "CPU" and window.viewport.frame is frame
        build(gpu=False)

        if native:
            def fail_upload(*_args: object) -> None:
                raise RuntimeError("Test unavailable OpenGL viewport.")

            monkeypatch.setattr(QOpenGLContext, "create", lambda _context: False)
            monkeypatch.setattr(OpenGLPreview, "_upload", fail_upload)
        _choose(window, monkeypatch, before=False, after=True)
        build(gpu=False)
        assert window.viewport.backend == "CPU"
        assert window._gpu_acceleration_preference()
    finally:
        window.close()
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
