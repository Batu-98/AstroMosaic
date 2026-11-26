"""Share pan, zoom, and stretch controls across the two preview surfaces."""

from math import ceil, floor, sqrt

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from astromosaic.core import Region
from astromosaic.display import (
    DEFAULT_MIDTONES,
    MAX_MIDTONES,
    MIN_MIDTONES,
    DisplayFrame,
    highlight_overlap,
    stretch_rgba,
)
from astromosaic.photometry.photo import PhotoTone
from astromosaic.pipeline.mosaic import MAX_DETAIL_PIXELS, MAX_OVERVIEW_EDGE
from astromosaic.ui.preview_crop import CropDrag, output_point, screen_rect
from astromosaic.ui.preview_gl import BACKGROUND_RGB, OpenGLPreview


class _RasterPreview(QWidget):
    def __init__(self, view: "SkyViewport") -> None:
        super().__init__()
        self._view = view
        self._image = QImage()

    def set_display(
        self, frame: DisplayFrame | None, midtones: float, *, preserve_tone: bool = False
    ) -> None:
        self._image = QImage()
        if frame is not None:
            self._image = _display_image(frame, midtones, preserve_tone)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor(*BACKGROUND_RGB))
            if self._image.isNull():
                painter.setPen(QColor("#b9c4d2"))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Build a sky preview.")
            else:
                rect = self._view.image_rect()
                painter.setRenderHint(
                    QPainter.RenderHint.SmoothPixmapTransform,
                    rect.width() * self.devicePixelRatioF() < self._image.width(),
                )
                painter.drawImage(rect, self._image)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
                self._view.paint_overlay(painter)
        finally:
            painter.end()


def _display_image(
    frame: DisplayFrame, midtones: float, preserve_tone: bool, *, highlight_common: bool = False
) -> QImage:
    pixels = stretch_rgba(
        frame, midtones, preserve_tone=preserve_tone, highlight_common=highlight_common
    )
    width, height = frame.size
    return QImage(
        pixels.data, width, height, width * 4, QImage.Format.Format_RGBA8888
    ).copy()


