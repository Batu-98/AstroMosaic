"""Verify the resolution selector builds the displayed overview at the selected scale."""

import os
from pathlib import Path
from time import monotonic, sleep
from typing import cast

import pytest

from astromosaic.display import DisplayFrame


def test_preview_resolution_selector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEvent, QSettings
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.mosaic_job import PreviewJob
    from astromosaic.ui.project_window import ProjectWindow

    manifest = (
        Path(__file__).resolve().parents[2] / "data/application-tests/sky01-m17-atlas/project.astromosaic"
    )
    if not manifest.is_file():
        pytest.skip("Prepare the real M17 reference in docs/phase-6.md.")
    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = cast(QApplication | None, QApplication.instance()) or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = ProjectWindow(use_gpu=False, preferences=settings)
    monkeypatch.setattr(window.viewport, "overview_edge", lambda: 512)
    combo = window.viewport.resolution_box

    def wait_idle() -> None:
        deadline = monotonic() + 20
        while window.job is not None or window._inspection_job is not None:
            assert monotonic() < deadline, window.status.text()
            app.processEvents()
            sleep(0.005)

    def finish(scale: int) -> DisplayFrame:
        job = window.job
        assert isinstance(job, PreviewJob) and job.resolution_scale == scale
        assert not combo.isEnabled()
        wait_idle()
        assert combo.isEnabled()
        frame = window.viewport.frame
        assert frame is not None and frame.has_coverage
        return frame

    try:
        secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
        if secondary is not None:
            window.move(secondary.availableGeometry().center() - window.rect().center())
        window.resize(630, 760)
        window.show()
        assert combo.currentText() == "50%" and combo.isVisible()
        assert [combo.itemText(index) for index in range(combo.count())] == [
            "25%", "50%", "75%", "100%"
        ]
        window._open_project(manifest)
        wait_idle()
        window.live_preview_action.setChecked(False)
        window.preview_button.click()
        half = finish(50)
        combo.setCurrentIndex(combo.findData(100))
        full = finish(100)
        combo.setCurrentIndex(combo.findData(25))
        quarter = finish(25)
        assert max(half.size) == round(max(full.size) / 2)
        assert max(quarter.size) == round(max(full.size) / 4)
        assert full.output_size == half.output_size == quarter.output_size
        assert full.tone_levels == half.tone_levels == quarter.tone_levels
        assert window.project == window._saved
    finally:
        window.close()
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
