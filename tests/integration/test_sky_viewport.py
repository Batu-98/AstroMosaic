import os
from dataclasses import replace
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
        check_samples()
        viewport.tone_box.setCurrentIndex(1)
        assert not viewport.midtones.isEnabled()
        check_samples(preserve_tone=True)

        if use_gpu:

            def fail_upload(*args: object) -> None:
                raise RuntimeError("Test preview texture upload failure.")

            monkeypatch.setattr(OpenGLPreview, "_upload", fail_upload)
            viewport.set_frame(replace(frame))
            screenshot()
            app.processEvents()
            assert viewport.backend == "CPU"
            check_samples(preserve_tone=True)
    finally:
        viewport.close()
        viewport.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
