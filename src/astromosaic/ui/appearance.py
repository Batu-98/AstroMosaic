"""Shared desktop palette and per-user appearance preference."""

from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtGui import QActionGroup, QColor, QFontDatabase, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QApplication, QMenu, QSplitter, QSplitterHandle

_STYLE = """
    QWidget { font-size: BODY_SIZE; }
    QLabel[sectionTitle="true"] { font-size: HEADING_SIZE; font-weight: 600; }
    QPushButton, QToolButton, QComboBox { padding: 4px 10px; border: 1px solid palette(mid);
        border-radius: 4px; background: palette(button); color: palette(button-text); }
    QComboBox { padding-right: 18px; }
    QToolButton { padding-right: 15px; }
    QPushButton:hover, QToolButton:hover, QComboBox:hover { border-color: palette(window-text); }
    QPushButton:focus, QToolButton:focus, QComboBox:focus { border-color: palette(link); }
    QPushButton:pressed, QToolButton:pressed { background: palette(mid); }
    QPushButton[primary="true"]:enabled {
        background: PRIMARY_FILL; color: PRIMARY_TEXT;
        border: 1px solid PRIMARY_FILL;
    }
    QPushButton[primary="true"]:focus { border-color: palette(text); }
    QPushButton:disabled, QToolButton:disabled, QComboBox:disabled {
        background: palette(window); color: DISABLED_TEXT; border: 1px dashed DISABLED_TEXT;
    }
    QTableView { border: 1px solid palette(mid); gridline-color: palette(mid); }
    QTableView::item { padding: 0 5px; }
    QHeaderView::section { background: palette(button); color: palette(button-text);
        padding: 2px 6px; border: 0; border-right: 1px solid palette(mid);
        border-bottom: 1px solid palette(mid); }
    QSplitter::handle { background: palette(mid); }
    QFrame#mosaicPreviewSurface { border: 2px solid palette(mid); }
    QFrame#mosaicPreviewSurface:focus { border-color: palette(link); }
    QProgressBar#workspaceProgress {
        background: palette(base); border: 1px solid palette(mid); border-radius: 5px;
    }
    QProgressBar#workspaceProgress::chunk { background: PRIMARY_FILL; border-radius: 4px; }
    QLabel#jobPercentage { font-size: HEADING_SIZE; font-weight: 700; min-width: 54px; }
"""


class _WorkspaceSplitterHandle(QSplitterHandle):
    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        center = self.rect().center()
        grip = self.palette().color(QPalette.ColorRole.Accent)
        for offset in (-9, 0, 9):
            if self.orientation() == Qt.Orientation.Horizontal:
                painter.fillRect(center.x() - 1, center.y() + offset - 2, 3, 5, grip)
            else:
                painter.fillRect(center.x() + offset - 2, center.y() - 1, 5, 3, grip)
        painter.end()


class WorkspaceSplitter(QSplitter):
    def __init__(self) -> None:
        super().__init__(Qt.Orientation.Vertical)
        self.setHandleWidth(5)
        self._pane_sizes = {
            Qt.Orientation.Vertical: [235, 380],
            Qt.Orientation.Horizontal: [990, 890],
        }
        self.splitterMoved.connect(self._remember_sizes)

    def _remember_sizes(self, position: int, index: int) -> None:
        self._pane_sizes[self.orientation()] = self.sizes()

    def event(self, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest) and self.count() == 2:
            panels, preview = self.widget(0), self.widget(1)
            assert panels is not None and preview is not None
            required = panels.minimumSizeHint().width() + preview.minimumSizeHint().width()
            wide = self.width() >= max(1200, required + self.handleWidth())
            orientation = Qt.Orientation.Horizontal if wide else Qt.Orientation.Vertical
            if orientation != self.orientation():
                self.setOrientation(orientation)
                self.setSizes(self._pane_sizes[orientation])
        return super().event(event)

    def createHandle(self) -> QSplitterHandle:
        return _WorkspaceSplitterHandle(self.orientation(), self)


def apply_theme(name: str) -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    dark = name == "Dark"
    # Clear the stylesheet's widget palettes before resolving its palette() colors again.
    app.setStyleSheet("")
    if app.style().name().lower() != "fusion":
        app.setStyle("Fusion")
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light)
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    if font.pointSizeF() > 0:
        font.setPointSizeF(max(12.0, font.pointSizeF()))
        body_size = f"{font.pointSizeF():g}pt"
        heading_size = f"{font.pointSizeF() * 1.125:g}pt"
    else:
        font.setPixelSize(max(16, font.pixelSize()))
        body_size = f"{font.pixelSize()}px"
        heading_size = f"{round(font.pixelSize() * 1.125)}px"
    app.setFont(font)
    palette = QPalette()
    role = QPalette.ColorRole
    colors = {
        role.Window: ("#202429", "#f2f4f5"),
        role.WindowText: ("#edf0f2", "#20262b"),
        role.Base: ("#181c20", "#ffffff"),
        role.AlternateBase: ("#21262b", "#f3f6f7"),
        role.Text: ("#edf0f2", "#20262b"),
        role.Button: ("#30363c", "#e6eaec"),
        role.ButtonText: ("#edf0f2", "#20262b"),
        role.Mid: ("#42494f", "#c7cdd1"),
        role.Light: ("#50575d", "#ffffff"),
        role.Midlight: ("#43494f", "#f6f7f8"),
        role.Dark: ("#15181b", "#a0a7ac"),
        role.Shadow: ("#101215", "#859096"),
        role.Highlight: ("#325952", "#cbe7e0"),
        role.HighlightedText: ("#f1fffc", "#133a34"),
        role.Accent: ("#76c9bf", "#17695f"),
        role.Link: ("#88d5cb", "#14665e"),
        role.ToolTipBase: ("#30363c", "#ffffff"),
        role.ToolTipText: ("#edf0f2", "#20262b"),
        role.PlaceholderText: ("#a0a9af", "#616a70"),
    }
    for key, (night, day) in colors.items():
        palette.setColor(key, QColor(night if dark else day))
    for key in (role.Text, role.WindowText, role.ButtonText):
        palette.setColor(
            QPalette.ColorGroup.Disabled, key, QColor("#89939a" if dark else "#59636a")
        )
    app.setPalette(palette)
    app.setStyleSheet(
        _STYLE.replace("PRIMARY_FILL", palette.color(role.Accent).name())
        .replace("PRIMARY_TEXT", "#102321" if dark else "#ffffff")
        .replace("DISABLED_TEXT", palette.color(QPalette.ColorGroup.Disabled, role.ButtonText).name())
        .replace("BODY_SIZE", body_size)
        .replace("HEADING_SIZE", heading_size)
    )


def add_theme_menu(view: QMenu, settings: QSettings) -> None:
    name = settings.value("appearance/theme", "Dark")
    if name not in ("Dark", "Light"):
        name = "Dark"
    apply_theme(name)
    menu = view.addMenu("Theme")
    group = QActionGroup(menu)
    for option in ("Dark", "Light"):
        action = menu.addAction(option)
        group.addAction(action)
        action.setCheckable(True)
        action.setChecked(option == name)

    def select(option: str) -> None:
        apply_theme(option)
        settings.setValue("appearance/theme", option)

    group.triggered.connect(lambda action: select(action.text()))
