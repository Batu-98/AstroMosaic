"""Desktop project and background render workflow."""

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

from astromosaic.astrometry.hints import PanelOptics
from astromosaic.display import DisplayFrame, highlight_overlap
from astromosaic.storage.project import (
    FileReference,
    Layer,
    MosaicProject,
    PanelInspection,
    ProjectPanel,
    load_project,
    save_project,
)
from astromosaic.ui.mask_editor import MaskEditor
from astromosaic.ui.mosaic_job import (
    CompositionProposalJob,
    ForegroundAlignmentJob,
    ForegroundJob,
    MaskEditorJob,
    MosaicJob,
    PanelInspectionJob,
    PreviewJob,
)
from astromosaic.ui.project_settings import (
    PANEL_FILES,
    CompositionSettings,
    PanelSettings,
    ProjectSettings,
)
from astromosaic.ui.sky_viewport import SkyViewport

_PROJECT_FILTER = "AstroMosaic project (*.astromosaic)"
_TIFF_FILTER = "TIFF mosaic (*.tiff *.tif)"
_FITS_FILTER = "FITS mosaic (*.fits *.fit *.fts)"
_Button = QMessageBox.StandardButton
_Job = (
    MosaicJob
    | PreviewJob
    | ForegroundJob
    | MaskEditorJob
    | ForegroundAlignmentJob
    | CompositionProposalJob
)
_LAYERS: tuple[Layer, ...] = ("sky", "foreground", "composition")


