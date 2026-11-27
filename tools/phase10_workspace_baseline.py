"""Measure the native Windows workspace before changing its layout."""

import argparse
import json
import os
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from PySide6.QtCore import QEvent, QEventLoop, QObject, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QFont, QFontDatabase, QKeySequence, QShortcut
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDockWidget, QWidget

from astromosaic.ui.appearance import apply_theme
from astromosaic.ui.mosaic_job import PreviewJob
from astromosaic.ui.project_window import ProjectWindow


def wait_events(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def wait_for(check: Callable[[], bool], description: str, timeout: float = 45) -> None:
    deadline = perf_counter() + timeout
    while not check():
        if perf_counter() > deadline:
            raise RuntimeError(f"Timed out waiting for {description}.")
        wait_events(5)


class Workspace(ProjectWindow):
    def __init__(self, settings: QSettings, *, use_gpu: bool) -> None:
        self.preview_jobs = 0
        super().__init__(use_gpu=use_gpu, preferences=settings)

    def _launch_job(self, job, message):
        self.preview_jobs += isinstance(job, PreviewJob)
        super()._launch_job(job, message)


class FirstPaint(QObject):
    def __init__(self, target: QWidget, changed: Callable[[], bool]) -> None:
        super().__init__()
        self.target = target
        self.changed = changed
        self.seconds: float | None = None

    def eventFilter(self, watched, event):
        if watched is self.target and event.type() == QEvent.Type.Paint and self.changed():
            self.seconds = self.seconds or perf_counter()
        return False

    def measure(self, action: Callable[[], None]) -> float:
        self.target.installEventFilter(self)
        try:
            started = perf_counter()
            action()
            wait_for(lambda: self.seconds is not None, "changed widget paint", 3)
            assert self.seconds is not None
            return round((self.seconds - started) * 1000, 2)
        finally:
            self.target.removeEventFilter(self)


def dimensions(widget: QWidget) -> list[int]:
    return [widget.width(), widget.height()]


def layout(window: Workspace, dock: QDockWidget) -> dict[str, object]:
    table = window.panels
    header = table.horizontalHeader()
    columns = []
    for index in range(table.model().columnCount()):
        left = header.sectionViewportPosition(index)
        right = left + header.sectionSize(index)
        if not header.isSectionHidden(index) and left >= 0 and right <= table.viewport().width():
            columns.append(table.model().headerData(index, Qt.Orientation.Horizontal))
    row = table.visualRect(table.model().index(0, 0))
    canvas = window.viewport.canvas
    return {
        "client": dimensions(window),
        "outer_logical": [window.frameGeometry().width(), window.frameGeometry().height()],
        "preview": dimensions(canvas),
        "table": dimensions(table),
        "dock": dimensions(dock) if dock.isVisible() else None,
        "body_pt": table.font().pointSizeF(),
        "dpr": canvas.devicePixelRatioF(),
        "columns": columns,
        "full_first_row": row.isValid()
        and 0 <= row.top() <= row.bottom() < table.viewport().height(),
        "captured_status": window.status.text(),
    }


def keyboard_route(start: QWidget, key: Qt.Key) -> list[str]:
    def name(widget: QWidget) -> str:
        text = getattr(widget, "text", None)
        return widget.accessibleName() or (text() if callable(text) else type(widget).__name__)

    start.setFocus()
    visited = []
    for _ in range(45):
        focused = QApplication.focusWidget()
        assert focused is not None
        label = name(focused)
        if visited and focused is start:
            return visited
        visited.append(label)
        QTest.keyClick(focused, key)
    raise RuntimeError("The keyboard route did not return to its first control.")


def verify_shortcut(window: Workspace, target: QWidget) -> None:
    key = QKeySequence("Ctrl+Shift+F")
    shortcut = QShortcut(key, window)
    activations = []
    shortcut.activated.connect(lambda: activations.append(True))
    try:
        target.setFocus()
        focused = QApplication.focusWidget()
        assert focused is not None and (focused is target or target.isAncestorOf(focused))
        QTest.keyClick(
            focused,
            Qt.Key.Key_F,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        assert activations == [True], "The proposed focus shortcut was intercepted."
    finally:
        shortcut.setEnabled(False)
        shortcut.deleteLater()


def measure_busy_cancel(window: Workspace, settled: Callable[[], bool]) -> list[float]:
    samples = []
    cancel = window.cancel_button
    for _ in range(8):
        window.preview_button.click()
        assert cancel.isEnabled() and cancel.isVisible()
        cancel.setFocus()
        assert QApplication.focusWidget() is cancel
        samples.append(
            FirstPaint(window.status, lambda: "cancel" in window.status.text().lower()).measure(
                lambda: QTest.keyClick(cancel, Qt.Key.Key_Space)
            )
        )
        wait_for(settled, "cancelled preview job")
    return samples


def apply_large_text(theme: str = "Dark") -> None:
    system_font = QFontDatabase.systemFont

    def larger_font(role: QFontDatabase.SystemFont) -> QFont:
        font = system_font(role)
        font.setPointSize(14)
        return font

    with patch.object(QFontDatabase, "systemFont", larger_font):
        apply_theme(theme)


def record(args: argparse.Namespace, app: QApplication) -> dict[str, object]:
    settings = QSettings(str(args.output / "preferences.ini"), QSettings.Format.IniFormat)
    window = Workspace(settings, use_gpu=not args.cpu)
    screen = next(
        (item for item in app.screens() if item != app.primaryScreen()), app.primaryScreen()
    )
    assert screen is not None
    work = screen.availableGeometry()
    screen_size = screen.size()
    window.setScreen(screen)
    window.move(work.topLeft())
    window.show()
    window.activateWindow()
    wait_for(window.isActiveWindow, "active test window")
    dock = window.findChild(QDockWidget)
    assert dock is not None
    dpr = screen.devicePixelRatio()
    frame_margin = window.windowHandle().frameMargins()
    width = round(1920 / dpr) - frame_margin.left() - frame_margin.right()
    height = round(1032 / dpr) - frame_margin.top() - frame_margin.bottom()
    window.resize(width, height)
    wait_events(250)

    def snapshot(name: str) -> dict[str, object]:
        measured = layout(window, dock)
        bounds = window.frameGeometry()
        image = screen.grabWindow(
            0,
            bounds.x() - screen.geometry().x(),
            bounds.y() - screen.geometry().y(),
            bounds.width(),
            bounds.height(),
        )
        if image.isNull() or not image.save(str(args.output / f"{name}.png")):
            raise RuntimeError(f"Could not capture {name}.")
        return measured

    def settled() -> bool:
        return (
            window.job is None
            and window._detail_job is None
            and not window._preview_timer.isActive()
        )

    def resize(w: int, h: int) -> None:
        window.resize(w, h)
        wait_events(500)
        wait_for(settled, "settled workspace layout")

    results: dict[str, object] = {
        "version": version("astromosaic"),
        "scale_requested": os.environ.get("QT_SCALE_FACTOR", "1"),
        "screen": {
            "secondary": screen != app.primaryScreen(),
            "dpr": dpr,
            "qt_logical_dpi": screen.logicalDotsPerInch(),
            "logical_size": [screen_size.width(), screen_size.height()],
            "logical_work_area": [work.width(), work.height()],
            "reference_physical": [1920, 1080],
            "reference_taskbar_allowance_physical": 48,
        },
    }
    try:
        results["empty"] = snapshot("empty")
        window._open_project(args.fixtures / "sky01-m17-atlas/project.astromosaic")
        wait_for(window.preview_button.isEnabled, "loaded M17")
        busy_feedback = FirstPaint(window.status, lambda: window.job is not None).measure(
            window.preview_button.click
        )
        assert window.cancel_button.isVisible() and window.cancel_button.isEnabled()
        results["busy"] = snapshot("busy")
        wait_for(settled, "M17 preview")
        assert window.viewport.frame is not None
        results["backend"] = window.viewport.backend
        results["m17"] = snapshot("m17")
        results["tab"] = keyboard_route(window.panels, Qt.Key.Key_Tab)
        results["backtab"] = keyboard_route(window.panels, Qt.Key.Key_Backtab)
        available = {
            sequence.toString()
            for action in window.findChildren(QAction)
            for sequence in action.shortcuts()
        }
        available.update(shortcut.key().toString() for shortcut in window.findChildren(QShortcut))
        candidate = QKeySequence("Ctrl+Shift+F")
        assert candidate.toString() not in available
        results["registered_shortcuts"] = sorted(available)
        verify_shortcut(window, window.panels)
        verify_shortcut(window, window.command_panel.entry)
        window.viewport.canvas.setFocus()
        idle = []
        for _ in range(12):
            before = window.viewport._zoom
            idle.append(
                FirstPaint(
                    window.viewport.canvas, lambda before=before: window.viewport._zoom != before
                ).measure(lambda: QTest.keyClick(window.viewport.canvas, Qt.Key.Key_Equal))
            )
            QTest.keyClick(window.viewport.canvas, Qt.Key.Key_Home)
            wait_events(25)
        wait_for(settled, "preview after keyboard input")
        window.edit_crop_button.click()
        wait_for(window.apply_crop_button.isEnabled, "crop editor")
        results["crop"] = snapshot("crop")
        verify_shortcut(window, window.viewport._surface)
        QTest.keyClick(window.viewport.canvas, Qt.Key.Key_Escape)
        if window.cancel_crop_button.isVisible():
            QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Escape)
        wait_for(lambda: window._preview_state.crop is None and settled(), "cancelled crop")

        start = window.preview_jobs
        window.command_panel_action.trigger()
        resize(width, height)
        results["m17_dock_hidden"] = snapshot("m17-dock-hidden")
        window.command_panel_action.trigger()
        resize(width, height)
        results["dock_round_trip_preview_jobs"] = window.preview_jobs - start
        start = window.preview_jobs
        compact_width = 800 if args.compact_text == 14 else 630
        resize(compact_width, 650)
        if args.compact_text == 14:
            apply_large_text()
            resize(compact_width, 650)
        assert window.panels.font().pointSizeF() == args.compact_text
        results["compact"] = snapshot("compact")
        resize(width, height)
        results["resize_round_trip_preview_jobs"] = window.preview_jobs - start
        resize(compact_width, 650)
        window._open_project(args.fixtures / "owner01-pa4/all-panels-unaligned.astromosaic")
        table = window.panels
        wait_for(lambda: table.verticalScrollBar().maximum() > 0, "scrollable PA4 panel table")
        table.scrollToBottom()
        wait_events(100)
        results["scroll"] = snapshot("scroll") | {
            "rows": table.model().rowCount(),
            "scroll_max": table.verticalScrollBar().maximum(),
            "scroll_value": table.verticalScrollBar().value(),
        }
        window._open_project(args.fixtures / "sky01-m17-atlas/project.astromosaic")
        wait_for(
            lambda: settled() and window.preview_button.isEnabled(), "M17 ready for cancellation"
        )
        results["response_ms"] = {
            "zoom_paints": idle,
            "build_busy_status_paint": busy_feedback,
            "busy_cancel_paints": measure_busy_cancel(window, settled),
        }
    finally:
        window.close()
        wait_for(lambda: not window.isVisible(), "window close")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=Path("data/application-tests"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--compact-text", choices=(12, 14), type=int, default=12)
    args = parser.parse_args()
    args.fixtures = args.fixtures.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    app = QApplication([])
    report = record(args, app)
    (args.output / "baseline.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
