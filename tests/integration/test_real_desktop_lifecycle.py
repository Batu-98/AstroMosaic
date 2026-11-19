"""Native cleanup regression on the real 2MASS atlas reference."""

import os
from pathlib import Path
from time import monotonic, sleep

import pytest

_ATLAS = (
    Path(__file__).resolve().parents[2]
    / "data/application-tests/sky01-m17-atlas/project.astromosaic"
)


def test_close_real_preview_releases_opengl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if not _ATLAS.is_file():
        pytest.skip("Prepare the Phase 6 M17 observational reference in docs/phase-6.md.")
    if os.environ.get("ASTROMOSAIC_TEST_OPENGL") != "1":
        pytest.skip("Set ASTROMOSAIC_TEST_OPENGL=1 on a native desktop with OpenGL 3.2.")
    pytest.importorskip("PySide6")
    from PySide6.QtCore import (
        QEvent,
        QMessageLogContext,
        QSettings,
        QtMsgType,
        qInstallMessageHandler,
    )
    from PySide6.QtWidgets import QApplication, QFileDialog

    from astromosaic.ui.preview_gl import OpenGLPreview
    from astromosaic.ui.project_window import ProjectWindow

    instance = QApplication.instance()
    app = instance if isinstance(instance, QApplication) else QApplication([])
    quit_on_close = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)
    window = ProjectWindow(
        preferences=QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    )
    secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
    if secondary is not None:
        window.move(secondary.availableGeometry().center() - window.rect().center())
    messages: list[str] = []

    def collect(kind: QtMsgType, _context: QMessageLogContext, text: str) -> None:
        if kind in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            messages.append(text)

    previous_handler = qInstallMessageHandler(collect)
    try:
        window.show()
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: (str(_ATLAS), ""))
        window._file_actions[1].trigger()
        assert window.project_path == _ATLAS
        window.preview_button.click()
        assert window.job is not None
        deadline = monotonic() + 30
        while monotonic() < deadline:
            app.processEvents()
            if not window._is_running() and window._inspection_job is None:
                break
            sleep(0.005)
        assert window.job is None and window._inspection_job is None
        surface = window.viewport.canvas
        assert isinstance(surface, OpenGLPreview) and surface.isValid()
        assert not surface.grabFramebuffer().isNull() and surface._texture is not None

        assert window.close()
        assert window.viewport.frame is None and window.viewport.backend == "CPU"
        assert surface._texture is None and surface._vao is None and surface._program is None
    finally:
        window.close()
        deadline = monotonic() + 15
        while window.isVisible() and monotonic() < deadline:
            app.processEvents()
            sleep(0.005)
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.setQuitOnLastWindowClosed(quit_on_close)
        qInstallMessageHandler(previous_handler)
    assert not messages
