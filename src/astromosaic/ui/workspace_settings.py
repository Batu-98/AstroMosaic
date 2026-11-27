"""Read local workspace preferences using screen-relative logical coordinates."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from PySide6.QtCore import QMargins, QRect, QSize
from PySide6.QtGui import QScreen

LAYOUT_KEY = "workspace/layout"
RECENT_KEY = "workspace/recentProjects"
RECENT_LIMIT = 8
type CommandDisplay = Literal["hidden", "collapsed", "expanded"]


@dataclass(frozen=True, slots=True)
class WindowPlacement:
    screen: str
    rect: QRect

    @classmethod
    def capture(cls, rect: QRect, screen: QScreen) -> "WindowPlacement":
        return cls(screen.name(), rect.translated(-screen.availableGeometry().topLeft()))

    @classmethod
    def read(cls, value: object) -> "WindowPlacement | None":
        if not isinstance(value, dict):
            return None
        screen, rect = value.get("screen"), value.get("rect")
        if (
            not isinstance(screen, str)
            or not isinstance(rect, list)
            or len(rect) != 4
            or any(type(item) is not int or abs(item) > 100_000 for item in rect)
        ):
            return None
        bounds = QRect(*rect)
        return cls(screen, bounds) if 100 <= bounds.width() and 70 <= bounds.height() else None

    def settings(self) -> dict[str, object]:
        rect = self.rect
        return {"screen": self.screen, "rect": [rect.x(), rect.y(), rect.width(), rect.height()]}

    def absolute(self, work: QRect, minimum: QSize, margins: QMargins | None = None) -> QRect:
        usable = work if margins is None else work.marginsRemoved(margins)
        width = min(usable.width(), max(self.rect.width(), minimum.width()))
        height = min(usable.height(), max(self.rect.height(), minimum.height()))
        left = min(max(usable.x(), work.x() + self.rect.x()), usable.right() - width + 1)
        top = min(max(usable.y(), work.y() + self.rect.y()), usable.bottom() - height + 1)
        return QRect(left, top, width, height)


@dataclass(frozen=True, slots=True)
class WorkspaceSettings:
    window: WindowPlacement
    maximized: bool
    display: CommandDisplay
    area: int
    dock_size: int | None
    floating: WindowPlacement | None

    @classmethod
    def read(cls, value: object) -> "WorkspaceSettings | None":
        if not isinstance(value, dict) or value.get("version") != 1:
            return None
        window = WindowPlacement.read(value.get("window"))
        maximized, display = value.get("maximized"), value.get("display")
        area, size = value.get("area"), value.get("dock_size")
        if window is None or type(maximized) is not bool:
            return None
        return cls(
            window,
            maximized,
            cast(CommandDisplay, display)
            if display in ("hidden", "collapsed", "expanded")
            else "collapsed",
            area if type(area) is int and area in (1, 2, 4, 8) else 8,
            size if type(size) is int and 0 < size <= 100_000 else None,
            WindowPlacement.read(value.get("floating")),
        )

    def settings(self) -> dict[str, object]:
        return {
            "version": 1,
            "window": self.window.settings(),
            "maximized": self.maximized,
            "display": self.display,
            "area": self.area,
            "dock_size": self.dock_size,
            "floating": self.floating.settings() if self.floating is not None else None,
        }


def recent_projects(value: object) -> tuple[Path, ...]:
    if not isinstance(value, (tuple, list)):
        return ()
    projects: dict[str, Path] = {}
    for item in value:
        if isinstance(item, str) and item and "\0" not in item:
            path = Path(item)
            if path.is_absolute() and path.suffix.casefold() == ".astromosaic":
                path = Path(os.path.abspath(path))
                projects.setdefault(os.path.normcase(str(path)), path)
            if len(projects) == RECENT_LIMIT:
                break
    return tuple(projects.values())
