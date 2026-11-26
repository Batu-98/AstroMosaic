"""History controls and shortcuts scoped to an editor dialog."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDialog, QHBoxLayout, QToolButton


def add_draft_history_controls(
    layout: QHBoxLayout,
    dialog: QDialog,
    undo: Callable[[], None],
    redo: Callable[[], None],
) -> tuple[QAction, QAction]:
    undo_action = QAction("Undo", dialog)
    redo_action = QAction("Redo", dialog)
    undo_action.setShortcut(QKeySequence("Ctrl+Z"))
    redo_action.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
    undo_action.setToolTip("Undo the last edit (Ctrl+Z).")
    redo_action.setToolTip("Redo the last undone edit (Ctrl+Y or Ctrl+Shift+Z).")
    for action, callback in ((undo_action, undo), (redo_action, redo)):
        action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        action.triggered.connect(callback)
        dialog.addAction(action)
        button = QToolButton(dialog)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.setDefaultAction(action)
        layout.addWidget(button)
    return undo_action, redo_action
