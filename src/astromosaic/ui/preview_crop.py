"""Output-pixel crop handles for the preview canvas."""

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF

from astromosaic.core import Region


def screen_rect(region: Region, image: QRectF, size: tuple[int, int]) -> QRectF:
    x_scale, y_scale = image.width() / size[0], image.height() / size[1]
    return QRectF(
        image.x() + x_scale * region.x,
        image.y() + y_scale * region.y,
        x_scale * region.width,
        y_scale * region.height,
    )


def output_point(point: QPointF, image: QRectF, size: tuple[int, int]) -> QPointF:
    return QPointF(
        (point.x() - image.x()) * size[0] / image.width(),
        (point.y() - image.y()) * size[1] / image.height(),
    )


def adjust_crop(
    crop: Region, dx: int, dy: int, size: tuple[int, int], *,
    horizontal: int = 0, vertical: int = 0,
) -> Region:
    width, height = size
    left, top = crop.x, crop.y
    right, bottom = left + crop.width, top + crop.height
    if not horizontal and not vertical:
        return Region(
            max(0, min(width - crop.width, left + dx)),
            max(0, min(height - crop.height, top + dy)),
            crop.width, crop.height,
        )
    if horizontal < 0:
        left = max(0, min(right - 1, left + dx))
    elif horizontal > 0:
        right = min(width, max(left + 1, right + dx))
    if vertical < 0:
        top = max(0, min(bottom - 1, top + dy))
    elif vertical > 0:
        bottom = min(height, max(top + 1, bottom + dy))
    return Region(left, top, right - left, bottom - top)


@dataclass(frozen=True, slots=True)
class CropDrag:
    crop: Region
    start: QPointF
    horizontal: int
    vertical: int

    @classmethod
    def begin(
        cls, crop: Region, point: QPointF, image: QRectF, size: tuple[int, int]
    ) -> "CropDrag | None":
        bounds = screen_rect(crop, image, size)
        if not bounds.adjusted(-8, -8, 8, 8).contains(point):
            return None
        left, right = abs(point.x() - bounds.left()), abs(point.x() - bounds.right())
        top, bottom = abs(point.y() - bounds.top()), abs(point.y() - bounds.bottom())
        horizontal = (-1 if left <= right else 1) if min(left, right) <= 8 else 0
        vertical = (-1 if top <= bottom else 1) if min(top, bottom) <= 8 else 0
        return cls(crop, output_point(point, image, size), horizontal, vertical)

    def update(self, point: QPointF, size: tuple[int, int]) -> Region:
        dx = round(point.x() - self.start.x())
        dy = round(point.y() - self.start.y())
        return adjust_crop(
            self.crop, dx, dy, size, horizontal=self.horizontal, vertical=self.vertical,
        )
