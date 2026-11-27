import os
from dataclasses import replace
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from astromosaic.core import Region
from astromosaic.display import DisplayFrame, stretch_rgba


@pytest.mark.parametrize("use_gpu", [False, True], ids=["cpu", "opengl"])
def test_sky_viewport_pixels_pan_zoom_and_stretch(
    use_gpu: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    if use_gpu and os.environ.get("ASTROMOSAIC_TEST_OPENGL") != "1":
        pytest.skip("Set ASTROMOSAIC_TEST_OPENGL=1 on a native desktop with OpenGL 3.2.")

    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QImage, QWheelEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.preview_gl import BACKGROUND_RGB, OpenGLPreview
    from astromosaic.ui.sky_viewport import SkyViewport

    if not use_gpu and "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = cast(QApplication | None, QApplication.instance()) or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    viewport = SkyViewport(use_gpu=use_gpu)
    viewport.resize(400, 320)
    rgba = np.array(
        [
            [[0.0, 0.0, 0.0, 1.0], [0.2, 0.5, 0.8, 1.0], [0.0, 0.0, 0.0, 0.0]],
            [[0.9, 0.6, 0.3, 1.0], [0.0, 1.0, 0.25, 1.0], [1.0, 1.0, 1.0, 1.0]],
        ],
        dtype=np.float32,
    )
    rgba.setflags(write=False)
    frame = DisplayFrame((3, 2), rgba, True)

    def screenshot() -> QImage:
        app.processEvents()
        canvas = viewport.canvas
        if isinstance(canvas, OpenGLPreview):
            assert canvas.isValid()
            return canvas.grabFramebuffer()
        return canvas.grab().toImage()

    def check_samples(*, preserve_tone: bool = False) -> None:
        image = screenshot()
        assert not image.isNull()
        rect = viewport.image_rect()
        expected = stretch_rgba(frame, viewport.midtones.value() / 100, preserve_tone=preserve_tone)
        for row, col in np.ndindex(expected.shape[:2]):
            x = rect.x() + rect.width() * (col + 0.5) / 3
            y = rect.y() + rect.height() * (row + 0.5) / 2
            color = image.pixelColor(
                int(x * image.width() / viewport.canvas.width()),
                int(y * image.height() / viewport.canvas.height()),
            )
            truth = expected[row, col, :3] if expected[row, col, 3] else BACKGROUND_RGB
            actual = (color.red(), color.green(), color.blue())
            np.testing.assert_allclose(actual, truth, atol=1, rtol=0)

    try:
        secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
        if secondary is not None:
            viewport.move(secondary.availableGeometry().center() - viewport.rect().center())
        viewport.show()
        viewport.activateWindow()
        viewport.set_frame(frame)
        viewport.midtones.setValue(50)
        check_samples()
        assert viewport.backend == ("OpenGL" if use_gpu else "CPU")
        image, canvas = screenshot(), viewport.canvas
        assert (image.width(), image.height()) == (
            round(canvas.width() * canvas.devicePixelRatioF()),
            round(canvas.height() * canvas.devicePixelRatioF()),
        )
        original = viewport.image_rect()
        viewport.fit_button.setFocus()
        QTest.keyClick(viewport.fit_button, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
        navigation = app.focusWidget()
        assert navigation is not None and navigation.accessibleName() == "Mosaic preview"
        QTest.keyClick(navigation, Qt.Key.Key_Right)
        QTest.keyClick(navigation, Qt.Key.Key_Down)
        panned = viewport.image_rect()
        assert panned.x() < original.x() and panned.y() < original.y()
        assert panned.size() == original.size()
        QTest.keyClick(navigation, Qt.Key.Key_Equal)
        keyboard_zoom = viewport.image_rect()
        assert keyboard_zoom.width() == pytest.approx(1.2 * panned.width())
        assert keyboard_zoom.center().x() == pytest.approx(
            original.center().x() + 1.2 * (panned.center().x() - original.center().x())
        )
        QTest.keyClick(navigation, Qt.Key.Key_Minus)
        assert viewport.image_rect().width() == pytest.approx(panned.width())
        QTest.keyClick(navigation, Qt.Key.Key_Home)
        assert viewport.image_rect() == original
        QTest.keyClick(navigation, Qt.Key.Key_Tab)
        assert app.focusWidget() is viewport.fit_button

        anchor = original.center() + QPointF(30, -20)
        zoom = QWheelEvent(
            anchor,
            canvas.mapToGlobal(anchor),
            QPoint(),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(canvas, zoom)
        zoomed = viewport.image_rect()
        assert zoomed.width() == pytest.approx(1.2 * original.width())
        assert (anchor.x() - original.x()) / original.width() == pytest.approx(
            (anchor.x() - zoomed.x()) / zoomed.width()
        )
        assert (anchor.y() - original.y()) / original.height() == pytest.approx(
            (anchor.y() - zoomed.y()) / zoomed.height()
        )
        start = anchor.toPoint()
        end = start + QPoint(25, -13)
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(canvas, end)
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)
        delta = viewport.image_rect().topLeft() - zoomed.topLeft()
        assert (delta.x(), delta.y()) == pytest.approx((25, -13))
        QTest.mouseClick(viewport.fit_button, Qt.MouseButton.LeftButton)
        assert viewport.image_rect() == original

        viewport.midtones.setValue(25)
        assert viewport.frame is frame
        check_samples()
        np.testing.assert_array_equal(frame.rgba, rgba)

        detail = DisplayFrame((3, 2), np.array([[[0, 1, 0, 1]]], dtype=np.float32), True)
        viewport.set_detail(Region(1, 0, 1, 1), detail)
        image = screenshot()
        center = viewport.image_rect()
        pixel = image.pixelColor(
            int(center.center().x() * image.width() / viewport.canvas.width()),
            int((center.y() + center.height() / 4) * image.height() / viewport.canvas.height()),
        )
        assert (pixel.red(), pixel.green(), pixel.blue()) == (0, 255, 0)
        viewport.clear_detail()

        preserved = rgba.copy()
        preserved[..., :3] *= 0.5
        preserved.setflags(write=False)
        frame = replace(frame, photo_levels=(0.0, 0.5), preserved_rgba=preserved)
        viewport.set_frame(frame)
        assert not viewport.midtones.isEnabled()
        check_samples(preserve_tone=True)
        viewport.tone_box.setCurrentIndex(0)
        assert viewport.midtones.isEnabled()
        check_samples()
        viewport.tone_box.setCurrentIndex(1)

        if use_gpu:

            def fail_upload(*args: object) -> None:
                raise RuntimeError("Test preview texture upload failure.")

            monkeypatch.setattr(OpenGLPreview, "_upload", fail_upload)
            navigation.setFocus()
            viewport.set_frame(replace(frame))
            screenshot()
            app.processEvents()
            assert viewport.backend == "CPU"
            assert app.focusWidget() is navigation
            before = viewport.image_rect()
            QTest.keyClick(navigation, Qt.Key.Key_Plus, Qt.KeyboardModifier.ShiftModifier)
            assert viewport.image_rect().width() == pytest.approx(1.2 * before.width())
            QTest.keyClick(navigation, Qt.Key.Key_Home)
            check_samples(preserve_tone=True)
    finally:
        viewport.close()
        viewport.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("use_gpu", [False, True], ids=["cpu", "opengl"])
def test_overlap_toggle_recolors_the_displayed_detail(
    use_gpu: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("PySide6")
    if use_gpu and os.environ.get("ASTROMOSAIC_TEST_OPENGL") != "1":
        pytest.skip("Set ASTROMOSAIC_TEST_OPENGL=1 on a native desktop with OpenGL 3.2.")

    from PySide6.QtCore import QEvent, QSettings
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.preview_gl import BACKGROUND_RGB, OpenGLPreview
    from astromosaic.ui.preview_state import PreviewResult
    from astromosaic.ui.project_window import ProjectWindow

    if not use_gpu and "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = cast(QApplication | None, QApplication.instance()) or QApplication([])
    quit_on_close = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)
    window = ProjectWindow(
        use_gpu=use_gpu,
        preferences=QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat),
    )
    viewport = window.viewport
    window.layer_box.setCurrentText("Composition")

    rgba = np.full((2, 4, 4), 0.4, dtype=np.float32)
    rgba[..., 3] = 1
    rgba[0, 3, 3] = 0
    common = np.array([[True, True, False, False], [False] * 4])
    overview = DisplayFrame((4, 2), rgba, True, common_coverage=common)
    region = Region(1, 0, 3, 1)
    detail = DisplayFrame(
        overview.output_size,
        np.array([[[0.25, 0.25, 0.25, 1], [0.15, 0.15, 0.15, 1], [0, 0, 0, 0]]], np.float32),
        True,
        common_coverage=common[region.slices],
    )

    def row_colors() -> list[tuple[int, int, int]]:
        app.processEvents()
        canvas = viewport.canvas
        image = (
            canvas.grabFramebuffer() if isinstance(canvas, OpenGLPreview) else canvas.grab().toImage()
        )
        assert not image.isNull()
        rect = viewport.image_rect()
        y = int((rect.y() + rect.height() / 4) * image.height() / canvas.height())
        colors = []
        for column in range(4):
            color = image.pixelColor(
                int((rect.x() + rect.width() * (column + 0.5) / 4) * image.width() / canvas.width()),
                y,
            )
            colors.append((color.red(), color.green(), color.blue()))
        return colors

    try:
        secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
        if secondary is not None:
            window.move(secondary.availableGeometry().center() - window.rect().center())
        window.show()
        selection = window._preview_selection()
        state = window._preview_state
        assert state.complete(state.start(selection), selection, PreviewResult(overview)) is not None
        window._update_preview_view()
        viewport.midtones.setValue(37)
        viewport.set_detail(region, detail)
        before = row_colors()
        rect = viewport.image_rect()
        assert viewport.backend == ("OpenGL" if use_gpu else "CPU")
        assert before[0] != before[1] and before[3] == BACKGROUND_RGB
        assert window.overlap_check.isEnabled()

        window.overlap_check.click()
        highlighted = row_colors()
        assert highlighted[0] != before[0]
        np.testing.assert_allclose(highlighted[1], highlighted[0], atol=1, rtol=0)
        assert highlighted[2:] == before[2:]
        assert viewport.detail == region and viewport.image_rect() == rect
        assert viewport._backend.text().endswith(" · 1:1")

        window.overlap_check.click()
        assert row_colors() == before
        assert viewport.detail == region and viewport.image_rect() == rect
    finally:
        window.close()
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.setQuitOnLastWindowClosed(quit_on_close)
