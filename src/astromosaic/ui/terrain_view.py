"""Display a bounded foreground image with source-coordinate point markers."""

from bisect import bisect_right

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPen, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView, QWidget

from astromosaic.display import DEFAULT_MIDTONES, stretch_rgba
from astromosaic.pipeline.control_points import XY
from astromosaic.ui.terrain_job import TerrainImage


def _source_axis(offset: float, edges: tuple[int, ...]) -> float:
    cell = int(offset)
    start, end = edges[cell : cell + 2]
    return min(edges[-1] - 1, max(edges[0], start + (offset - cell) * (end - start) - 0.5))


def _scene_axis(pixel: float, edges: tuple[int, ...]) -> float | None:
    center = pixel + 0.5
    if not edges[0] <= center < edges[-1]:
        return None
    cell = bisect_right(edges, center) - 1
    start, end = edges[cell : cell + 2]
    return cell + (center - start) / (end - start)


class TerrainView(QGraphicsView):
    picked = Signal(object)
    detail_requested = Signal(object)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setMinimumSize(230, 165)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setBackgroundBrush(QColor("#151d27"))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._editing = False
        self._zoom_steps = 0
        self._edges: tuple[tuple[int, ...], tuple[int, ...]] | None = None
        self._bounds = QRectF()
        self._markers: list[QGraphicsItem] = []

    @property
    def has_image(self) -> bool:
        return self._edges is not None

    def show_image(self, frame: TerrainImage | None) -> None:
        scene = self.scene()
        scene.clear()
        self._markers.clear()
        self._edges = None
        self._bounds = QRectF()
        if frame is not None:
            width, height = frame.display.size
            region = frame.region
            self._edges = (
                tuple(region.x + i * region.width // width for i in range(width + 1)),
                tuple(region.y + i * region.height // height for i in range(height + 1)),
            )
            pixels = stretch_rgba(frame.display, DEFAULT_MIDTONES / 100).tobytes()
            image = QImage(pixels, width, height, width * 4, QImage.Format.Format_RGBA8888)
            scene.addPixmap(QPixmap.fromImage(image))
            self._bounds = QRectF(0, 0, width, height)
        self.setSceneRect(self._bounds)
        self.reset_view()

    def reset_view(self) -> None:
        self._zoom_steps = 0
        self.resetTransform()
        if self.has_image:
            self.fitInView(self._bounds, Qt.AspectRatioMode.KeepAspectRatio)

    def set_editing(self, editing: bool) -> None:
        self._editing = editing
        if editing:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.viewport().unsetCursor()
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def scene_position(self, xy: XY) -> QPointF | None:
        if self._edges is None:
            return None
        x, y = (_scene_axis(pixel, edges) for pixel, edges in zip(xy, self._edges, strict=True))
        return None if x is None or y is None else QPointF(x, y)

    def set_markers(self, rows: list[tuple[XY, str, str]]) -> None:
        scene = self.scene()
        for marker in self._markers:
            scene.removeItem(marker)
        self._markers.clear()
        for xy, color, label in rows:
            position = self.scene_position(xy)
            if position is None:
                continue
            marker = scene.addEllipse(-5, -5, 10, 10, QPen(QColor(color), 2))
            marker.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            marker.setPos(position)
            marker.setZValue(1)
            self._markers.append(marker)
            text = scene.addSimpleText(label)
            text.setParentItem(marker)
            text.setPos(6, -19)
            text.setPen(QPen(QColor("#151d27"), 2))
            text.setBrush(QColor(color))

    def _source_position(self, event: QMouseEvent) -> XY | None:
        point = self.mapToScene(event.position().toPoint())
        if self._edges is None or not self._bounds.contains(point):
            return None
        # Ignore the outer edge, which is beyond the last thumbnail cell.
        if point.x() >= self._bounds.width() or point.y() >= self._bounds.height():
            return None
        return _source_axis(point.x(), self._edges[0]), _source_axis(point.y(), self._edges[1])

    def mousePressEvent(self, event: QMouseEvent) -> None:
        right = event.button() == Qt.MouseButton.RightButton
        if right or (self._editing and event.button() == Qt.MouseButton.LeftButton):
            xy = self._source_position(event)
            if xy is not None:
                if right:
                    self.detail_requested.emit(xy)
                else:
                    self.picked.emit(xy)
            event.accept()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        increments = event.angleDelta().y()
        if self.has_image and increments != 0:
            steps = min(14, max(0, self._zoom_steps + (1 if increments > 0 else -1)))
            if steps == 0:
                self.reset_view()
            else:
                scale = 1.25 ** (steps - self._zoom_steps)
                self.scale(scale, scale)
            self._zoom_steps = steps
        event.accept()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._zoom_steps == 0 and self.has_image:
            self.reset_view()