class ProjectWindow(QMainWindow):
    def __init__(self, *, use_gpu: bool = True) -> None:
        super().__init__()
        self.project = MosaicProject()
        self._saved = self.project
        self.project_path: Path | None = None
        self.job: _Job | None = None
        self._inspection_job: PanelInspectionJob | None = None
        self._inspected_panels: tuple[ProjectPanel, ...] = ()
        self._inspections: tuple[PanelInspection, ...] = ()
        self._panel_dialog: tuple[int, PanelSettings] | None = None
        self._preview_project: MosaicProject | None = None
        self._display_frame: DisplayFrame | None = None
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
        panel_menu = self.menuBar().addMenu("&Panel")
        self.check_foreground = panel_menu.addAction("Check Foreground", self._check_foreground)
        self.propose_mask = panel_menu.addAction("Propose Sky Mask…", self._propose_mask)
        layers_menu = self.menuBar().addMenu("&Layers")
        self.align_action = layers_menu.addAction("Align Foreground", self._align_foreground)
        self.placement_action = layers_menu.addAction("Propose Placement", self._propose_placement)
        self.composition_action = layers_menu.addAction(
            "Composition Settings…", self._composition_settings
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
        self.mask_button = QPushButton("Edit Sky Mask…")
        self.mask_button.clicked.connect(self._edit_mask)
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self._remove)
        for button in (
            self.add_button,
            self.relink_button,
            self.panel_button,
            self.mask_button,
            self.remove_button,
        ):
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
        self.layer_box = QComboBox()
        self.layer_box.addItems(["Sky", "Foreground", "Composition"])
        self.layer_box.setAccessibleName("Mosaic layer")
        self.layer_box.setToolTip("Choose the layer to preview and export.")
        self.layer_box.currentIndexChanged.connect(self._layer_changed)
        self.overlap_check = QCheckBox("Highlight Overlap")
        self.overlap_check.toggled.connect(self._paint_display)
        actions.addWidget(self.settings_button)
        actions.addWidget(self.overlap_check)
        actions.addStretch()
        actions.addWidget(self.layer_box)
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
        for index, panel in enumerate(self.project.panels):
            statuses = [(role, reference.status()) for role, reference in panel.references()]
            attention = [f"{role} {value.lower()}" for role, value in statuses if value != "Ready"]
            linked &= not attention
            detail = ", ".join(attention) or "Linked"
            tag = {
                None: "Foreground unchecked",
                "mixed": "Foreground suggested",
                "uncertain": "Uncertain foreground",
                "sky-only": "No foreground detected",
            }[panel.foreground_tag]
            if panel.foreground_override is not None:
                tag = (
                    "Mixed (manual)"
                    if panel.foreground_override == "mixed"
                    else "Sky only (manual)"
                )
            elif panel.source_mask is not None:
                tag = "Mixed"
            mask = ""
            if panel.source_mask is not None or panel.sky_mask is not None:
                mask = "  ·  Sky mask saved"
            elif panel.foreground_tag in ("mixed", "uncertain"):
                mask = "  ·  Sky mask needed"
            sky = "  ·  Sky skipped" if not panel.include_sky else ""
            info = self._panel_inspection(index)
            wcs = info.wcs_status if info is not None else "Checking…"
            if statuses[0][1] != "Ready":
                wcs = "Unavailable"
            elif any(role == "WCS sidecar" and value != "Ready" for role, value in statuses):
                wcs = "Invalid"
            item = QListWidgetItem(
                f"{panel.source.path.name}  ·  WCS {wcs}  ·  Weight {panel.weight:g}"
                f"  ·  {detail}  ·  {tag}{mask}{sky}"
            )
            tooltip = [f"{role}: {reference.path}" for role, reference in panel.references()]
            if info is not None:
                tooltip.append(info.detail)
            item.setToolTip("\n".join(tooltip))
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
        self._layer_controls()
        self.cancel_button.setEnabled(self.job is not None)
        self._start_panel_inspection()

    def _panel_inspection(self, index: int) -> PanelInspection | None:
        if self._inspected_panels is self.project.panels and 0 <= index < len(self._inspections):
            return self._inspections[index]
        return None

    def _start_panel_inspection(self) -> None:
        if self._inspection_job is not None:
            if self._inspection_job.project.panels is not self.project.panels:
                self._inspection_job.cancel()
            return
        if (
            not self._close_after_job
            and self.project.panels
            and self.project.panels is not self._inspected_panels
        ):
            job = PanelInspectionJob(self.project, self)
            self._inspection_job = job
            job.finished.connect(self._finish_panel_inspection)
            job.start()

    @Slot()
    def _finish_panel_inspection(self) -> None:
        job, self._inspection_job = self._inspection_job, None
        assert job is not None
        if job.project.panels is self.project.panels and not job.cancelled:
            self._inspected_panels = job.project.panels
            self._inspections = job.result or (
                PanelInspection("Unavailable", job.error or "Panel metadata could not be read."),
            ) * len(job.project.panels)
            if self._panel_dialog is not None:
                index, dialog = self._panel_dialog
                dialog.show_embedded_optics(self._inspections[index].embedded_optics)
        job.deleteLater()
        if self._close_after_job:
            if self.job is None:
                self._close_after_job = False
                QTimer.singleShot(0, self.close)
            return
        self._refresh(self.panels.currentRow())

    def _layer(self) -> Layer:
        return _LAYERS[self.layer_box.currentIndex()]

    def _layer_controls(self) -> None:
        idle = self.job is None
        layer = self._layer()
        ground = self.project.current_foreground()
        sky = bool(self.project.sky_indices())
        self.align_action.setEnabled(idle and bool(self.project.foreground_inputs()))
        self.placement_action.setEnabled(idle and ground is not None and sky)
        self.composition_action.setEnabled(idle and ground is not None and sky)
        self.layer_box.setEnabled(idle and bool(self.project.panels))
        self.overlap_check.setVisible(layer == "composition")
        self.overlap_check.setEnabled(
            self._display_frame is not None and self._display_frame.common_coverage is not None
        )
        spec = self.project.render
        region = spec.output_region()
        ra, dec = spec.center
        ready = False
        if layer == "sky":
            summary = (
                f"ICRS TAN  ·  RA {ra:.7g}°, Dec {dec:.7g}°"
                f"  ·  {region.width} × {region.height} px  ·  {spec.scale_arcsec:g} arcsec/px"
            )
            ready = sky
        elif ground is None:
            summary = "Apply editable foreground masks and choose Layers → Align Foreground."
        elif layer == "foreground":
            summary = f"Foreground  ·  {ground.canvas.width} × {ground.canvas.height} px"
            ready = True
        elif self.project.composition is None or not sky:
            summary = "Include sky panels and set placement from the Layers menu."
        else:
            composition = self.project.composition
            try:
                canvas, seam = composition.frame(
                    (region.width, region.height), (ground.canvas.width, ground.canvas.height)
                )
            except ValueError as error:
                summary = str(error)
            else:
                summary = f"Composition  ·  {canvas.width} × {canvas.height} px  ·  Seam width {seam:.2f} px"
                ready = True
        self.grid_summary.setText(summary)
        self.start_button.setEnabled(idle and ready)
        self.preview_button.setEnabled(idle and ready)

    @Slot()
    def _layer_changed(self) -> None:
        self._clear_preview()
        self._layer_controls()
        self.progress.setValue(0)
        self.status.setText("")

    def _selection_changed(self) -> None:
        index = self.panels.currentRow()
        selected = index >= 0 and self.job is None
        for button in (self.relink_button, self.panel_button, self.mask_button, self.remove_button):
            button.setEnabled(selected)
        self.check_foreground.setEnabled(selected)
        self.propose_mask.setEnabled(
            selected and self.project.panels[index].foreground_tag in ("mixed", "uncertain")
        )

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
            if additions:
                indices = tuple(range(start, len(self.project.panels)))
                self._launch_job(ForegroundJob(self.project, indices, self), "Checking foreground…")
            else:
                self.status.setText("Panels already added.")
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
        info = self._panel_inspection(index)
        dialog.show_embedded_optics(info.embedded_optics if info is not None else PanelOptics())
        self._panel_dialog = (index, dialog)
        try:
            while dialog.exec():
                try:
                    panel = dialog.settings()
                except (OSError, ValueError) as error:
                    self._error("Invalid panel settings", error)
                    continue
                self._update_panel(index, panel)
                break
        finally:
            self._panel_dialog = None
            dialog.deleteLater()

    def _update_panel(self, index: int, panel: ProjectPanel) -> None:
        panels = self.project.panels
        self.project = replace(self.project, panels=panels[:index] + (panel,) + panels[index + 1 :])
        self._refresh(index)

    def _check_foreground(self) -> None:
        index = self.panels.currentRow()
        if index >= 0 and self.job is None:
            self._launch_job(ForegroundJob(self.project, (index,), self), "Checking foreground…")

    def _edit_mask(self) -> None:
        self._open_mask_editor(propose=False)

    def _propose_mask(self) -> None:
        self._open_mask_editor(propose=True)

    def _open_mask_editor(self, *, propose: bool) -> None:
        index = self.panels.currentRow()
        if index >= 0 and self.job is None:
            self._launch_job(
                MaskEditorJob(self.project, index, propose, self), "Preparing sky mask…"
            )

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
        self._launch_job(MosaicJob(self.project, path, self, self._layer()), "Preparing mosaic…")

    def _clear_preview(self) -> None:
        self._preview_project = None
        self._display_frame = None
        self.overlap_check.setEnabled(False)
        self.viewport.set_frame(None)

    def _preview(self) -> None:
        if self.job is not None or not self.project.panels:
            return
        self._clear_preview()
        self._preview_project = self.project
        layer = self._layer()
        job = PreviewJob(self.project, self, layer)
        job.proxy_ready.connect(self._show_proxy)
        self._launch_job(job, f"Preparing {layer} preview…")

    @Slot(object)
    def _show_proxy(self, frame: DisplayFrame) -> None:
        if self.sender() is self.job and self.cancel_button.isEnabled():
            self._set_display_frame(frame)

    def _set_display_frame(self, frame: DisplayFrame) -> None:
        self._display_frame = frame
        self.overlap_check.setEnabled(frame.common_coverage is not None)
        self._paint_display()

    @Slot()
    def _paint_display(self) -> None:
        frame = self._display_frame
        if frame is not None:
            self.viewport.set_frame(
                highlight_overlap(frame) if self.overlap_check.isChecked() else frame
            )

    def _align_foreground(self) -> None:
        if self.job is None:
            self._launch_job(
                ForegroundAlignmentJob(self.project, self), "Preparing foreground alignment…"
            )

    def _propose_placement(self) -> None:
        if self.job is None:
            self._launch_job(
                CompositionProposalJob(self.project, self), "Finding a shared horizon…"
            )

    def _composition_settings(self) -> None:
        dialog = CompositionSettings(self.project, self)
        try:
            while dialog.exec():
                try:
                    composition = dialog.settings()
                except (ValueError, OverflowError) as error:
                    self._error("Invalid composition settings", error)
                    continue
                self.project = replace(self.project, composition=composition)
                self._refresh(self.panels.currentRow())
                self.layer_box.setCurrentIndex(_LAYERS.index("composition"))
                self.status.setText("Composition settings applied.")
                break
        finally:
            dialog.deleteLater()

    def _launch_job(self, job: _Job, message: str) -> None:
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
        self._layer_controls()
        self.cancel_button.setEnabled(running)
        self._selection_changed()

    @Slot(object, object)
    def _progress(self, done: int, total: int) -> None:
        self.progress.setValue((100 * done) // total)
        job = self.job
        if job is not None and self.cancel_button.isEnabled():
            self.status.setText(f"{job.progress_label} {done:,} / {total:,} {job.progress_units}.")

    @Slot()
    def _finished(self) -> None:
        job, self.job = self.job, None
        assert job is not None
        self._set_running(False)
        if isinstance(job, PreviewJob):
            self._finish_preview(job)
        elif isinstance(job, ForegroundJob):
            self._finish_foreground_check(job)
        elif isinstance(job, MaskEditorJob):
            self._finish_mask_editor(job)
        elif isinstance(job, (ForegroundAlignmentJob, CompositionProposalJob)):
            self._finish_layer_job(job)
        elif job.result is not None:
            self.progress.setValue(100)
            text = f"Saved {job.destination.name} · {job.result.covered_pixels:,} covered pixels."
            if job.result.common_pixels is not None:
                text += f" Both layers cover {job.result.common_pixels:,} pixels."
            self.status.setText(text)
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
            self._set_display_frame(job.result)
            self.progress.setValue(100)
            width, height = job.result.size
            text = (
                f"{job.layer.capitalize()} preview · {width} × {height} samples."
                if job.result.has_coverage
                else "No coverage at this preview resolution."
            )
            if job.result.common_coverage is not None:
                text += (
                    f" Both layers cover {int(job.result.common_coverage.sum()):,} preview samples."
                )
            self.status.setText(text)
        else:
            self._clear_preview()
            self.progress.setValue(0)
            if job.cancelled:
                self.status.setText("Preview cancelled.")
            else:
                self.status.setText(f"Preview failed. {job.error or 'No result was returned.'}")
                self._refresh(self.panels.currentRow())

    def _finish_layer_job(self, job: ForegroundAlignmentJob | CompositionProposalJob) -> None:
        if job.result is None:
            self.progress.setValue(0)
            label = job.label.capitalize()
            self.status.setText(
                f"{label} cancelled."
                if job.cancelled
                else f"{label} failed. {job.error or 'No result was returned.'}"
            )
            return
        if isinstance(job, ForegroundAlignmentJob):
            self.project = job.result
            assert self.project.foreground is not None
            alignment = self.project.foreground.alignment
            layer = "foreground"
            message = f"Aligned {len(alignment.panels)} foreground panel(s) across {len(alignment.overlaps)} overlap(s)."
        else:
            placement = job.result
            self.project = replace(self.project, composition=placement)
            assert placement.reference_panel is not None and placement.placement_rms_px is not None
            layer = "composition"
            message = f"Placement from panel {placement.reference_panel + 1} · {placement.placement_rms_px:.2f} px RMS."
        self._refresh(self.panels.currentRow())
        self.layer_box.setCurrentIndex(_LAYERS.index(layer))
        self.progress.setValue(100)
        self.status.setText(message)

    def _finish_foreground_check(self, job: ForegroundJob) -> None:
        if job.result is None:
            self._mask_job_status(job)
            return
        self.project, problems = job.result
        self._refresh(self.panels.currentRow())
        self.progress.setValue(100)
        if problems:
            self.status.setText(
                f"Foreground check failed for {len(problems)} panel(s). {problems[0]}"
            )
        else:
            self.status.setText(f"Checked {len(job.indices)} panel(s) for foreground.")

    def _finish_mask_editor(self, job: MaskEditorJob) -> None:
        if job.result is None:
            self._mask_job_status(job)
            return
        if self._close_after_job:
            return
        self.progress.setValue(100)
        panel = self.project.panels[job.index]
        self.status.setText(f"Edit the sky mask for {panel.source.path.name}.")
        dialog = MaskEditor(
            panel.source.path.name,
            job.result,
            proposed=job.propose,
            attached=panel.sky_mask is not None,
            parent=self,
        )
        try:
            accepted = dialog.exec()
            mask = dialog.result_mask
        finally:
            dialog.deleteLater()
        if not accepted:
            self.status.setText("Sky mask editing cancelled.")
            return
        if (panel.sky_mask is not None and mask is not None and mask == job.result.saved) or (
            panel.sky_mask is None and mask == panel.source_mask
        ):
            self.status.setText("Sky mask kept.")
            return
        self._update_panel(job.index, replace(panel, source_mask=mask, sky_mask=None))
        message = "Sky mask applied." if mask is not None else "Sky mask removed."
        previous = panel.source_mask.sky_fingerprint if panel.source_mask is not None else None
        current = mask.sky_fingerprint if mask is not None else None
        if panel.wcs_sidecar is not None and (panel.sky_mask is not None or previous != current):
            message += " Recompute or clear the WCS sidecar for the new mask revision."
        self.status.setText(message)

    def _mask_job_status(self, job: ForegroundJob | MaskEditorJob) -> None:
        self.progress.setValue(0)
        name = job.label.capitalize()
        self.status.setText(
            f"{name} cancelled."
            if job.cancelled
            else f"{name} failed. {job.error or 'No result was returned.'}"
        )

    def _cancel(self) -> None:
        if self.job is not None:
            self.job.cancel()
            self.cancel_button.setEnabled(False)
            self.status.setText(f"Cancelling {self.job.label}…")

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
        elif self._inspection_job is not None:
            self._close_after_job = True
            self._inspection_job.cancel()
            event.ignore()
        elif self._confirm_discard():
            event.accept()
        else:
            event.ignore()
            self._start_panel_inspection()
