"""Desktop project and background render workflow."""

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from astromosaic.display import DisplayFrame
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    load_project,
    save_project,
)
from astromosaic.ui.mosaic_job import MosaicJob, PreviewJob
from astromosaic.ui.project_settings import PANEL_FILES, PanelSettings, ProjectSettings
from astromosaic.ui.sky_viewport import SkyViewport

_PROJECT_FILTER = "AstroMosaic project (*.astromosaic)"
_TIFF_FILTER = "TIFF mosaic (*.tiff *.tif)"
_FITS_FILTER = "FITS mosaic (*.fits *.fit *.fts)"
_Button = QMessageBox.StandardButton


class ProjectWindow(QMainWindow):
    def __init__(self, *, use_gpu: bool = True) -> None:
        super().__init__()
        self.project = MosaicProject()
        self._saved = self.project
        self.project_path: Path | None = None
        self.job: MosaicJob | PreviewJob | None = None
        self._preview_project: MosaicProject | None = None
        self._close_after_job = False
        self.setWindowTitle("AstroMosaic")
        self.resize(1040, 780)
        self.setMinimumWidth(630)

        file_menu = self.menuBar().addMenu("&File")
        self._file_actions = (
            file_menu.addAction("&New Project", "Ctrl+N", self._new),
            file_menu.addAction("&Open Project…", "Ctrl+O", self._open),
            file_menu.addAction("&Save Project", "Ctrl+S", self._save),
            file_menu.addAction("Save Project &As…", "Ctrl+Shift+S", self._save_as),
        )

        body = QWidget(self)
        self.setCentralWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        self.viewport = SkyViewport(use_gpu=use_gpu)
        splitter.addWidget(self.viewport)
        self._editor = QWidget(body)
        controls = QVBoxLayout(self._editor)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(QLabel("Panels"))
        self.panels = QListWidget()
        self.panels.setAccessibleName("Project panels")
        controls.addWidget(self.panels, 1)
        buttons = QHBoxLayout()
        self.add_button = QPushButton("Add Panels…")
        self.add_button.clicked.connect(self._add)
        self.relink_button = QPushButton("Relink…")
        self.relink_button.clicked.connect(self._relink)
        self.panel_button = QPushButton("Panel Settings…")
        self.panel_button.clicked.connect(self._panel_settings)
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self._remove)
        for button in (self.add_button, self.relink_button, self.panel_button, self.remove_button):
            buttons.addWidget(button)
        buttons.addStretch()
        controls.addLayout(buttons)
        self.panels.currentRowChanged.connect(self._selection_changed)
        splitter.addWidget(self._editor)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([500, 150])
        layout.addWidget(splitter, 1)

        self.grid_summary = QLabel()
        self.grid_summary.setWordWrap(True)
        layout.addWidget(self.grid_summary)
        actions = QHBoxLayout()
        self.settings_button = QPushButton("Mosaic Settings…")
        self.settings_button.clicked.connect(self._settings)
        self.preview_button = QPushButton("Build Preview")
        self.preview_button.clicked.connect(self._preview)
        self.start_button = QPushButton("Export Mosaic…")
        self.start_button.clicked.connect(self._start)
        self.cancel_button = QPushButton("Cancel Job")
        self.cancel_button.clicked.connect(self._cancel)
        actions.addWidget(self.settings_button)
        actions.addStretch()
        actions.addWidget(self.preview_button)
        actions.addWidget(self.start_button)
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status = QLabel("Add linear FITS or TIFF panels to begin.")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(36)
        layout.addWidget(self.status)
        self._refresh()

    def _refresh(self, selected: int = -1) -> None:
        self.panels.clear()
        linked = True
        for panel in self.project.panels:
            statuses = [(role, reference.status()) for role, reference in panel.references()]
            attention = [f"{role} {value.lower()}" for role, value in statuses if value != "Ready"]
            linked &= not attention
            detail = ", ".join(attention) or "Linked"
            item = QListWidgetItem(
                f"{panel.source.path.name}  ·  Weight {panel.weight:g}  ·  {detail}"
            )
            item.setToolTip(
                "\n".join(f"{role}: {reference.path}" for role, reference in panel.references())
            )
            self.panels.addItem(item)
        if self.project.panels:
            self.panels.setCurrentRow(max(0, min(selected, self.panels.count() - 1)))
        if self._preview_project is not None and (
            self._preview_project != self.project or not linked
        ):
            self._clear_preview()
        self._selection_changed()
        name = self.project_path.name if self.project_path else "Untitled"
        marker = "*" if self.project != self._saved else ""
        self.setWindowTitle(f"{name}{marker} — AstroMosaic")
        spec = self.project.render
        region = spec.output_region()
        ra, dec = spec.center
        self.grid_summary.setText(
            f"ICRS TAN  ·  RA {ra:.7g}°, Dec {dec:.7g}°"
            f"  ·  {region.width} × {region.height} px  ·  {spec.scale_arcsec:g} arcsec/px"
        )
        self.start_button.setEnabled(bool(self.project.panels) and self.job is None)
        self.preview_button.setEnabled(bool(self.project.panels) and self.job is None)
        self.cancel_button.setEnabled(self.job is not None)

    def _selection_changed(self) -> None:
        selected = self.panels.currentRow() >= 0
        for button in (self.relink_button, self.panel_button, self.remove_button):
            button.setEnabled(selected)

    def _confirm_discard(self) -> bool:
        if self.project == self._saved:
            return True
        response = QMessageBox.question(
            self,
            "Unsaved project",
            "Save changes to this project?",
            _Button.Save | _Button.Discard | _Button.Cancel,
            _Button.Save,
        )
        return response == _Button.Discard or (response == _Button.Save and self._save())

    def _set_project(self, project: MosaicProject, path: Path | None) -> None:
        self._clear_preview()
        self.project = self._saved = project
        self.project_path = path
        self.progress.setValue(0)
        self._refresh()

    def _new(self) -> None:
        if self._confirm_discard():
            self._set_project(MosaicProject(), None)
            self.status.setText("New project.")

    def _open(self) -> None:
        if not self._confirm_discard():
            return
        name, _ = QFileDialog.getOpenFileName(self, "Open Project", "", _PROJECT_FILTER)
        if not name:
            return
        try:
            path = Path(name)
            self._set_project(load_project(path), path)
            self.status.setText(f"Opened {path.name}.")
        except (OSError, ValueError) as error:
            self._error("Open failed", error)

    def _save(self) -> bool:
        if self.project_path is None:
            return self._save_as()
        return self._write(self.project_path, replace_existing=True)

    def _save_as(self) -> bool:
        name, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            str(self.project_path or ""),
            _PROJECT_FILTER,
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not name:
            return False
        path = Path(name)
        if not path.suffix:
            path = path.with_suffix(".astromosaic")
        existing = path.exists() or path.is_symlink()
        if (
            existing
            and QMessageBox.question(
                self,
                "Replace project?",
                f"Replace {path.name}?",
                _Button.Yes | _Button.No,
                _Button.No,
            )
            != _Button.Yes
        ):
            return False
        return self._write(path, replace_existing=existing)

    def _write(self, path: Path, *, replace_existing: bool) -> bool:
        try:
            save_project(path, self.project, replace_existing=replace_existing)
        except (OSError, ValueError, OverflowError) as error:
            self._error("Save failed", error)
            return False
        self.project_path, self._saved = path, self.project
        self._refresh(self.panels.currentRow())
        self.status.setText(f"Saved {path.name}.")
        return True

    def _add(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(self, "Add Panels", "", PANEL_FILES)
        if not names:
            return
        try:
            sources = tuple(FileReference.capture(Path(name)) for name in names)
            known = {panel.source.path for panel in self.project.panels}
            additions = []
            for source in sources:
                if source.path not in known:
                    additions.append(ProjectPanel(source))
                    known.add(source.path)
            start = len(self.project.panels)
            self.project = replace(self.project, panels=self.project.panels + tuple(additions))
            self._refresh(start)
            self.status.setText(
                f"Added {len(additions)} panel(s)." if additions else "Panels already added."
            )
        except (OSError, ValueError) as error:
            self._error("Add failed", error)

    def _relink(self) -> None:
        index = self.panels.currentRow()
        panel = self.project.panels[index]
        name, _ = QFileDialog.getOpenFileName(
            self, "Relink Panel", panel.source.path.name, PANEL_FILES
        )
        if name:
            try:
                self.project = self.project.relink_panel(index, Path(name))
                self._refresh(index)
                self.status.setText(f"Relinked {Path(name).name}.")
            except (OSError, ValueError) as error:
                self._error("Relink failed", error)

    def _remove(self) -> None:
        index = self.panels.currentRow()
        panels = self.project.panels
        self.project = replace(self.project, panels=panels[:index] + panels[index + 1 :])
        self._refresh(index)

    def _panel_settings(self) -> None:
        index = self.panels.currentRow()
        panels = self.project.panels
        dialog = PanelSettings(panels[index], self)
        try:
            while dialog.exec():
                try:
                    panel = dialog.settings()
                except (OSError, ValueError) as error:
                    self._error("Invalid panel settings", error)
                    continue
                self.project = replace(
                    self.project, panels=panels[:index] + (panel,) + panels[index + 1 :]
                )
                self._refresh(index)
                break
        finally:
            dialog.deleteLater()

    def _settings(self) -> None:
        dialog = ProjectSettings(self.project, self)
        try:
            while dialog.exec():
                try:
                    self.project = dialog.settings()
                except (ValueError, OverflowError) as error:
                    self._error("Invalid mosaic settings", error)
                    continue
                self._refresh(self.panels.currentRow())
                break
        finally:
            dialog.deleteLater()

    def _start(self) -> None:
        if self.job is not None or not self.project.panels:
            return
        name, selected = QFileDialog.getSaveFileName(
            self,
            "Render Mosaic",
            "",
            f"{_TIFF_FILTER};;{_FITS_FILTER}",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not name:
            return
        path = Path(name)
        if not path.suffix:
            path = path.with_suffix(".fits" if selected == _FITS_FILTER else ".tiff")
        self._launch_job(MosaicJob(self.project, path, self), "Preparing mosaic…")

    def _clear_preview(self) -> None:
        self._preview_project = None
        self.viewport.set_frame(None)

    def _preview(self) -> None:
        if self.job is not None or not self.project.panels:
            return
        self._clear_preview()
        self._preview_project = self.project
        job = PreviewJob(self.project, self)
        job.proxy_ready.connect(self._show_proxy)
        self._launch_job(job, "Preparing sky preview…")

    @Slot(object)
    def _show_proxy(self, frame: DisplayFrame) -> None:
        if self.sender() is self.job and self.cancel_button.isEnabled():
            self.viewport.set_frame(frame)

    def _launch_job(self, job: MosaicJob | PreviewJob, message: str) -> None:
        self.job = job
        job.progress.connect(self._progress)
        job.finished.connect(self._finished)
        self._set_running(True)
        self.progress.setValue(0)
        self.status.setText(message)
        job.start()

    def _set_running(self, running: bool) -> None:
        for action in self._file_actions:
            action.setEnabled(not running)
        self._editor.setEnabled(not running)
        self.settings_button.setEnabled(not running)
        self.start_button.setEnabled(not running and bool(self.project.panels))
        self.preview_button.setEnabled(not running and bool(self.project.panels))
        self.cancel_button.setEnabled(running)

    @Slot(object, object)
    def _progress(self, done: int, total: int) -> None:
        self.progress.setValue((100 * done) // total)
        if self.cancel_button.isEnabled():
            action = "Previewing" if isinstance(self.job, PreviewJob) else "Rendering"
            self.status.setText(f"{action} {done:,} / {total:,} pixels.")

    @Slot()
    def _finished(self) -> None:
        job, self.job = self.job, None
        assert job is not None
        self._set_running(False)
        if isinstance(job, PreviewJob):
            self._finish_preview(job)
        elif job.result is not None:
            self.progress.setValue(100)
            self.status.setText(
                f"Saved {job.destination.name} · {job.result.covered_pixels:,} covered pixels."
            )
        elif job.cancelled:
            self.progress.setValue(0)
            self.status.setText("Mosaic cancelled.")
        else:
            self.progress.setValue(0)
            self.status.setText(f"Mosaic failed. {job.error or 'No result was returned.'}")
            self._refresh(self.panels.currentRow())
        job.deleteLater()
        if self._close_after_job:
            self._close_after_job = False
            QTimer.singleShot(0, self.close)

    def _finish_preview(self, job: PreviewJob) -> None:
        if job.result is not None:
            self.viewport.set_frame(job.result)
            self.progress.setValue(100)
            width, height = job.result.size
            self.status.setText(
                f"Sky preview · {width} × {height} samples."
                if job.result.has_coverage
                else "No sky coverage at this preview resolution."
            )
        else:
            self._clear_preview()
            self.progress.setValue(0)
            if job.cancelled:
                self.status.setText("Preview cancelled.")
            else:
                self.status.setText(f"Preview failed. {job.error or 'No result was returned.'}")
                self._refresh(self.panels.currentRow())

    def _cancel(self) -> None:
        if self.job is not None:
            self.job.cancel()
            self.cancel_button.setEnabled(False)
            action = "preview" if isinstance(self.job, PreviewJob) else "mosaic"
            self.status.setText(f"Cancelling {action}…")

    def _error(self, title: str, error: Exception) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(str(error))
        box.exec()
        box.deleteLater()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.job is not None:
            self._close_after_job = True
            self._cancel()
            event.ignore()
        elif self._confirm_discard():
            event.accept()
        else:
            event.ignore()
