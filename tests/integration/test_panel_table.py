import os
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from astromosaic.storage.project import FileReference, MosaicProject, ProjectPanel, load_project


def test_workspace_reflows_across_full_hd_display_scales(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QPoint, QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QSplitter

    from astromosaic.ui.panel_table import COLUMNS
    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    settings = QSettings(str(tmp_path / "workspace.ini"), QSettings.Format.IniFormat)
    window = ProjectWindow(use_gpu=False, preferences=settings)
    if len(app.screens()) > 1:
        window.setScreen(app.screens()[1])
        window.move(app.screens()[1].availableGeometry().topLeft())
    window.show()
    try:
        splitter = window.findChild(QSplitter)
        assert splitter is not None
        # Logical client sizes allow for the Windows taskbar and window frame.
        for width, height in ((1280, 648), (1536, 800), (1920, 1008)):
            window.resize(width, height)
            app.processEvents()
            if splitter.orientation() == Qt.Orientation.Horizontal:
                assert window.viewport.canvas.height() >= height // 3
                assert window.viewport.canvas.width() >= width * 0.4
            else:
                required = sum(splitter.widget(i).minimumSizeHint().width() for i in (0, 1))
                assert required + splitter.handleWidth() > splitter.width()
            assert window.command_panel.entry.isVisibleTo(window)
            if width == 1920:
                assert splitter.orientation() == Qt.Orientation.Horizontal
                table = window.panels
                band = COLUMNS.index("Band")
                assert table.columnViewportPosition(band) + table.columnWidth(band) <= (
                    table.viewport().width()
                )

        handle = splitter.handle(1)
        center = handle.rect().center()
        previous = splitter.sizes()
        QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=center)
        QTest.mouseMove(handle, center + QPoint(36, 0))
        QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=handle.rect().center())
        adjusted = splitter.sizes()
        assert adjusted[0] > previous[0]

        window.resize(800, 650)
        app.processEvents()
        assert splitter.orientation() == Qt.Orientation.Vertical
        assert window.width() == 800 and window.viewport.canvas.height() >= 100
        window.resize(1920, 1008)
        app.processEvents()
        assert abs(splitter.sizes()[0] - adjusted[0]) <= 1
    finally:
        window.close()


def test_workspace_control_states_have_distinct_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QAction, QImage, QPalette
    from PySide6.QtWidgets import QApplication, QSplitter

    from astromosaic.ui.panel_table import panel_row
    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    preferences = QSettings(str(tmp_path / "appearance.ini"), QSettings.Format.IniFormat)
    window = ProjectWindow(use_gpu=False, preferences=preferences)
    secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
    if secondary is not None:
        window.move(secondary.availableGeometry().center() - window.rect().center())
    window.show()

    def pixel(image: QImage, x: int, y: int) -> str:
        scale = image.devicePixelRatio()
        return image.pixelColor(int((x + 0.5) * scale), int((y + 0.5) * scale)).name()

    try:
        table = window.panels
        rows = []
        for index in range(2):
            source = tmp_path / f"panel-{index}.fits"
            fits.writeto(source, np.ones((8, 12), dtype=np.float32))
            panel = ProjectPanel(FileReference.capture(source))
            rows.append(panel_row(panel, None, None, None))
        table.properties.refresh(rows)
        table.selectRow(0)
        assert window.add_button.isEnabled() and not window.preview_button.isEnabled()
        splitter = window.findChild(QSplitter)
        handle = splitter.handle(1)

        themes = {a.text(): a for a in window.findChildren(QAction) if a.text() in {"Dark", "Light"}}
        for theme in ("Dark", "Light"):
            themes[theme].trigger()
            app.processEvents()
            palette = app.palette()
            accent = palette.color(QPalette.ColorRole.Accent).name()
            enabled = window.add_button.grab().toImage()
            disabled = window.preview_button.grab().toImage()
            assert len({pixel(enabled, x, 0) for x in range(10, 40)}) == 1
            assert len({pixel(disabled, x, 0) for x in range(10, 40)}) > 1

            cells = table.viewport().grab().toImage()
            for column in ("Panel", "Weight"):
                selected = table.visualRect(table.cell(0, column))
                unselected = table.visualRect(table.cell(1, column))
                assert pixel(cells, selected.center().x(), selected.top()) == accent
                assert pixel(cells, selected.center().x(), selected.bottom()) == accent
                assert pixel(cells, unselected.center().x(), unselected.top()) != accent

            grip = handle.grab().toImage()
            center = handle.rect().center()
            assert all(pixel(grip, center.x() + x, center.y()) == accent for x in (-9, 0, 9))
            assert all(pixel(grip, center.x() + x, center.y()) != accent for x in (-5, 5))
    finally:
        window.close()


