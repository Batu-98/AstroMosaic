"""Desktop controls for the AstroMosaic command line."""

from multiprocessing import get_context
from multiprocessing.connection import wait
from pathlib import Path
from shlex import shlex

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFontDatabase, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from astromosaic.cli.worker import run_command
from astromosaic.core.job import JobContext
from astromosaic.ui.mosaic_job import BackgroundJob

_HISTORY_LIMIT = 100
_LAUNCHERS = {"astromosaic", "astromosaic.exe", "astromosaic-cli", "astromosaic-cli.exe"}


class CommandJob(BackgroundJob[int]):
    output = Signal(str)

    def __init__(self, argv: list[str], directory: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self.argv = argv
        self.directory = directory

    def perform(self, context: JobContext) -> int:
        spawn = get_context("spawn")
        cancelled = spawn.Event()
        reader, writer = spawn.Pipe(duplex=False)
        child = spawn.Process(
            target=run_command, args=(self.argv, self.directory, writer, cancelled)
        )
        with reader, writer:
            try:
                child.start()
                writer.close()
                try:
                    while True:
                        if context.is_cancelled is not None and context.is_cancelled():
                            cancelled.set()
                        if wait([reader], timeout=0.05):
                            try:
                                message = reader.recv()
                            except (EOFError, BrokenPipeError):
                                break
                            if isinstance(message, str):
                                self.output.emit(message)
                            else:
                                self._progress(*message)
                        elif child.exitcode is not None:
                            break
                finally:
                    # Closing the reader also unblocks a writer after a transport failure.
                    reader.close()
                    cancelled.set()
                    child.join()
                assert child.exitcode is not None
                return child.exitcode
            finally:
                child.close()


class CommandPanel(QWidget):
    running_changed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._startup_directory = Path.cwd()
        self._directory = self._startup_directory
        self._job: CommandJob | None = None
        self._available = True
        self._history: list[str] = []
        self._history_index = 0
        self._draft = ""

        layout = QVBoxLayout(self)
        self.directory_label = QLabel()
        self.directory_label.setTextFormat(Qt.TextFormat.PlainText)
        self.directory_label.setWordWrap(True)
        self.directory_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.directory_label)
        self.set_project_path(None)

        self.output = QPlainTextEdit()
        self.output.setAccessibleName("Command output")
        self.output.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(2_000)
        self.output.setMinimumHeight(100)
        layout.addWidget(self.output, 1)

        controls = QHBoxLayout()
        self.entry = QLineEdit()
        self.entry.setAccessibleName("AstroMosaic command")
        self.entry.setPlaceholderText("--help")
        self.entry.setToolTip("Use Up and Down to recall commands from this session.")
        self.entry.returnPressed.connect(self._run)
        for key, recall in ((Qt.Key.Key_Up, self._previous), (Qt.Key.Key_Down, self._next)):
            shortcut = QShortcut(QKeySequence(key), self.entry)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(recall)
        controls.addWidget(self.entry, 1)
        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self._run)
        controls.addWidget(self.run_button)
        self.cancel_button = QPushButton("Cancel Command")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.setEnabled(False)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)

        feedback = QHBoxLayout()
        self.status = QLabel("Ready.")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        feedback.addWidget(self.status, 1)
        self.progress = QProgressBar()
        self.progress.setAccessibleName("Command progress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        feedback.addWidget(self.progress)
        layout.addLayout(feedback)

    @property
    def is_running(self) -> bool:
        return self._job is not None

    def set_project_path(self, path: Path | None) -> None:
        self._directory = path.absolute().parent if path is not None else self._startup_directory
        self.directory_label.setText(f"Working folder: {self._directory}")

    def set_available(self, available: bool) -> None:
        self._available = available
        self._update_input()

    @Slot(str)
    def append_summary(self, message: str) -> None:
        prefix = "\n" if self.output.document().lastBlock().text() else ""
        self._append(f"{prefix}{message}\n")

    def _update_input(self) -> None:
        enabled = self._available and not self.is_running
        self.entry.setEnabled(enabled)
        self.run_button.setEnabled(enabled)

    @Slot()
    def _previous(self) -> None:
        if not self._history or self._history_index == 0:
            return
        if self._history_index == len(self._history):
            self._draft = self.entry.text()
        self._history_index -= 1
        self.entry.setText(self._history[self._history_index])

    @Slot()
    def _next(self) -> None:
        if self._history_index == len(self._history):
            return
        self._history_index += 1
        if self._history_index == len(self._history):
            self.entry.setText(self._draft)
        else:
            self.entry.setText(self._history[self._history_index])

    @Slot()
    def _run(self) -> None:
        command = self.entry.text().strip()
        if not command or self.is_running or not self._available:
            return
        if not self._history or self._history[-1] != command:
            self._history.append(command)
            if len(self._history) > _HISTORY_LIMIT:
                del self._history[0]
        self._history_index = len(self._history)
        self._append(f"> {command}\n")
        try:
            tokens = shlex(command, posix=True)
            tokens.whitespace_split = True
            tokens.commenters = tokens.escape = ""
            argv = list(tokens)
        except ValueError as error:
            self._append(f"{error}. Close the quoted argument and run again.\n")
            self.status.setText("Invalid command.")
            self.progress.setValue(0)
            self.entry.setFocus()
            return
        if argv and argv[0].lower() in _LAUNCHERS:
            argv = argv[1:]

        job = CommandJob(argv, self._directory, self)
        self._job = job
        job.output.connect(self._append)
        job.progress.connect(self._progress)
        job.finished.connect(self._finished)
        self.entry.clear()
        self._update_input()
        self.cancel_button.setEnabled(True)
        self.progress.setRange(0, 0)
        self.status.setText("Running command…")
        self.running_changed.emit()
        job.start()

    @Slot(str)
    def _append(self, text: str) -> None:
        scrollbar = self.output.verticalScrollBar()
        follow = scrollbar.value() == scrollbar.maximum()
        cursor = QTextCursor(self.output.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        if follow:
            scrollbar.setValue(scrollbar.maximum())

    @Slot(object, object)
    def _progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(100 * done // total)
        if self.cancel_button.isEnabled():
            self.status.setText(f"Rendering {done:,} / {total:,} pixels.")

    @Slot()
    def cancel(self) -> None:
        if self._job is not None and self.cancel_button.isEnabled():
            self._job.cancel()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling command…")

    @Slot()
    def _finished(self) -> None:
        job, self._job = self._job, None
        assert job is not None
        if job.result == 0:
            message = "Command completed."
        elif job.result == 130:
            message = "Command cancelled (exit code 130)."
        elif job.result is not None:
            message = f"Command failed (exit code {job.result})."
        else:
            message = f"Command failed. {job.error or 'No exit code was returned.'}"
        self.append_summary(message)
        self.status.setText(message)
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if job.result == 0 else 0)
        self.cancel_button.setEnabled(False)
        job.deleteLater()
        self._update_input()
        self.running_changed.emit()
        if self.isVisible() and self.isActiveWindow():
            self.entry.setFocus()
