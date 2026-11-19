"""Share pan, zoom, and stretch controls across the two preview surfaces."""

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, QTimer, Slot
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from astromosaic.display import (
    DEFAULT_MIDTONES,
    MAX_MIDTONES,
    MIN_MIDTONES,
    DisplayFrame,
    stretch_rgba,
)
from astromosaic.ui.preview_gl import BACKGROUND_RGB, OpenGLPreview


class _RasterPreview(QWidget):
    def __init__(self, view: "SkyViewport") -> None:
        super().__init__()
        self._view = view
        self._image = QImage()

    def set_display(self, frame: DisplayFrame | None, midtones: float) -> None:
        self._image = QImage()
        if frame is not None:
            pixels = stretch_rgba(frame, midtones)
            width, height = frame.size
            self._image = QImage(
                pixels.data, width, height, width * 4, QImage.Format.Format_RGBA8888
            ).copy()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor(*BACKGROUND_RGB))
            if self._image.isNull():
                painter.setPen(QColor("#b9c4d2"))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Build a sky preview.")
            else:
                painter.drawImage(self._view.image_rect(), self._image)
        finally:
            painter.end()


class SkyViewport(QWidget):
    def __init__(self, *, use_gpu: bool = True) -> None:
        super().__init__()
        self._use_gpu = use_gpu and QApplication.platformName() not in {"minimal", "offscreen"}
        self._gl: OpenGLPreview | None = None
        self._frame: DisplayFrame | None = None
        self._zoom = 1.0
        self._pan = QPointF()
        self._drag: QPointF | None = None

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

    def _configure_canvas(self, canvas: QWidget) -> None:
        canvas.setAccessibleName("Mosaic preview")
        self._pages.addWidget(canvas)
        canvas.installEventFilter(self)

    def set_frame(self, frame: DisplayFrame | None) -> None:
        previous = self._frame
        self._frame = frame
        if frame is None or previous is None or frame.output_size != previous.output_size:
            self.fit()
        self.fit_button.setEnabled(frame is not None)
        self.midtones.setEnabled(frame is not None)
        if frame is not None and self._use_gpu and self._gl is None:
            gl = self._gl = OpenGLPreview(self.image_rect)
            gl.failed.connect(self._fallback, Qt.ConnectionType.QueuedConnection)
            self._configure_canvas(gl)
            self._pages.setCurrentWidget(gl)
        if frame is None:
            if self._gl is not None:
                self._gl.set_display(None, self.midtones.value() / 100)
            self._pages.setCurrentWidget(self._raster)
        elif self._gl is not None:
            self._pages.setCurrentWidget(self._gl)
        self._backend.setText(self.backend if frame is not None else "")
        self._update_display()

    @Slot()
    def _check_context(self) -> None:
        if self._gl is not None and self._gl.isVisible() and not self._gl.isValid():
            self._fallback("Qt could not create the OpenGL preview context.")

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
        if self._gl is None:
            return
        self._use_gpu = False
        self.release_opengl()
        self._backend.setToolTip(reason)
        self._backend.setText(self.backend if self._frame is not None else "")
        self._update_display()

    @Slot()
    def _update_display(self) -> None:
        surface = self._gl if self.canvas is self._gl else self._raster
        assert surface is not None
        surface.set_display(self._frame, self.midtones.value() / 100)

    @Slot()
    def fit(self) -> None:
        self._zoom = 1.0
        self._pan = QPointF()
        self._drag = None
        self.canvas.unsetCursor()
        self.canvas.update()

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
            if isinstance(event, QWheelEvent):
                delta = event.angleDelta().y() or event.pixelDelta().y()
                steps = min(12.0, max(-12.0, delta / 120))
                zoom = min(128.0, max(0.5, self._zoom * 1.2**steps))
                toward = event.position() - QPointF(
                    self.canvas.width() / 2, self.canvas.height() / 2
                )
                self._pan = toward + (self._pan - toward) * (zoom / self._zoom)
                self._zoom = zoom
                self.canvas.update()
                return True
            if isinstance(event, QMouseEvent):
                return self._mouse_event(kind, event)
        return super().eventFilter(watched, event)

    def _mouse_event(self, kind: QEvent.Type, event: QMouseEvent) -> bool:
        if kind == QEvent.Type.MouseMove and self._drag is not None:
            self._pan += event.position() - self._drag
            self._drag = event.position()
            self.canvas.update()
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