def test_panel_grid_edits_and_appearance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtGui import QAction, QPalette
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLineEdit

    from astromosaic.ui.panel_table import COLUMNS
    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    settings = QSettings(str(tmp_path / "appearance.ini"), QSettings.Format.IniFormat)
    window = ProjectWindow(use_gpu=False, preferences=settings)
    source = tmp_path / "science.fits"
    fits.writeto(
        source,
        np.ones((8, 12), dtype=np.float32),
        fits.Header({"FOCALLEN": 380, "XPIXSZ": 3.8, "INSTRUME": "Test camera", "FILTER": "R"}),
    )
    project = MosaicProject((ProjectPanel(FileReference.capture(source)),))
    manifest = tmp_path / "test.astromosaic"
    window._set_project(project, manifest)

    try:
        secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
        if secondary is not None:
            window.move(secondary.availableGeometry().center() - window.rect().center())
        window.show()
        window.activateWindow()
        assert window._inspection_job is not None and window._inspection_job.wait(5000)
        app.processEvents()
        table = window.panels
        window.resize(800, 650)
        app.processEvents()
        assert table.font().pointSizeF() == app.font().pointSizeF()
        assert table.font().pointSizeF() >= 12 or table.font().pixelSize() >= 16
        assert table.viewport().height() >= table.rowHeight(0)
        critical_columns = ("Panel", "Sky", "WCS", "Solve result", "Weight", "Band")
        assert COLUMNS[: len(critical_columns)] == critical_columns
        header = table.horizontalHeader()
        for name in critical_columns:
            column = table.cell(0, name).column()
            assert not table.isColumnHidden(column)
            assert table.columnWidth(column) >= header.sectionSizeHint(column)
        window.resize(1140, 780)
        app.processEvents()
        table.setCurrentIndex(table.cell(0, "Size (px)"))
        table.setFocus()
        QTest.keyClick(table, Qt.Key.Key_Tab)
        assert app.focusWidget() is window.auto_frame_check
        QTest.keyClick(window.auto_frame_check, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
        assert app.focusWidget() is table
        table.setCurrentIndex(table.cell(0, "Panel"))
        QTest.keyClick(table, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
        previous = app.focusWidget()
        assert previous is not None and previous.accessibleName() == "More panel actions"
        QTest.keyClick(previous, Qt.Key.Key_Tab)
        assert app.focusWidget() is table
        QTest.keyClick(table, Qt.Key.Key_Right)
        assert table.currentIndex() == table.cell(0, "Sky")
        assert table.cell(0, "WCS").data() == "Missing"
        assert table.cell(0, "Camera").data() == "Test camera"
        assert table.cell(0, "Size (px)").data() == "12 × 8"
        window.table_view.setCurrentText("Optics")
        focal = table.cell(0, "Focal length (mm)")
        assert focal.data() == "380" and not table.isColumnHidden(focal.column())
        assert table.isColumnHidden(table.cell(0, "Weight").column())
        table.setCurrentIndex(focal)
        QTest.keyClick(table, Qt.Key.Key_F2)
        edit = table.findChild(QLineEdit)
        assert edit is not None
        edit.selectAll()
        QTest.keyClicks(edit, "500")
        QTest.keyClick(edit, Qt.Key.Key_Return)
        app.processEvents()
        assert focal.data() == "500" and window.project.panels[0].optics.focal_length_mm == 500
        assert table.cell(0, "Embedded focal (mm)").data() == "380"
        assert table.properties.setData(focal, "")
        assert focal.data() == "380" and window.project.panels[0].optics.focal_length_mm is None
        window.table_view.setCurrentText("All properties")
        assert all(not table.isColumnHidden(i) for i in range(len(COLUMNS)))
        assert table.cell(0, "Source path").data() == str(source)
        assert not table.properties.setData(table.cell(0, "Weight"), "0")
        assert "positive" in window.status.text()
        assert table.properties.setData(table.cell(0, "Weight"), "1.5")
        assert table.properties.setData(table.cell(0, "Band"), "Ha")
        sky = table.cell(0, "Sky")
        table.setCurrentIndex(sky)
        QTest.keyClick(table, Qt.Key.Key_Space)
        assert sky.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Unchecked
        assert window._save()
        panel = load_project(manifest).panels[0]
        assert (panel.include_sky, panel.weight, panel.band_override) == (False, 1.5, "Ha")

        dark = app.palette().color(QPalette.ColorRole.Window)
        assert dark.lightness() < 128
        light_action = next(a for a in window.findChildren(QAction) if a.text() == "Light")
        light_action.trigger()
        assert app.palette().color(QPalette.ColorRole.Window).lightness() > 128
        assert table.viewport().palette().color(QPalette.ColorRole.Base).lightness() > 128
        assert window.panel_heading.palette().color(QPalette.ColorRole.WindowText).lightness() < 128
        assert settings.value("appearance/theme") == "Light"
        assert window.project == window._saved
        reopened = ProjectWindow(use_gpu=False, preferences=settings)
        try:
            assert next(
                a for a in reopened.findChildren(QAction) if a.text() == "Light"
            ).isChecked()
            next(a for a in reopened.findChildren(QAction) if a.text() == "Dark").trigger()
            assert app.palette().color(QPalette.ColorRole.Window) == dark
        finally:
            reopened.close()
    finally:
        window._saved = window.project
        window.close()
