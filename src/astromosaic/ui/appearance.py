"""Shared desktop palette and per-user appearance preference."""

from PySide6.QtCore import QEvent, QSettings, QSize, Qt
from PySide6.QtGui import QActionGroup, QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QBoxLayout, QHBoxLayout, QMenu, QWidget

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
    QLabel#pinnedPanelHeader { background: palette(button); color: palette(button-text);
        border-right: 1px solid palette(mid); border-bottom: 1px solid palette(mid); }
    QListWidget#workspaceNavigation { border: 1px solid palette(mid); border-radius: 4px; }
    QListWidget#workspaceNavigation:focus { border-color: palette(link); }
    QListWidget#workspaceNavigation::item { padding: 6px 7px; border-left: 3px solid transparent; }
    QListWidget#workspaceNavigation::item:selected {
        border-left: 3px solid palette(accent); background: palette(highlight);
        color: palette(highlighted-text);
    }
    QFrame#mosaicPreviewSurface { border: 2px solid palette(mid); }
    QFrame#mosaicPreviewSurface:focus { border-color: palette(link); }
    QProgressBar#workspaceProgress {
        background: palette(base); border: 1px solid palette(mid); border-radius: 5px;
    }
    QProgressBar#workspaceProgress::chunk { background: PRIMARY_FILL; border-radius: 4px; }
    QLabel#jobPercentage { font-size: HEADING_SIZE; font-weight: 700; min-width: 54px; }
"""


class ResponsiveRow(QWidget):
    def __init__(self, first: QWidget, actions: QHBoxLayout) -> None:
        super().__init__()
        self._first = first
        self._actions = actions
        self._layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._layout.addWidget(first)
        self._layout.addLayout(actions, 1)

    def minimumSizeHint(self) -> QSize:
        size = super().minimumSizeHint()
        size.setWidth(max(self._first.minimumSizeHint().width(), self._actions.minimumSize().width()))
        return size

    def event(self, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest):
            row_width = (
                self._first.minimumSizeHint().width()
                + self._actions.minimumSize().width()
                + self._layout.spacing()
            )
            direction = (
                QBoxLayout.Direction.TopToBottom
                if self.width() < row_width
                else QBoxLayout.Direction.LeftToRight
            )
            if direction != self._layout.direction():
                self._layout.setDirection(direction)
                self.updateGeometry()
        return super().event(event)


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