class SkyViewport(QWidget):
    view_changed = Signal()
    crop_changed = Signal(object)

    def __init__(self, *, use_gpu: bool = True) -> None:
        super().__init__()
        self._use_gpu = use_gpu and QApplication.platformName() not in {"minimal", "offscreen"}
        self._gl: OpenGLPreview | None = None
        self._frame: DisplayFrame | None = None
        self._highlight_common = False
        self._zoom = 1.0
        self._pan = QPointF()
        self._drag: QPointF | None = None
        self._crop: Region | None = None
        self._editing_crop = False
        self._crop_drag: CropDrag | None = None
        self._detail: tuple[Region, DisplayFrame] | None = None
        self._detail_image = QImage()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        surface = QFrame()
        surface.setFrameShape(QFrame.Shape.StyledPanel)
        surface.setMinimumHeight(190)
        self._pages = QStackedLayout(surface)
        self._raster = _RasterPreview(self)
        self._configure_canvas(self._raster)
        layout.addWidget(surface, 1)

        controls = QHBoxLayout()
        self.fit_button = QPushButton("Fit View")
        self.fit_button.clicked.connect(self.fit)
        controls.addWidget(self.fit_button)
        self.midtones = QSlider(Qt.Orientation.Horizontal)
        self.midtones.setRange(MIN_MIDTONES, MAX_MIDTONES)
        self.midtones.setValue(DEFAULT_MIDTONES)
        self.midtones.setMaximumWidth(180)
        self.midtones.setAccessibleName("Preview midtones")
        self.midtones.valueChanged.connect(self._update_display)
        label = QLabel("Midtones")
        label.setBuddy(self.midtones)
        controls.addWidget(label)
        controls.addWidget(self.midtones)
        self.tone_box = QComboBox()
        self.tone_box.setAccessibleName("Photo mosaic tone")
        self.tone_box.addItem("Use Preview Tone")
        self.tone_box.addItem("Preserve Tone")
        self.tone_box.setCurrentIndex(1)
        self.tone_box.currentIndexChanged.connect(self._update_display)
        controls.addWidget(self.tone_box)
        controls.addStretch()
        self._backend = QLabel()
        controls.addWidget(self._backend)
        layout.addLayout(controls)
        self.set_frame(None)

    @property
    def frame(self) -> DisplayFrame | None:
        return self._frame

    @property
    def canvas(self) -> QWidget:
        canvas = self._pages.currentWidget()
        assert canvas is not None
        return canvas

    @property
    def backend(self) -> str:
        return "OpenGL" if self.canvas is self._gl else "CPU"

    def photo_tone(self) -> PhotoTone | None:
        if self._frame is None or self._frame.photo_levels is None:
            raise ValueError("Build a covered sRGB sky preview before exporting a photo.")
        if self.tone_box.currentIndex() == 1:
            return None
        return PhotoTone(self.midtones.value() / 100, self._frame.photo_levels)

    @property
    def crop(self) -> Region | None:
        return self._crop

    @property
    def detail(self) -> Region | None:
        return self._detail[0] if self._detail is not None else None

    def set_crop(self, crop: Region | None, *, editing: bool = False) -> None:
        self._crop, self._editing_crop = crop, editing
        self._crop_drag = None
        self.canvas.unsetCursor()
        self.canvas.update()

    def set_detail(self, region: Region, frame: DisplayFrame) -> None:
        self._detail = region, frame
        self._backend.setText(f"{self.backend} · 1:1")
        self._update_display()

    def clear_detail(self) -> None:
        self._detail = None
        self._detail_image = QImage()
        self._backend.setText(self.backend if self._frame is not None else "")
        self.canvas.update()

    def overview_edge(self) -> int:
        width, height = self.canvas.width(), self.canvas.height()
        fitted_edge = min(width, height)
        if self._frame is not None:
            x, y = self._frame.output_size
            fitted_edge = round(max(x, y) * min(width / x, height / y))
        physical = fitted_edge * self.canvas.devicePixelRatioF()
        return max(512, min(MAX_OVERVIEW_EDGE, ceil(physical * 1.25 / 128) * 128))

    def visible_detail(self) -> Region | None:
        frame = self._frame
        if (
            frame is None or frame.size == frame.output_size
            or self._zoom <= 1.0 or frame.tone_levels is None
        ):
            return None
        image = self.image_rect()
        size = frame.output_size
        if image.width() * self.canvas.devicePixelRatioF() / size[0] < 0.55:
            return None
        visible = image.intersected(QRectF(self.canvas.rect()))
        if visible.isEmpty():
            return None
        start = output_point(visible.topLeft(), image, size)
        end = output_point(visible.bottomRight(), image, size)
        left, top = max(0, floor(start.x())), max(0, floor(start.y()))
        right, bottom = min(size[0], ceil(end.x())), min(size[1], ceil(end.y()))
        width, height = right - left, bottom - top
        if width * height <= MAX_DETAIL_PIXELS:
            return Region(left, top, width, height)
        ratio = sqrt(MAX_DETAIL_PIXELS / (width * height))
        bounded_width = max(1, int(width * ratio))
        bounded_height = max(1, min(MAX_DETAIL_PIXELS // bounded_width, int(height * ratio)))
        return Region(
            left + (width - bounded_width) // 2,
            top + (height - bounded_height) // 2,
            bounded_width,
            bounded_height,
        )

    def _configure_canvas(self, canvas: QWidget) -> None:
        canvas.setAccessibleName("Mosaic preview")
        self._pages.addWidget(canvas)
        canvas.installEventFilter(self)

    def set_frame(self, frame: DisplayFrame | None, *, highlight_common: bool = False) -> None:
        previous = self._frame
        self._frame = highlight_overlap(frame) if frame is not None and highlight_common else frame
        self._highlight_common = highlight_common
        if frame is None or previous is None or frame.output_size != previous.output_size:
            self.clear_detail()
            self.fit()
        self.fit_button.setEnabled(frame is not None)
        self.tone_box.setVisible(frame is not None and frame.photo_levels is not None)
        self._select_canvas()

    def set_gpu_enabled(self, enabled: bool) -> None:
        self._use_gpu = enabled and QApplication.platformName() not in {"minimal", "offscreen"}
        if not self._use_gpu:
            self.release_opengl()
        self._backend.setToolTip("")
        self._select_canvas()

    def _select_canvas(self) -> None:
        frame = self._frame
        if frame is not None and self._use_gpu and self._gl is None:
            gl = self._gl = OpenGLPreview(self.image_rect, self._paint_gl_overlay)
            gl.failed.connect(self._fallback, Qt.ConnectionType.QueuedConnection)
            self._configure_canvas(gl)
        if frame is None:
            if self._gl is not None:
                self._gl.set_display(None, self.midtones.value() / 100)
            self._pages.setCurrentWidget(self._raster)
        elif self._gl is not None:
            self._pages.setCurrentWidget(self._gl)
        self._backend.setText(
            f"{self.backend} · 1:1" if self._detail is not None
            else self.backend if frame is not None else ""
        )
        self._update_display()

    @Slot()
    def _check_context(self) -> None:
        if self._gl is not None and self._gl.isVisible() and not self._gl.isValid():
            self._gl.failed.emit("Qt could not create the OpenGL preview context.")

    def release_opengl(self) -> None:
        """Release the preview's resources on the UI thread before removing its widget."""
        if self._gl is None:
            return
        gl, self._gl = self._gl, None
        gl.release_resources()
        self._pages.setCurrentWidget(self._raster)
        self._pages.removeWidget(gl)
        gl.deleteLater()

    @Slot(str)
    def _fallback(self, reason: str) -> None:
        if self._gl is None or self.sender() is not self._gl:
            return
        self.set_gpu_enabled(False)
        self._backend.setToolTip(reason)

    @Slot()
    def _update_display(self) -> None:
        surface = self._gl if self.canvas is self._gl else self._raster
        assert surface is not None
        frame = self._frame
        preserve = frame is not None and frame.photo_levels is not None and (
            self.tone_box.currentIndex() == 1
        )
        self.midtones.setEnabled(frame is not None and not preserve)
        midtones = self.midtones.value() / 100
        if self._detail is not None:
            self._detail_image = _display_image(
                self._detail[1], midtones, preserve, highlight_common=self._highlight_common
            )
        surface.set_display(frame, midtones, preserve_tone=preserve)

    @Slot()
    def fit(self) -> None:
        self._zoom = 1.0
        self._pan = QPointF()
        self._drag = None
        self.canvas.unsetCursor()
        self.clear_detail()
        self.canvas.update()
        self.view_changed.emit()

    def image_rect(self) -> QRectF:
        if self._frame is None:
            return QRectF()
        width, height = self._frame.output_size
        view_width, view_height = self.canvas.width(), self.canvas.height()
        scale = self._zoom * min(view_width / width, view_height / height)
        width_on_screen, height_on_screen = width * scale, height * scale
        return QRectF(
            (view_width - width_on_screen) / 2 + self._pan.x(),
            (view_height - height_on_screen) / 2 + self._pan.y(),
            width_on_screen,
            height_on_screen,
        )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._gl and event.type() == QEvent.Type.Show:
            QTimer.singleShot(0, self._check_context)
        if self._frame is not None and watched is self._pages.currentWidget():
            kind = event.type()
            if kind in (QEvent.Type.Resize, QEvent.Type.DevicePixelRatioChange):
                self.view_changed.emit()
            if isinstance(event, QWheelEvent):
                delta = event.angleDelta().y() or event.pixelDelta().y()
                steps = min(12.0, max(-12.0, delta / 120))
                width, height = self._frame.output_size
                fit = min(self.canvas.width() / width, self.canvas.height() / height)
                physical = max(fit * self.canvas.devicePixelRatioF(), 1e-12)
                limit = max(128.0, 4.0 / physical)
                zoom = min(limit, max(0.5, self._zoom * 1.2**steps))
                toward = event.position() - QPointF(
                    self.canvas.width() / 2, self.canvas.height() / 2
                )
                self._pan = toward + (self._pan - toward) * (zoom / self._zoom)
                self._zoom = zoom
                self.canvas.update()
                self.view_changed.emit()
                return True
            if isinstance(event, QMouseEvent):
                return self._mouse_event(kind, event)
        return super().eventFilter(watched, event)

    def _mouse_event(self, kind: QEvent.Type, event: QMouseEvent) -> bool:
        if self._editing_crop and self._crop is not None and self._edit_crop(kind, event):
            return True
        if kind == QEvent.Type.MouseMove and self._drag is not None:
            self._pan += event.position() - self._drag
            self._drag = event.position()
            self.canvas.update()
            self.view_changed.emit()
            return True
        if event.button() == Qt.MouseButton.LeftButton:
            if kind == QEvent.Type.MouseButtonPress:
                self._drag = event.position()
                self.canvas.setCursor(Qt.CursorShape.ClosedHandCursor)
                return True
            if kind == QEvent.Type.MouseButtonRelease:
                self._drag = None
                self.canvas.unsetCursor()
                return True
            if kind == QEvent.Type.MouseButtonDblClick:
                self.fit()
                return True
        return False

    def _edit_crop(self, kind: QEvent.Type, event: QMouseEvent) -> bool:
        frame, crop = self._frame, self._crop
        assert frame is not None and crop is not None
        image = self.image_rect()
        point = event.position()
        if kind == QEvent.Type.MouseMove and self._crop_drag is not None:
            area = self._crop_drag.update(output_point(point, image, frame.output_size), frame.output_size)
            if area != crop:
                self._crop = area
                self.crop_changed.emit(area)
                self.canvas.update()
            return True
        if kind == QEvent.Type.MouseMove and self._drag is None:
            handle = CropDrag.begin(crop, point, image, frame.output_size)
            cursor = Qt.CursorShape.ArrowCursor
            if handle is not None:
                if handle.horizontal and handle.vertical:
                    cursor = (
                        Qt.CursorShape.SizeFDiagCursor if handle.horizontal == handle.vertical
                        else Qt.CursorShape.SizeBDiagCursor
                    )
                elif handle.horizontal:
                    cursor = Qt.CursorShape.SizeHorCursor
                elif handle.vertical:
                    cursor = Qt.CursorShape.SizeVerCursor
                else:
                    cursor = Qt.CursorShape.SizeAllCursor
            self.canvas.setCursor(cursor)
        if event.button() == Qt.MouseButton.LeftButton:
            if kind == QEvent.Type.MouseButtonPress:
                self._crop_drag = CropDrag.begin(crop, point, image, frame.output_size)
                return self._crop_drag is not None
            if kind == QEvent.Type.MouseButtonRelease and self._crop_drag is not None:
                self._crop_drag = None
                return True
        return False

    def _paint_gl_overlay(self) -> None:
        if self._crop is not None or self._detail is not None:
            painter = QPainter(self.canvas)
            try:
                self.paint_overlay(painter)
            finally:
                painter.end()

    def paint_overlay(self, painter: QPainter) -> None:
        if self._frame is None:
            return
        image = self.image_rect()
        size = self._frame.output_size
        if self._detail is not None and not self._detail_image.isNull():
            rect = screen_rect(self._detail[0], image, size)
            painter.fillRect(rect, QColor(*BACKGROUND_RGB))
            painter.drawImage(rect, self._detail_image)
        if self._crop is None or image.isEmpty():
            return
        bounds = screen_rect(self._crop, image, size)
        ink = QColor(231, 249, 255, 255 if self._editing_crop else 175)
        if self._editing_crop:
            outside, inside = QPainterPath(), QPainterPath()
            outside.addRect(image)
            inside.addRect(bounds)
            painter.fillPath(outside.subtracted(inside), QColor(0, 0, 0, 96))
        if bounds.width() > 2 and bounds.height() > 2:
            stroke = bounds.adjusted(1, 1, -1, -1)
            painter.setPen(QPen(QColor(0, 0, 0, 200), 3))
            painter.drawRect(stroke)
            painter.setPen(QPen(ink, 1.5))
            painter.drawRect(stroke)
        if self._editing_crop:
            left, middle, right = bounds.left(), bounds.center().x(), bounds.right()
            top, center, bottom = bounds.top(), bounds.center().y(), bounds.bottom()
            for x, y in (
                (left, top), (middle, top), (right, top), (left, center), (right, center),
                (left, bottom), (middle, bottom), (right, bottom),
            ):
                painter.fillRect(QRectF(x - 3, y - 3, 6, 6), QColor(12, 20, 26))
                painter.fillRect(QRectF(x - 2, y - 2, 4, 4), ink)
