import os
from pathlib import Path
from time import monotonic, sleep

import pytest

from astromosaic.pipeline.smoke import write_smoke_panel
from astromosaic.storage.project import MosaicProject, save_project


def test_workspace_roundtrip_reset_and_cancelled_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QRect, QSettings, Qt
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.project_window import ProjectWindow
    from astromosaic.ui.workspace_settings import LAYOUT_KEY, RECENT_KEY, WorkspaceSettings

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    screen = next(
        (screen for screen in app.screens() if screen != app.primaryScreen()), app.primaryScreen()
    )
    assert screen is not None
    config = tmp_path / "settings.ini"
    settings = QSettings(str(config), QSettings.Format.IniFormat)
    settings.setValue("appearance/theme", "Light")
    path = tmp_path / "Recent.astromosaic"
    settings.setValue(RECENT_KEY, [str(path)])
    window = ProjectWindow(use_gpu=False, preferences=settings)
    window.show_workspace(screen)
    app.processEvents()
    assert window.isMaximized() and window.navigation.currentRow() == 0
    assert window.recent_list.count() == 1 and window.open_button.isVisible()
    assert window.command_toggle.isVisible() and not window.command_dock.isVisible()
    window.showNormal()
    target = QRect(
        screen.availableGeometry().topLeft(),
        window.size().boundedTo(screen.availableGeometry().size()),
    )
    target.adjust(24, 48, -60, -48)
    window.setGeometry(target)
    window.command_toggle.click()
    app.processEvents()
    window.navigation.setCurrentRow(1)
    window.focus_mode_action.setChecked(True)
    assert not window.command_dock.isVisible()
    assert window.close()
    persisted = WorkspaceSettings.read(settings.value(LAYOUT_KEY))
    assert persisted is not None and persisted.display == "expanded" and not persisted.maximized

    restored_settings = QSettings(str(config), QSettings.Format.IniFormat)
    restored = ProjectWindow(use_gpu=False, preferences=restored_settings)
    restored.show_workspace(screen)
    app.processEvents()
    assert not restored.isMaximized() and restored.navigation.currentRow() == 0
    assert screen.availableGeometry().contains(restored.frameGeometry())
    assert restored.command_dock.isVisible() and restored.recent_list.count() == 1
    restored.navigation.setCurrentRow(1)
    assert restored.command_dock.isVisible()
    before = restored_settings.value(LAYOUT_KEY)
    with monkeypatch.context() as patch:
        patch.setattr(restored, "_confirm_discard", lambda: False)
        assert not restored.close() and restored.isVisible()
        assert restored_settings.value(LAYOUT_KEY) == before
    project = restored.project
    restored._reset_workspace()
    assert restored.project is project and restored.navigation.currentRow() == 0
    assert (
        restored.recent_list.count() == 1 and restored_settings.value("appearance/theme") == "Light"
    )
    assert not restored.command_dock.isVisible() and restored.isMaximized()
    assert restored.close()

    layout = persisted.settings()
    layout["floating"] = {"screen": screen.name(), "rect": [60, 80, 430, 240]}
    settings.setValue(LAYOUT_KEY, layout)
    floating = ProjectWindow(use_gpu=False, preferences=settings)
    floating.show_workspace(screen)
    app.processEvents()
    assert floating.command_dock.isFloating() and floating.command_dock.isVisible()
    assert screen.availableGeometry().contains(floating.command_dock.frameGeometry())
    assert floating.close()

    layout["window"] = {"screen": "Removed display", "rect": [3200, 1800, 1800, 1000]}
    layout["floating"] = {"screen": "Removed display", "rect": [10, 10, 380, 210]}
    settings.setValue(LAYOUT_KEY, layout)
    moved = ProjectWindow(use_gpu=False, preferences=settings)
    moved.show_workspace()
    app.processEvents()
    assert moved.screen().availableGeometry().contains(moved.frameGeometry())
    assert moved.command_dock.isVisible() and not moved.command_dock.isFloating()
    assert moved.dockWidgetArea(moved.command_dock) == Qt.DockWidgetArea.BottomDockWidgetArea
    assert moved.close()

    settings.setValue(LAYOUT_KEY, {"version": 1, "window": {"rect": ["invalid"]}})
    fallback = ProjectWindow(use_gpu=False, preferences=settings)
    fallback.show_workspace(screen)
    assert fallback.isMaximized() and not fallback.command_dock.isVisible()
    assert fallback.close()


def test_recent_projects_and_drop_preserve_the_project_on_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QMimeData, QPointF, QSettings, Qt, QUrl
    from PySide6.QtGui import QDropEvent
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = ProjectWindow(use_gpu=False, preferences=settings)
    secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
    window.show_workspace(secondary)

    def drop(*paths: Path) -> None:
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
        event = QDropEvent(
            QPointF(50, 90),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        window.dropEvent(event)
        assert event.isAccepted()

    def idle() -> None:
        deadline = monotonic() + 12
        while window.job is not None or window._inspection_job is not None:
            app.processEvents()
            assert monotonic() < deadline, window.status.text()
            sleep(0.005)

    first = tmp_path / "Gökyüzü" / "Mosaic.astromosaic"
    second = tmp_path / "Başka" / first.name
    absent = tmp_path / "Missing.astromosaic"
    for path in (first, second, absent):
        path.parent.mkdir(exist_ok=True)
        save_project(path, MosaicProject())
        drop(path)
        assert window.project_path == path
    assert window._recent_projects == (absent, second, first)
    drop(first)
    assert window._recent_projects == (first, absent, second)
    absent.unlink()
    window._new_project()
    assert window.recent_list.isVisible() and window.recent_list.count() == 3
    assert first.parent.name in window.recent_list.item(0).text()
    window._remove_unavailable_recents()
    assert list(window._recent_projects) == [first, second]

    error_titles: list[str] = []
    monkeypatch.setattr(window, "_error", lambda title, _error: error_titles.append(title))
    before = window.project
    revision = window._revision
    drop(absent)
    assert (
        error_titles == ["Open failed"]
        and window.project is before
        and window._revision == revision
    )

    image = tmp_path / "first.fits"
    image2 = tmp_path / "second.fits"
    invalid = tmp_path / "invalid.fits"
    write_smoke_panel(image)
    write_smoke_panel(image2)
    invalid.write_text("Invalid FITS data", encoding="ascii")
    drop(first, image)
    assert "by itself" in window.status.text() and window.project is before
    drop(image, invalid)
    idle()
    assert "Cannot read invalid.fits" in window.status.text()
    assert window.project is before and window._revision == revision

    drop(image, image2)
    drop(first)
    assert "current operation" in window.status.text()
    idle()
    assert len(window.project.panels) == 2 and window.undo_action.text() == "&Undo Add Panels"
    edited = window.project
    drop(image)
    idle()
    assert window.project is edited and "already added" in window.status.text()
    with monkeypatch.context() as patch:
        patch.setattr(window, "_confirm_discard", lambda: False)
        drop(first)
    assert window.project is edited and window.project_path is None
    window.undo_action.trigger()
    idle()
    assert window.project is before and not window.undo_action.isEnabled()
    window.recent_menu.actions()[-1].trigger()
    assert not window._recent_projects and window.recent_list.count() == 0
    window._set_recent(tuple(tmp_path / f"Project {index}.astromosaic" for index in range(10)))
    assert window.recent_list.count() == 8
    assert window.close()
