"""Edit a source-coordinate mask over a bounded panel preview."""

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from astromosaic.core.masks import FOREGROUND, SKY, UNCLASSIFIED, SourceMask, paint_stroke
from astromosaic.display import DEFAULT_MIDTONES, stretch_rgba
from astromosaic.ui.mosaic_job import MaskEditorFrame

_COLORS = np.array([(175, 129, 214, 90), (64, 183, 231, 95), (246, 161, 67, 130)], dtype=np.uint8)
_TOOLS = (None, SKY, FOREGROUND, UNCLASSIFIED)


class _MaskCanvas(QWidget):
    edited = Signal()

    def __init__(self, frame: MaskEditorFrame, parent: QWidget) -> None:
        super().__init__(parent)
        self.setMinimumSize(360, 260)
        self.setAccessibleName("Panel sky mask overlay")
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.source_size = frame.image.output_size
        self.width_cells, self.height_cells = frame.image.size
        self._base = self._image(stretch_rgba(frame.image, DEFAULT_MIDTONES / 100).tobytes())
        self._uncovered = frame.image.rgba[..., 3] == 0
        self._initial = frame.proposed or frame.saved
        self.grid = np.zeros((self.height_cells, self.width_cells), dtype=np.uint8)
        self.tool: int | None = None
        self.radius = 8
        self.show_overlay = True
        self._point: tuple[int, int] | None = None
        self.restore()

    def _image(self, rgba: bytes) -> QImage:
        return QImage(
            rgba,
            self.width_cells,
            self.height_cells,
            4 * self.width_cells,
            QImage.Format.Format_RGBA8888,
        ).copy()

    def restore(self) -> None:
        self.grid[:] = self._initial.grid() if self._initial is not None else UNCLASSIFIED
        self._update_overlay()

    def _update_overlay(self) -> None:
        rgba = _COLORS[self.grid]
        rgba[self._uncovered, 3] = 0
        self._overlay = self._image(rgba.tobytes())
        self.update()

    def image_rect(self) -> QRectF:
        width, height = self.source_size
        scale = min(self.width() / width, self.height() / height)
        w, h = width * scale, height * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor("#131b25"))
            painter.drawImage(self.image_rect(), self._base)
            if self.show_overlay:
                painter.drawImage(self.image_rect(), self._overlay)
        finally:
            painter.end()

    def _cell(self, position: QPointF) -> tuple[int, int]:
        rect = self.image_rect()
        x = int((position.x() - rect.x()) * self.width_cells / rect.width())
        y = int((position.y() - rect.y()) * self.height_cells / rect.height())
        return (
            max(0, min(self.width_cells - 1, x)),
            max(0, min(self.height_cells - 1, y)),
        )

    def _paint_to(self, position: QPointF) -> None:
        end = self._cell(position)
        paint_stroke(self.grid, self._point or end, end, self.tool, self.radius)
        self._point = end
        self._update_overlay()
        self.edited.emit()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.image_rect().contains(
            event.position()
        ):
            self._paint_to(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._point is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._paint_to(event.position())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._point is not None and event.button() == Qt.MouseButton.LeftButton:
            self._paint_to(event.position())
            self._point = None


class MaskEditor(QDialog):
    def __init__(
        self, name: str, frame: MaskEditorFrame, *, proposed: bool, attached: bool, parent: QWidget
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Sky mask — {name}")
        self.resize(820, 660)
        self.result_mask: SourceMask | None = None
        self.canvas = _MaskCanvas(frame, self)

        layout = QVBoxLayout(self)
        if frame.attachment_error is not None or attached or proposed:
            if frame.attachment_error is not None:
                message = f"Attached FITS mask could not be displayed. {frame.attachment_error}"
            elif attached:
                message = "Applying edits replaces the attached FITS mask with the editable grid."
            elif frame.proposed is None:
                message = "No reliable horizon found. Trace the horizon or paint the mask."
            else:
                message = "Review the proposed horizon before applying the mask."
            notice = QLabel(message)
            notice.setTextFormat(Qt.TextFormat.PlainText)
            notice.setWordWrap(True)
            layout.addWidget(notice)
        layout.addWidget(self.canvas, 1)

        controls = QHBoxLayout()
        self.tool = QComboBox()
        self.tool.addItems(["Trace horizon", "Paint sky", "Paint foreground", "Paint unclassified"])
        self.tool.setAccessibleName("Mask tool")
        self.tool.currentIndexChanged.connect(self._tool_changed)
        controls.addWidget(self.tool)
        self.radius = QSpinBox()
        self.radius.setRange(1, 80)
        self.radius.setValue(self.canvas.radius)
        self.radius.setSuffix(" cells")
        self.radius.setAccessibleName("Brush radius")
        self.radius.valueChanged.connect(self._set_radius)
        controls.addWidget(self.radius)
        self.tool.setCurrentIndex(1 if frame.proposed is not None or frame.saved is not None else 0)
        self._tool_changed(self.tool.currentIndex())
        controls.addStretch()
        overlay = QCheckBox("Show mask")
        overlay.setChecked(True)
        overlay.toggled.connect(self._show_overlay)
        controls.addWidget(overlay)
        reset = QPushButton("Reset Edits")
        reset.clicked.connect(self._reset)
        controls.addWidget(reset)
        layout.addLayout(controls)

        width, height = frame.image.size
        legend = QLabel(
            '<span style="color: #40b7e7">■</span> Sky &nbsp; '
            '<span style="color: #f6a143">■</span> Foreground &nbsp; '
            '<span style="color: #af81d6">■</span> Unclassified'
            f" &nbsp;&nbsp; {width} × {height} mask cells"
        )
        layout.addWidget(legend)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        apply = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert apply is not None
        self.apply_button = apply
        apply.setText("Apply Mask")
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        if frame.saved is not None or attached:
            remove = buttons.addButton("Remove Mask", QDialogButtonBox.ButtonRole.ResetRole)
            remove.clicked.connect(self._remove)
        layout.addWidget(buttons)
        self.canvas.edited.connect(self._update_actions)
        self._update_actions()

    def _tool_changed(self, index: int) -> None:
        self.canvas.tool = _TOOLS[index]
        self.radius.setEnabled(self.canvas.tool is not None)

    def _set_radius(self, radius: int) -> None:
        self.canvas.radius = radius

    def _show_overlay(self, visible: bool) -> None:
        self.canvas.show_overlay = visible
        self.canvas.update()

    def _reset(self) -> None:
        self.canvas.restore()
        self._update_actions()

    def _update_actions(self) -> None:
        self.apply_button.setEnabled(bool(self.canvas.grid.any()))

    def _apply(self) -> None:
        self.result_mask = SourceMask(self.canvas.source_size, self.canvas.grid.tobytes())
        self.accept()

    def _remove(self) -> None:
        self.result_mask = None
        self.accept()
