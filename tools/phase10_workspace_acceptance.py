"""Replay Phase 10B on a native Windows display using M17 and PA4."""

import argparse
import json
from pathlib import Path
from statistics import quantiles

from phase10_workspace_baseline import (
    FirstPaint,
    Workspace,
    apply_large_text,
    wait_events,
    wait_for,
)
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


def run(args: argparse.Namespace, app: QApplication) -> dict[str, object]:
    settings = QSettings(str(args.output / "preferences.ini"), QSettings.Format.IniFormat)
    settings.setValue("appearance/theme", args.theme)
    window = Workspace(settings, use_gpu=not args.cpu)
    screen = next(
        (screen for screen in app.screens() if screen != app.primaryScreen()), app.primaryScreen()
    )
    assert screen is not None
    window.setScreen(screen)
    window.move(screen.availableGeometry().topLeft())
    window.resize(args.width, args.height)
    window.show()
    window.activateWindow()
    wait_for(window.isActiveWindow, "active test window")
    if args.large:
        apply_large_text(args.theme)
    nav = window.navigation
    preview = window.viewport
    m17 = args.fixtures / "sky01-m17-atlas/project.astromosaic"

    def settled() -> bool:
        return (
            window.job is None
            and window._inspection_job is None
            and window._detail_job is None
            and not window._adaptive_timer.isActive()
        )

    def switch(index: int, *, mouse: bool = False) -> None:
        if nav.currentRow() == index:
            return
        if mouse:
            position = nav.visualItemRect(nav.item(index)).center()
            QTest.mouseClick(nav.viewport(), Qt.MouseButton.LeftButton, pos=position)
        else:
            nav.setFocus()
            QTest.keyClick(nav, Qt.Key.Key_Down if index else Qt.Key.Key_Up)
        assert nav.currentRow() == index and nav.item(index).isSelected()

    def focus_mode() -> None:
        QTest.keyClick(
            nav,
            Qt.Key.Key_F,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )

    def timing(action: str, *, busy: bool) -> dict[str, float]:
        samples = []
        for trial in range(22):
            if action == "focus":
                switch(1)
            if busy:
                window._start_preview()
                assert window.job is not None and window.cancel_button.isVisible()
            if action == "view":
                target = 1 - nav.currentRow()
                paint = FirstPaint(nav.viewport(), lambda target=target: nav.currentRow() == target)
                elapsed = paint.measure(
                    lambda target=target, mouse=trial % 2 == 0: switch(target, mouse=mouse)
                )
            else:
                expected = not window.focus_mode_action.isChecked()
                paint = FirstPaint(
                    window.centralWidget(),
                    window.exit_focus_button.isVisible
                    if expected
                    else window.exit_focus_button.isHidden,
                )
                elapsed = paint.measure(focus_mode)
                assert window.focus_mode_action.isChecked() == expected
            if busy:
                assert window.job is not None
                window.cancel_button.click()
                wait_for(settled, "preview cancellation")
                assert "cancelled" in window.status.text().lower()
            if trial >= 2:
                samples.append(elapsed)
        if window.focus_mode_action.isChecked():
            focus_mode()
        p95 = quantiles(samples, n=20, method="inclusive")[-1]
        assert p95 <= (100 if busy else 50) and max(samples) <= 200, (action, busy, samples)
        return {"p95_ms": round(p95, 2), "max_ms": max(samples)}

    try:
        assert window.command_toggle.isVisible() and not window.command_panel.isVisible()
        window._open_project(m17)
        switch(1)
        wait_for(lambda: settled() and window.preview_button.isEnabled(), "M17 inspection")
        window.command_toggle.click()
        window.preview_button.click()
        switch(0, mouse=True)
        wait_for(settled, "M17 preview in Panels")
        assert preview.frame is not None and preview.frame.has_coverage
        switch(1)
        wait_events(400)
        wait_for(settled, "settled M17 preview")
        assert preview.backend == ("CPU" if args.cpu else "OpenGL")
        expanded = preview.canvas.height()
        assert (window.width(), window.height()) == (args.width, args.height)
        assert expanded >= 100 and window.command_panel.entry.isVisible(), (
            expanded, window.command_dock.height(), window.command_panel.entry.isVisible()
        )

        preview.focus_crop()
        QTest.keyClick(app.focusWidget(), Qt.Key.Key_Equal)
        QTest.keyClick(app.focusWidget(), Qt.Key.Key_Right)
        wait_events(400)
        wait_for(settled, "settled zoom")
        rect = preview.image_rect()
        frame = preview.frame
        guard = (window.project, window._revision, window.undo_action.text(), window.preview_jobs)
        view_idle = timing("view", busy=False)
        wait_events(400)
        assert preview.image_rect() == rect and preview.frame is frame
        assert guard == (
            window.project,
            window._revision,
            window.undo_action.text(),
            window.preview_jobs,
        )
        switch(1)
        QTest.keyClick(nav, Qt.Key.Key_Tab)
        assert app.focusWidget().accessibleName() == "Mosaic preview"

        window.edit_crop_button.click()
        wait_for(settled, "crop preview")
        assert preview.crop is not None
        QTest.keyClick(app.focusWidget(), Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
        draft = preview.crop
        switch(0)
        switch(1, mouse=True)
        assert preview.crop == draft and window.crop_controls.isVisible()
        window.cancel_crop_button.click()

        window.command_panel.entry.setText("Unsubmitted command")
        window.command_toggle.click()
        wait_events(400)
        wait_for(settled, "collapsed preview")
        gained = preview.canvas.height() - expanded
        focus_mode()
        wait_events(50)
        ratio = preview.canvas.width() / window.centralWidget().width()
        assert not window.command_toggle.isVisible() and window.exit_focus_button.isVisible()
        if args.width == 1920:
            assert gained >= 100 and ratio >= 0.9
        switch(0)
        assert not window.focus_mode_action.isChecked() and window.command_toggle.isVisible()
        window.command_toggle.click()
        assert window.command_panel.entry.text() == "Unsubmitted command"
        focus_idle = timing("focus", busy=False)
        wait_events(400)
        wait_for(settled, "idle focus measurements")
        view_busy = timing("view", busy=True)
        focus_busy = timing("focus", busy=True)

        switch(0)
        window._open_project(args.fixtures / "owner01-pa4/all-panels-unaligned.astromosaic")
        if args.width <= 800:
            wait_for(settled, "PA4 inspection")
            table = window.panels
            table.selectRow(21)
            table.scrollToBottom()
            scroll = table.verticalScrollBar().value()
            assert scroll > 0
            switch(1)
            switch(0)
            assert table.currentIndex().row() == 21 and table.verticalScrollBar().value() == scroll
        return {
            "title": window._app_title,
            "screen_scale": screen.devicePixelRatio(),
            "preview_height_expanded": expanded,
            "height_recovered": gained,
            "focus_width_ratio": round(ratio, 4),
            "view_idle": view_idle,
            "focus_idle": focus_idle,
            "view_busy": view_busy,
            "focus_busy": focus_busy,
        }
    finally:
        window.close()
        wait_for(lambda: not window.isVisible(), "closed workspace")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=Path("data/application-tests"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1001)
    parser.add_argument("--theme", choices=("Dark", "Light"), default="Dark")
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--large", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = run(args, QApplication([]))
    result = json.dumps(report, indent=2)
    (args.output / "results.json").write_text(result, encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
