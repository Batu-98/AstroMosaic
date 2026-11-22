"""Desktop project and background render workflow."""

import json
import re
from argparse import Namespace
from dataclasses import asdict, dataclass, replace
from importlib.metadata import version
from pathlib import Path
from time import monotonic
from typing import cast

from PySide6.QtCore import QSettings, QSignalBlocker, QStandardPaths, Qt, QTimer, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from astromosaic.astrometry.hints import PanelOptics
from astromosaic.astrometry.solve import read_solution_diagnostics
from astromosaic.core import Region
from astromosaic.display import DisplayFrame, highlight_overlap
from astromosaic.pipeline.mosaic import MAX_DETAIL_PIXELS, RenderSpec, SkyCalibrationRequirement
from astromosaic.storage.project import (
    FileReference,
    Layer,
    MosaicProject,
    PanelInspection,
    PanelSolveOutcome,
    ProjectPanel,
    load_project,
    save_project,
)
from astromosaic.ui.appearance import add_theme_menu
from astromosaic.ui.command_panel import CommandPanel
from astromosaic.ui.foreground_details import ForegroundAlignmentDetails
from astromosaic.ui.mask_editor import MaskEditor
from astromosaic.ui.mosaic_job import (
    CompositionProposalJob,
    ForegroundAlignmentJob,
    ForegroundAlignmentReport,
    ForegroundJob,
    MaskEditorJob,
    MosaicJob,
    PanelInspectionJob,
    PlateSolveJob,
    PreviewDetailJob,
    PreviewJob,
)
from astromosaic.ui.panel_table import VIEWS, PanelTable, panel_row
from astromosaic.ui.plate_solve_details import PlateSolveDetails
from astromosaic.ui.plate_solve_settings import PlateSolveSettings, load_plate_solve_settings
from astromosaic.ui.project_settings import (
    PANEL_FILES,
    CompositionSettings,
    PanelSettings,
    ProjectSettings,
)
from astromosaic.ui.sky_viewport import SkyViewport
from astromosaic.ui.terrain_editor import TerrainPointEditor

_PROJECT_FILTER = "AstroMosaic project (*.astromosaic)"
_TIFF_FILTER = "TIFF mosaic (*.tiff *.tif)"
_FITS_FILTER = "FITS mosaic (*.fits *.fit *.fts)"
_XISF_FILTER = "XISF mosaic (*.xisf)"
_Button = QMessageBox.StandardButton
_Job = (
    MosaicJob
    | PreviewJob
    | ForegroundJob
    | MaskEditorJob
    | ForegroundAlignmentJob
    | CompositionProposalJob
    | PlateSolveJob
)
_LAYERS: tuple[Layer, ...] = ("sky", "foreground", "composition")
_CALIBRATION_GUIDANCE: dict[SkyCalibrationRequirement, str] = {
    "filter": "Select a Sky band when panels have different filter labels. "
    "Use Common filter in Mosaic Settings to assign unlabeled panels to a known band.",
    "brightness": "Use linear panels with compatible brightness units. For linear panels on a "
    "shared scale, select Declare a common surface-brightness scale in Mosaic Settings.",
}


@dataclass(slots=True)
class _CropDraft:
    grid: RenderSpec
    frame: DisplayFrame
    fitted_grid: RenderSpec | None
    rotation: float | None
    suggested: Region | None = None


class ProjectWindow(QMainWindow):
    def __init__(self, *, use_gpu: bool = True, preferences: QSettings | None = None) -> None:
        super().__init__()
        app_version = version("astromosaic")
        beta_label = " (Beta)" if re.match(r"(?:\d+!)?[\d.]+b\d+", app_version) else ""
        self._app_title = f"AstroMosaic {app_version}{beta_label}"
        self.project = MosaicProject(auto_frame_preview=True)
        self._saved = self.project
        self.project_path: Path | None = None
        self.job: _Job | None = None
        self._inspection_job: PanelInspectionJob | None = None
        self._inspected_panels: tuple[ProjectPanel, ...] = ()
        self._inspections: tuple[PanelInspection, ...] = ()
        self._solved_panels: tuple[ProjectPanel, ...] = ()
        self._solve_outcomes: dict[int, PanelSolveOutcome] = {}
        self._foreground_report: ForegroundAlignmentReport | None = None
        self._foreground_panels: tuple[ProjectPanel, ...] | None = None
        self._panel_dialog: tuple[int, PanelSettings] | None = None
        self._preview_project: MosaicProject | None = None
        self._preview_grid: RenderSpec | None = None
        self._display_frame: DisplayFrame | None = None
        self._suggested_rotation: float | None = None
        self._crop_draft: _CropDraft | None = None
        self._detail_job: PreviewDetailJob | None = None
        self._detail_base: DisplayFrame | None = None
        self._live_ready = False
        self._live_pending = False
        self._overview_edge = 0
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(350)
        self._preview_timer.timeout.connect(self._live_preview)
        self._detail_timer = QTimer(self)
        self._detail_timer.setSingleShot(True)
        self._detail_timer.setInterval(160)
        self._detail_timer.timeout.connect(self._request_detail)
        self._close_after_job = False
        self.resize(1140, 780)
        self.setMinimumWidth(630)

        file_menu = self.menuBar().addMenu("&File")
        self._file_actions = (
            file_menu.addAction("&New Project", "Ctrl+N", self._new),
            file_menu.addAction("&Open Project…", "Ctrl+O", self._open),
            file_menu.addAction("&Save Project", "Ctrl+S", self._save),
            file_menu.addAction("Save Project &As…", "Ctrl+Shift+S", self._save_as),
        )
        file_menu.addSeparator()
        self.scientific_export = file_menu.addAction(
            "Export Scientific Mosaic…", self._start_scientific
        )
        view_menu = self.menuBar().addMenu("&View")
        application_preferences = (
            preferences if preferences is not None else QSettings("AstroMosaic", "AstroMosaic")
        )
        self.live_preview_action = view_menu.addAction("Live Sky Preview")
        self.live_preview_action.setCheckable(True)
        self.live_preview_action.setChecked(bool(
            application_preferences.value("view/liveSkyPreview", True, type=bool)
        ))
        self.live_preview_action.toggled.connect(self._toggle_live_preview)
        self.live_preview_action.toggled.connect(
            lambda enabled: application_preferences.setValue("view/liveSkyPreview", enabled)
        )
        add_theme_menu(view_menu, application_preferences)
        panel_menu = self.menuBar().addMenu("&Panel")
        self.check_foreground = panel_menu.addAction("Check Foreground", self._check_foreground)
        self.propose_mask = panel_menu.addAction("Propose Sky Mask…", self._propose_mask)
        layers_menu = self.menuBar().addMenu("&Layers")
        self.align_menu = layers_menu.addMenu("Align Foreground")
        self.review_points_action = self.align_menu.addAction(
            "Review Control Points…", self._review_terrain_points
        )
        self.align_action = self.align_menu.addAction("Match Translations", self._align_foreground)
        self.foreground_details_action = layers_menu.addAction(
            "Foreground Alignment Details…", self._foreground_alignment_details
        )
        self.placement_action = layers_menu.addAction("Propose Placement", self._propose_placement)
        self.composition_action = layers_menu.addAction(
            "Composition Settings…", self._composition_settings
        )
        tools_menu = self.menuBar().addMenu("&Tools")
        self.plate_solve_settings_action = tools_menu.addAction(
            "Plate Solve Settings…", self._plate_solve_settings
        )
        self.command_panel = CommandPanel(self, self._session_command)
        self.command_panel.running_changed.connect(self._command_running_changed)
        command_dock = QDockWidget("Command Panel", self)
        command_dock.setWidget(self.command_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, command_dock)
        self.command_panel_action = command_dock.toggleViewAction()
        self.command_panel_action.triggered.connect(self._focus_command_panel)
        tools_menu.addAction(self.command_panel_action)
        self.revalidate_solve_action = panel_menu.addAction(
            "Revalidate Plate Solution", self._revalidate_plate_solve
        )
        self.solve_details_action = panel_menu.addAction(
            "Plate Solve Details…", self._plate_solve_details
        )

        body = QWidget(self)
        self.setCentralWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        self.viewport = SkyViewport(use_gpu=use_gpu)
        self.viewport.view_changed.connect(self._view_changed)
        self.viewport.crop_changed.connect(self._show_crop_bounds)
        self._editor = QWidget(body)
        controls = QVBoxLayout(self._editor)
        controls.setContentsMargins(0, 0, 0, 6)
        buttons = QHBoxLayout()
        self.panel_heading = QLabel("Panels")
        self.panel_heading.setProperty("sectionTitle", True)
        buttons.addWidget(self.panel_heading)
        buttons.addStretch()
        self.table_view = QComboBox()
        self.table_view.addItems(list(VIEWS))
        self.table_view.setAccessibleName("Panel table columns")
        self.table_view.setToolTip("Choose the panel properties to display")
        buttons.addWidget(self.table_view)
        self.add_button = QPushButton("Add Panels…")
        self.add_button.clicked.connect(self._add)
        buttons.addWidget(self.add_button)
        self.panel_button = QPushButton("Panel Settings…")
        self.panel_button.clicked.connect(self._panel_settings)
        buttons.addWidget(self.panel_button)
        self.plate_solve_button = QPushButton("Plate Solve")
        self.plate_solve_button.setToolTip("Solve sky panels that need a usable WCS.")
        self.plate_solve_button.clicked.connect(self._plate_solve)
        buttons.addWidget(self.plate_solve_button)
        more = QToolButton()
        more.setText("More")
        more.setAccessibleName("More panel actions")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_menu = QMenu(more)
        self.relink_action = more_menu.addAction("Relink…", self._relink)
        self.mask_action = more_menu.addAction("Edit Sky Mask…", self._edit_mask)
        more_menu.addSeparator()
        self.remove_action = more_menu.addAction("Remove Panel", self._remove)
        more.setMenu(more_menu)
        buttons.addWidget(more)
        controls.addLayout(buttons)
        self.panels = PanelTable()
        self.table_view.currentTextChanged.connect(self.panels.show_view)
        self.panels.properties.panelEdited.connect(self._update_panel)
        self.panels.selectionModel().currentRowChanged.connect(self._selection_changed)
        controls.addWidget(self.panels, 1)
        splitter.addWidget(self._editor)
        preview = QWidget()
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(0, 6, 0, 0)
        preview_header = QHBoxLayout()
        self.preview_title = QLabel("Preview")
        self.preview_title.setProperty("sectionTitle", True)
        preview_header.addWidget(self.preview_title)
        self.auto_frame_check = QCheckBox("Auto Frame")
        self.auto_frame_check.setToolTip("Fit the preview to the solved sky panels.")
        self.auto_frame_check.toggled.connect(self._set_auto_frame)
        preview_header.addWidget(self.auto_frame_check)
        preview_header.addStretch()
        self.band_label = QLabel("Sky band")
        self.band_box = QComboBox()
        self.band_box.setAccessibleName("Sky band")
        self.band_box.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.band_box.setMinimumContentsLength(12)
        self.band_label.setBuddy(self.band_box)
        self.band_box.currentIndexChanged.connect(self._layer_changed)
        preview_header.addWidget(self.band_label)
        preview_header.addWidget(self.band_box)
        self.use_preview_grid_button = QPushButton("Use Preview Grid")
        self.use_preview_grid_button.setToolTip(
            "Use this framing as the saved sky grid for export."
        )
        self.use_preview_grid_button.clicked.connect(self._adopt_preview_grid)
        preview_header.addWidget(self.use_preview_grid_button)
        preview_layout.addLayout(preview_header)
        self.grid_summary = QLabel()
        self.grid_summary.setTextFormat(Qt.TextFormat.PlainText)
        self.grid_summary.setWordWrap(True)
        grid_controls = QHBoxLayout()
        grid_controls.addWidget(self.grid_summary, 1)
        self.edit_crop_button = QPushButton("Edit Crop…")
        self.edit_crop_button.clicked.connect(self._start_crop)
        grid_controls.addWidget(self.edit_crop_button)
        preview_layout.addLayout(grid_controls)
        self.crop_controls = QWidget(preview)
        crop_row = QHBoxLayout(self.crop_controls)
        crop_row.setContentsMargins(0, 0, 0, 0)
        self.crop_bounds = QLabel()
        self.crop_bounds.setWordWrap(True)
        crop_row.addWidget(self.crop_bounds, 1)
        self.auto_crop_button = QPushButton("Use Auto Crop")
        self.auto_crop_button.clicked.connect(self._reset_crop)
        crop_row.addWidget(self.auto_crop_button)
        self.apply_crop_button = QPushButton("Apply Crop")
        self.apply_crop_button.clicked.connect(self._apply_crop)
        crop_row.addWidget(self.apply_crop_button)
        self.cancel_crop_button = QPushButton("Cancel")
        self.cancel_crop_button.clicked.connect(self._restore_crop_preview)
        crop_row.addWidget(self.cancel_crop_button)
        preview_layout.addWidget(self.crop_controls)
        preview_layout.addWidget(self.viewport, 1)
        splitter.addWidget(preview)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([235, 380])
        splitter.setHandleWidth(3)
        layout.addWidget(splitter, 1)

        actions = QHBoxLayout()
        self.settings_button = QPushButton("Mosaic Settings…")
        self.settings_button.clicked.connect(self._settings)
        self.preview_button = QPushButton("Build Preview")
        self.preview_button.clicked.connect(self._preview)
        self.start_button = QPushButton("Export Mosaic…")
        self.start_button.setProperty("primary", True)
        self.start_button.clicked.connect(self._start)
        self.cancel_button = QPushButton("Cancel Job")
        self.cancel_button.hide()
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
        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setObjectName("workspaceProgress")
        self.progress.setAccessibleName("Job progress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setMinimumHeight(24)
        self.progress_percent = QLabel("0%")
        self.progress_percent.setObjectName("jobPercentage")
        self.progress_percent.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.progress.valueChanged.connect(self._show_job_percentage)
        self.progress_elapsed = QLabel()
        self.progress_elapsed.setToolTip("Time since Plate Solve started.")
        self._solve_timer = QTimer(self)
        self._solve_timer.setInterval(1000)
        self._solve_timer.timeout.connect(self._update_solve_elapsed)
        self.status = QLabel("Add linear FITS, TIFF, or XISF panels to begin.")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        footer = QVBoxLayout()
        footer.setSpacing(6)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status, 1)
        status_row.addWidget(self.progress_elapsed)
        status_row.addWidget(self.cancel_button)
        footer.addLayout(status_row)
        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.progress_percent)
        footer.addLayout(progress_row)
        self._show_job_progress(False)
        layout.addLayout(footer)
        self.panels.properties.invalidEdit.connect(self._invalid_panel_edit)
        self._refresh()
        self.resizeDocks(
            [command_dock], [command_dock.minimumSizeHint().height()], Qt.Orientation.Vertical
        )

    def _refresh(self, selected: int = -1) -> None:
        if self._solved_panels is not self.project.panels:
            self._solved_panels = ()
            self._solve_outcomes.clear()
        rows = [
            panel_row(
                panel,
                self._panel_inspection(index),
                self._solve_outcomes.get(index),
                self.project.filter_name,
            )
            for index, panel in enumerate(self.project.panels)
        ]
        self.panels.properties.refresh(rows)
        self.panel_heading.setText(f"Panels ({len(rows)})" if rows else "Panels")
        linked = all(row.linked for row in rows)
        if rows:
            current = self.panels.currentIndex()
            row = max(0, min(selected, len(rows) - 1))
            if current.row() != row:
                self.panels.selectRow(row)
        if self._preview_project is not None and (
            self._preview_project != self.project or not linked
        ):
            self._clear_preview()
            self._queue_live_preview()
        self._selection_changed()
        name = self.project_path.name if self.project_path else "Untitled"
        marker = "*" if self.project != self._saved else ""
        self.setWindowTitle(f"{name}{marker} — {self._app_title}")
        self.command_panel.set_project_path(self.project_path)
        self._refresh_bands()
        self._layer_controls()
        self.cancel_button.setEnabled(self.job is not None)
        self._start_panel_inspection()
        if self._live_pending and not self._is_running():
            self._preview_timer.start()

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
                info = self._inspections[index]
                dialog.show_embedded_optics(info.embedded_optics, info.camera_model)
                dialog.band_override.setPlaceholderText(info.filter_name or "")
                dialog.photo_source_info.setText(info.photo_color_hint or "Source unavailable")
        job.deleteLater()
        if self._close_after_job:
            self._finish_close_if_ready()
            return
        self._refresh(self.panels.currentIndex().row())

    def _is_running(self) -> bool:
        return self.job is not None or self.command_panel.is_running

    def _layer(self) -> Layer:
        return _LAYERS[self.layer_box.currentIndex()]

    def _sky_band(self) -> str | None:
        return cast(str | None, self.band_box.currentData()) if self._layer() == "sky" else None

    def _refresh_bands(self) -> None:
        selected = self.band_box.currentData()
        bands: dict[str, None] = {}
        for index in self.project.sky_indices():
            info = self._panel_inspection(index)
            if info is not None and info.wcs_status != "Unavailable":
                label = self.project.panels[index].sky_band(
                    info.filter_name, self.project.filter_name
                )
                bands[label] = None
        with QSignalBlocker(self.band_box):
            self.band_box.clear()
            self.band_box.addItem("Select a band" if len(bands) > 1 else "All sky panels")
            for label in bands:
                self.band_box.addItem(label, label)
            self.band_box.setCurrentIndex(max(0, self.band_box.findData(selected)))

    def _layer_controls(self) -> None:
        cropping = self._crop_draft is not None
        idle = not self._is_running() and not cropping
        layer = self._layer()
        ground = self.project.current_foreground()
        sky = bool(self.project.sky_indices())
        ground_count = len(self.project.foreground_inputs())
        self.align_menu.setEnabled(idle and ground_count > 0)
        self.align_action.setEnabled(idle and ground_count > 0)
        self.review_points_action.setEnabled(idle and ground_count > 1)
        if self._foreground_panels is not self.project.panels:
            self._foreground_report = None
            self._foreground_panels = None
        self.foreground_details_action.setEnabled(idle and self._foreground_report is not None)
        self.placement_action.setEnabled(idle and ground is not None and sky)
        self.composition_action.setEnabled(idle and ground is not None and sky)
        self.layer_box.setEnabled(idle and bool(self.project.panels))
        show_band = layer == "sky" and self.band_box.count() > 2
        self.band_label.setVisible(show_band)
        self.band_box.setVisible(show_band)
        self.band_box.setEnabled(idle and show_band)
        self.overlap_check.setVisible(layer == "composition")
        self.overlap_check.setEnabled(
            self._display_frame is not None and self._display_frame.common_coverage is not None
        )
        self.auto_frame_check.setVisible(layer == "sky")
        self.auto_frame_check.setEnabled(idle and layer == "sky")
        with QSignalBlocker(self.auto_frame_check):
            self.auto_frame_check.setChecked(self.project.auto_frame_preview)
        can_adopt = layer == "sky" and self._preview_grid is not None
        self.use_preview_grid_button.setVisible(can_adopt)
        self.use_preview_grid_button.setEnabled(idle and can_adopt)
        self.edit_crop_button.setVisible(layer == "sky" and not cropping)
        self.edit_crop_button.setEnabled(
            idle and self._preview_project == self.project
            and self._display_frame is not None and self._display_frame.has_coverage
        )
        self.crop_controls.setVisible(cropping)
        crop_ready = cropping and self.job is None
        self.apply_crop_button.setEnabled(crop_ready and self.viewport.crop is not None)
        self.auto_crop_button.setEnabled(
            crop_ready and self._crop_draft is not None and self._crop_draft.suggested is not None
        )
        self.cancel_crop_button.setEnabled(crop_ready)
        spec = self.project.render
        region = spec.output_region()
        ready = False
        if layer == "sky":
            if self._crop_draft is not None:
                width, height = self._crop_draft.grid.size
                summary = f"Full sky grid · {width:,} × {height:,} px"
            elif self.project.auto_frame_preview and self._preview_grid is None:
                summary = "Fit to solved sky panels"
            else:
                preview_spec = self._preview_grid or spec
                ra, dec = preview_spec.center
                framing = preview_spec.output_region()
                summary = (
                    f"ICRS {preview_spec.projection}  ·  RA {ra:.7g}°, Dec {dec:.7g}°"
                    f"  ·  {framing.width} × {framing.height} px"
                    f"  ·  {preview_spec.scale_arcsec:g} arcsec/px"
                )
            band = self._sky_band()
            ready = sky and (self.band_box.count() <= 2 or band is not None)
            if band is not None:
                summary += f"  ·  {band}"
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
        photo = self._photo_preview_ready()
        self.start_button.setText("Export Photo Mosaic…" if photo else "Export Mosaic…")
        self.start_button.setEnabled(idle and ready)
        self.scientific_export.setEnabled(idle and ready and layer == "sky")
        self.preview_button.setEnabled(idle and ready)
        self.plate_solve_button.setEnabled(idle and sky)

    @Slot()
    def _layer_changed(self) -> None:
        self._clear_preview()
        self._queue_live_preview()
        self._layer_controls()
        self.progress.setValue(0)
        if self.job is None:
            self._show_job_progress(False)
        self.status.setText("")

    def _selection_changed(self) -> None:
        index = self.panels.currentIndex().row()
        selected = index >= 0 and not self._is_running()
        for control in (
            self.relink_action,
            self.panel_button,
            self.mask_action,
            self.remove_action,
        ):
            control.setEnabled(selected)
        self.check_foreground.setEnabled(selected)
        self.propose_mask.setEnabled(
            selected and self.project.panels[index].foreground_tag in ("mixed", "uncertain")
        )
        self.revalidate_solve_action.setEnabled(selected and index in self.project.sky_indices())
        info = self._panel_inspection(index)
        self.solve_details_action.setEnabled(
            selected
            and (
                index in self._solve_outcomes
                or (info is not None and info.wcs_status in ("Embedded", "Sidecar"))
            )
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
        self._preview_timer.stop()
        self._live_ready = self._live_pending = False
        self._clear_preview()
        self._foreground_report = None
        self._foreground_panels = None
        with QSignalBlocker(self.band_box):
            self.band_box.setCurrentIndex(0)
        self.project = self._saved = project
        self.project_path = path
        self.progress.setValue(0)
        self._show_job_progress(False)
        self._refresh()

    def _new(self) -> None:
        if self._confirm_discard():
            self._new_project()

    def _new_project(self) -> None:
        self._set_project(MosaicProject(auto_frame_preview=True), None)
        self._report_operation("New project.")

    def _open(self) -> None:
        if not self._confirm_discard():
            return
        name, _ = QFileDialog.getOpenFileName(self, "Open Project", "", _PROJECT_FILTER)
        if not name:
            return
        try:
            self._open_project(Path(name))
        except (OSError, ValueError) as error:
            self._error("Open failed", error)

    def _open_project(self, path: Path) -> None:
        self._set_project(load_project(path), path)
        self._report_operation(f"Opened {path.name}.")

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
            self._save_project(path, replace_existing=replace_existing)
        except (OSError, ValueError, OverflowError) as error:
            self._error("Save failed", error)
            return False
        return True

    def _save_project(self, path: Path, *, replace_existing: bool) -> None:
        save_project(path, self.project, replace_existing=replace_existing)
        self.project_path, self._saved = path, self.project
        self._refresh(self.panels.currentIndex().row())
        self._report_operation(f"Saved {path.name}.")

    def _add(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(self, "Add Panels", "", PANEL_FILES)
        if not names:
            return
        try:
            self._add_paths(tuple(map(Path, names)))
        except (OSError, ValueError) as error:
            self._error("Add failed", error)

    def _add_paths(self, paths: tuple[Path, ...]) -> None:
        sources = tuple(FileReference.capture(path) for path in paths)
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
            self._report_operation(f"Added {len(additions)} panel(s).")
            indices = tuple(range(start, len(self.project.panels)))
            self._launch_job(ForegroundJob(self.project, indices, self), "Checking foreground…")
        else:
            self._report_operation("Panels already added.")

    def _relink(self) -> None:
        index = self.panels.currentIndex().row()
        panel = self.project.panels[index]
        name, _ = QFileDialog.getOpenFileName(
            self, "Relink Panel", panel.source.path.name, PANEL_FILES
        )
        if name:
            try:
                self._relink_panel(index, Path(name))
            except (OSError, ValueError) as error:
                self._error("Relink failed", error)

    def _relink_panel(self, index: int, path: Path) -> None:
        self.project = self.project.relink_panel(index, path)
        self._refresh(index)
        self._report_operation(f"Relinked {path.name}.")

    def _session_panel(self, number: int) -> int:
        if not 1 <= number <= len(self.project.panels):
            raise ValueError("The panel number is outside the active project.")
        return number - 1

    def _session_command(self, arguments: Namespace, directory: Path) -> str | None:
        action = arguments.action
        dirty = self.project != self._saved
        if action in {"new", "open", "close"} and dirty and not arguments.discard:
            raise ValueError(
                "The active project has unsaved changes. Run session save or pass --discard."
            )
        match action:
            case "status":
                return json.dumps(
                    {
                        "schema_version": 1,
                        "project": str(self.project_path) if self.project_path else None,
                        "dirty": dirty,
                        "panels": len(self.project.panels),
                    },
                    sort_keys=True,
                )
            case "new":
                self._new_project()
            case "open":
                self._open_project(directory / arguments.path)
            case "close":
                if dirty:
                    self._set_project(MosaicProject(), None)
                QTimer.singleShot(0, self.close)
            case "save":
                if arguments.path is None:
                    if self.project_path is None:
                        raise ValueError("Supply a project filename for the first save.")
                    self._save_project(self.project_path, replace_existing=True)
                else:
                    path = directory / arguments.path
                    if not path.suffix:
                        path = path.with_suffix(".astromosaic")
                    self._save_project(path, replace_existing=arguments.replace)
            case "add":
                self._add_paths(tuple(directory / path for path in arguments.paths))
            case "relink":
                self._relink_panel(self._session_panel(arguments.panel), directory / arguments.path)
            case "use-preview-grid":
                self._adopt_preview_grid()
            case "export-photo":
                self._export_photo_to(directory / arguments.output)
            case "preview" | "export":
                if not self.project.panels:
                    raise ValueError("Add panels to the active project first.")
                if action == "preview":
                    if arguments.grid is not None:
                        if self._layer() != "sky":
                            raise ValueError("Select the sky layer to set the sky preview grid.")
                        self._set_auto_frame(arguments.grid == "auto")
                    self._preview()
                else:
                    layer: Layer = arguments.layer or self._layer()
                    band = arguments.band if arguments.band is not None else self._sky_band()
                    if arguments.band is not None and layer != "sky":
                        raise ValueError("Select a band only for the sky layer.")
                    self._export_to(
                        directory / arguments.output, layer, band if layer == "sky" else None
                    )
            case "solve":
                sky = self.project.sky_indices()
                if not sky:
                    raise ValueError("The active project has no sky panels.")
                index = (
                    self._session_panel(arguments.panel) if arguments.panel is not None else None
                )
                if index is not None and index not in sky:
                    raise ValueError("The selected panel is excluded from the sky layer.")
                self._start_plate_solve(index)
        return None

    def _remove(self) -> None:
        index = self.panels.currentIndex().row()
        panels = self.project.panels
        self.project = replace(self.project, panels=panels[:index] + panels[index + 1 :])
        self._refresh(index)
        self._report_operation(f"Removed {panels[index].source.path.name}.")

    def _panel_settings(self) -> None:
        index = self.panels.currentIndex().row()
        panels = self.project.panels
        dialog = PanelSettings(panels[index], self)
        info = self._panel_inspection(index)
        dialog.show_embedded_optics(
            info.embedded_optics if info is not None else PanelOptics(),
            info.camera_model if info is not None else None,
        )
        if info is not None:
            dialog.band_override.setPlaceholderText(info.filter_name or "")
            dialog.photo_source_info.setText(info.photo_color_hint or "Source unavailable")
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

    def _update_panel(self, index: int, panel: ProjectPanel, *, summary: str | None = None) -> None:
        panels = self.project.panels
        previous = panels[index]
        if panel == previous:
            return
        self.project = replace(self.project, panels=panels[:index] + (panel,) + panels[index + 1 :])
        # Table edits only change how the project uses the inspected source.
        if self._inspected_panels is panels and panel == replace(
            previous,
            optics=panel.optics,
            include_sky=panel.include_sky,
            weight=panel.weight,
            band_override=panel.band_override,
            photo_profile=panel.photo_profile,
            photo_ev=panel.photo_ev,
        ):
            self._inspected_panels = self.project.panels
            if self._solved_panels is panels:
                self._solved_panels = self.project.panels
        self._refresh(index)
        self._report_operation(summary or f"Updated settings for {panel.source.path.name}.")

    @Slot(str)
    def _invalid_panel_edit(self, detail: str) -> None:
        self._report_operation("Invalid panel edit.", detail=detail)

    def _check_foreground(self) -> None:
        index = self.panels.currentIndex().row()
        if index >= 0 and not self._is_running():
            self._launch_job(ForegroundJob(self.project, (index,), self), "Checking foreground…")

    def _edit_mask(self) -> None:
        self._open_mask_editor(propose=False)

    def _propose_mask(self) -> None:
        self._open_mask_editor(propose=True)

    def _open_mask_editor(self, *, propose: bool) -> None:
        index = self.panels.currentIndex().row()
        if index >= 0 and not self._is_running():
            name = self.project.panels[index].source.path.name
            self._launch_job(
                MaskEditorJob(self.project, index, propose, self), f"Preparing sky mask for {name}…"
            )

    def _settings(self) -> None:
        selected_band = self._sky_band()
        inputs = set()
        for index in self.project.sky_indices():
            inspection = self._panel_inspection(index)
            if inspection is None or inspection.descriptor is None:
                continue
            band = self.project.panels[index].sky_band(
                inspection.filter_name, self.project.filter_name
            )
            if selected_band is None or band == selected_band:
                descriptor = inspection.descriptor
                unit = (
                    "sRGB" if descriptor.icc_encoding == "srgb"
                    else descriptor.unit or "no brightness unit"
                )
                inputs.add(f"{band} · {unit}")
        dialog = ProjectSettings(
            self.project, self, preview_grid=self._preview_grid,
            suggested_rotation=self._suggested_rotation, input_metadata=", ".join(sorted(inputs)),
        )
        try:
            while dialog.exec():
                try:
                    previous = self.project
                    self.project = dialog.settings()
                except (OSError, ValueError, OverflowError) as error:
                    self._error("Invalid mosaic settings", error)
                    continue
                self._refresh(self.panels.currentIndex().row())
                summary = "Mosaic settings applied."
                if previous.composition is not None and self.project.composition is None:
                    summary += " Set the composition placement for the new sky grid."
                self._report_operation(summary)
                break
        finally:
            dialog.deleteLater()

    def _plate_solve_settings(self) -> None:
        dialog = PlateSolveSettings(self)
        dialog.operation_summary.connect(self.command_panel.append_summary)
        try:
            if dialog.exec():
                self._report_operation("Saved local plate solve settings.")
        finally:
            dialog.deleteLater()

    def _plate_solve(self) -> None:
        self._start_plate_solve()

    def _revalidate_plate_solve(self) -> None:
        index = self.panels.currentIndex().row()
        if index in self.project.sky_indices():
            self._start_plate_solve(index)

    def _plate_solve_details(self) -> None:
        index = self.panels.currentIndex().row()
        info = self._panel_inspection(index)
        outcome = self._solve_outcomes.get(index)
        has_wcs = info is not None and info.wcs_status in ("Embedded", "Sidecar")
        if outcome is None and not has_wcs:
            return
        quality: dict[str, object] = {}
        attempts: list[dict[str, object]] = []
        if outcome is not None:
            quality = outcome.quality or {}
            attempts = [asdict(attempt) for attempt in outcome.attempts]
            has_wcs = has_wcs or outcome.sidecar is not None
        if (info is not None and info.wcs_status == "Sidecar") or (
            outcome is not None and outcome.sidecar is not None
        ):
            reference = self.project.panels[index].wcs_sidecar
            assert reference is not None
            try:
                if reference.status() != "Ready":
                    raise ValueError("The WCS sidecar changed. Reopen the project to verify it.")
                quality, saved_attempts = read_solution_diagnostics(reference.path)
                if outcome is None:
                    attempts = saved_attempts
            except (OSError, ValueError) as error:
                if outcome is None:
                    self._report_operation("Could not read plate solve details.", detail=str(error))
                    return
                has_wcs = False
                quality = {}
        dialog = PlateSolveDetails(
            quality,
            self,
            attempts=attempts,
            solve_error=outcome.error if outcome is not None else None,
            has_wcs=has_wcs,
        )
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def _start_plate_solve(self, selected_panel: int | None = None) -> None:
        if self._is_running() or not self.project.sky_indices():
            return
        if self.project_path is None:
            local_data = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppLocalDataLocation
            )
            if not local_data:
                self._report_operation("Could not locate local application data for WCS sidecars.")
                return
            directory = Path(local_data) / "wcs"
        else:
            directory = self.project_path.with_name(f"{self.project_path.name}.wcs")
        options = replace(load_plate_solve_settings(), revalidate=selected_panel is not None)
        job = PlateSolveJob(self.project, options, directory, self, selected_panel=selected_panel)
        message = "Preparing plate solve for sky panels that need a WCS…"
        if selected_panel is not None:
            name = self.project.panels[selected_panel].source.path.name
            message = f"Revalidating plate solution for {name}…"
        self._launch_job(job, message)

    def _photo_preview_ready(self) -> bool:
        return (
            self._layer() == "sky"
            and self._preview_project == self.project
            and self._display_frame is not None
            and self._display_frame.has_coverage
            and self._crop_draft is None
            and self._display_frame.photo_levels is not None
        )

    def _start(self) -> None:
        self._choose_export_path(photo=self._photo_preview_ready())

    def _start_scientific(self) -> None:
        self._choose_export_path(photo=False)

    def _choose_export_path(self, *, photo: bool) -> None:
        if self._is_running() or not self.project.panels:
            return
        name, selected = QFileDialog.getSaveFileName(
            self,
            "Export Photo Mosaic" if photo else "Render Mosaic",
            "",
            _TIFF_FILTER if photo else f"{_TIFF_FILTER};;{_FITS_FILTER};;{_XISF_FILTER}",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not name:
            return
        path = Path(name)
        if not path.suffix:
            path = path.with_suffix(
                {_FITS_FILTER: ".fits", _XISF_FILTER: ".xisf"}.get(selected, ".tiff")
            )
        if photo:
            self._export_photo_to(path)
        else:
            self._export_to(path, self._layer(), self._sky_band())

    def _export_photo_to(self, path: Path) -> None:
        if not self._photo_preview_ready():
            raise ValueError("Build a covered sRGB sky preview before exporting a photo.")
        self._launch_job(
            MosaicJob(
                self.project,
                path,
                self,
                band=self._sky_band(),
                photo_grid=self._preview_grid or self.project.render,
                photo_tone=self.viewport.photo_tone(),
            ),
            f"Preparing photo mosaic export to {path.name}…",
        )

    def _export_to(self, path: Path, layer: Layer, band: str | None) -> None:
        self._launch_job(
            MosaicJob(self.project, path, self, layer, band=band),
            f"Preparing {layer} mosaic export to {path.name}…",
        )

    def _clear_preview(self) -> None:
        self._detail_timer.stop()
        if self._detail_job is not None:
            self._detail_job.cancel()
        self._crop_draft = None
        self._suggested_rotation = None
        self._preview_project = None
        self._preview_grid = None
        self.preview_title.setText("Preview")
        self._display_frame = None
        self.overlap_check.setEnabled(False)
        self.viewport.set_crop(None)
        self.viewport.set_frame(None)

    @Slot(bool)
    def _toggle_live_preview(self, enabled: bool) -> None:
        if enabled and self._preview_project != self.project:
            self._queue_live_preview()
        elif not enabled:
            self._preview_timer.stop()
            self._live_pending = False

    def _queue_live_preview(self) -> None:
        if self._live_ready and self.live_preview_action.isChecked() and self._layer() == "sky":
            self._live_pending = True
            self._preview_timer.start()

    @Slot()
    def _live_preview(self) -> None:
        if not self._live_pending or self._close_after_job or self._crop_draft is not None:
            return
        if self._is_running() or self._inspection_job is not None or QApplication.activeModalWidget():
            self._preview_timer.start()
            return
        selected = self._sky_band()
        if self._layer() != "sky" or (self.band_box.count() > 2 and selected is None):
            return
        ready = False
        for index in self.project.sky_indices():
            info = self._panel_inspection(index)
            if info is None:
                return
            band = self.project.panels[index].sky_band(info.filter_name, self.project.filter_name)
            if selected is None or selected == band:
                if info.wcs_status not in ("Embedded", "Sidecar"):
                    return
                ready = True
        if ready:
            self._preview()

    @Slot()
    def _view_changed(self) -> None:
        if self._display_frame is None or self.job is not None or self._close_after_job:
            return
        edge = self.viewport.overview_edge()
        if self.viewport.visible_detail() is None and self._overview_edge and (
            abs(edge - self._overview_edge) >= 256
        ):
            self._queue_live_preview()
        self._detail_timer.start()

    @Slot()
    def _request_detail(self) -> None:
        frame = self._display_frame
        window = self.viewport.visible_detail()
        if window is None:
            self.viewport.clear_detail()
            if self._detail_job is not None:
                self._detail_job.cancel()
            return
        if frame is None or frame.tone_levels is None or self._is_running() or self._close_after_job:
            return
        if self.viewport.detail is not None and self.viewport.detail.contains(window):
            return
        if self._detail_job is not None:
            if not self._detail_job.window.contains(window):
                self._detail_job.cancel()
            return
        padded = window.with_halo(*frame.output_size, 48)
        if padded.width * padded.height <= MAX_DETAIL_PIXELS:
            window = padded
        grid = (
            replace(self._crop_draft.grid, crop=None) if self._crop_draft is not None
            else self._preview_grid or self.project.render
        )
        job = PreviewDetailJob(
            self.project, self, self._layer(), window, frame.tone_levels,
            band=self._sky_band(), grid=grid,
        )
        self._detail_base, self._detail_job = frame, job
        job.finished.connect(self._finish_detail)
        job.start()

    @Slot()
    def _finish_detail(self) -> None:
        job, self._detail_job = self._detail_job, None
        assert job is not None
        request = self.viewport.visible_detail()
        if self.job is not None:
            self.job.start()
        elif not self._close_after_job and request is not None and (
            self._detail_base is self._display_frame and job.project == self.project
        ):
            if job.result is not None and job.window.contains(request):
                detail = highlight_overlap(job.result) if self.overlap_check.isChecked() else job.result
                self.viewport.set_detail(job.window, detail)
            elif job.error is None:
                self._detail_timer.start()
        self._detail_base = None
        job.deleteLater()
        self._finish_close_if_ready()

    @Slot(bool)
    def _set_auto_frame(self, enabled: bool) -> None:
        if enabled != self.project.auto_frame_preview:
            self.project = replace(self.project, auto_frame_preview=enabled)
            self._refresh(self.panels.currentIndex().row())

    @Slot()
    def _adopt_preview_grid(self) -> None:
        grid = self._preview_grid
        if self._is_running() or grid is None or self._preview_project != self.project:
            raise ValueError("Build an automatically framed sky preview first.")
        previous = self.project
        composition = previous.composition if grid == previous.render else None
        self.project = replace(
            previous, render=grid, auto_frame_preview=False, composition=composition
        )
        self._preview_project = self.project
        self._preview_grid = None
        self._refresh(self.panels.currentIndex().row())
        text = "Applied the preview grid to the sky export settings."
        if previous.composition is not None and composition is None:
            text += " Set the composition placement for the new sky grid."
        self._report_operation(text)

    def _preview(self) -> None:
        if self._is_running() or not self.project.panels:
            return
        edge = self.viewport.overview_edge()
        self._clear_preview()
        self._live_pending = False
        self._preview_timer.stop()
        layer = self._layer()
        self._live_ready = self._live_ready or layer == "sky"
        job = PreviewJob(
            self.project, self, layer, band=self._sky_band(),
            adaptive_edge=edge,
        )
        job.proxy_ready.connect(self._show_proxy)
        self._launch_job(job, f"Preparing {layer} preview…")

    @Slot()
    def _start_crop(self) -> None:
        if self._is_running() or self._display_frame is None or self._preview_project != self.project:
            return
        grid = self._preview_grid or self.project.render
        draft = _CropDraft(grid, self._display_frame, self._preview_grid, self._suggested_rotation)
        self._clear_preview()
        self._crop_draft = draft
        self._show_crop_bounds(grid.output_region())
        job = PreviewJob(
            self.project, self, band=self._sky_band(),
            adaptive_edge=self.viewport.overview_edge(), crop_grid=grid,
        )
        job.proxy_ready.connect(self._show_proxy)
        self._launch_job(job, "Preparing the full sky grid for crop editing…")

    @Slot(object)
    def _show_crop_bounds(self, crop: Region) -> None:
        self.crop_bounds.setText(f"Crop {crop.x}, {crop.y} · {crop.width} × {crop.height} px")

    @Slot()
    def _reset_crop(self) -> None:
        if self._crop_draft is not None and (crop := self._crop_draft.suggested) is not None:
            self.viewport.set_crop(crop, editing=True)
            self._show_crop_bounds(crop)

    @Slot()
    def _apply_crop(self) -> None:
        draft, crop = self._crop_draft, self.viewport.crop
        if self._is_running() or draft is None or crop is None:
            return
        grid = replace(draft.grid, crop=None if crop == Region(0, 0, *draft.grid.size) else crop)
        previous = self.project
        self.project = replace(
            previous, render=grid, auto_frame_preview=False,
            frame_locks=previous.frame_locks | {"crop"},
            composition=previous.composition if grid == previous.render else None,
        )
        self._clear_preview()
        self._refresh(self.panels.currentIndex().row())
        self._preview()

    @Slot()
    def _restore_crop_preview(self) -> None:
        if self._crop_draft is None:
            return
        draft = self._crop_draft
        self._clear_preview()
        self._preview_project = self.project
        self._preview_grid = draft.fitted_grid
        self._suggested_rotation = draft.rotation
        self.preview_title.setText("Visual Preview" if draft.frame.photo_levels else "Preview")
        self._set_display_frame(draft.frame)
        self._set_running()
        self._report_operation("Crop changes discarded.")

    @Slot(object, bool)
    def _show_proxy(self, frame: DisplayFrame, visual_only: bool) -> None:
        if self.sender() is self.job and self.cancel_button.isEnabled():
            self.preview_title.setText("Visual Preview" if visual_only else "Preview")
            self._set_display_frame(frame)

    def _set_display_frame(self, frame: DisplayFrame) -> None:
        self._display_frame = frame
        self.overlap_check.setEnabled(frame.common_coverage is not None)
        self._paint_display()
        if self._layer() == "sky":
            draft = self._crop_draft
            crop = Region(0, 0, *frame.output_size) if draft is None else draft.grid.output_region()
            self.viewport.set_crop(crop, editing=draft is not None and self.job is None)

    @Slot()
    def _paint_display(self) -> None:
        frame = self._display_frame
        if frame is not None:
            self.viewport.set_frame(
                highlight_overlap(frame) if self.overlap_check.isChecked() else frame
            )

    def _align_foreground(self) -> None:
        if not self._is_running():
            self._launch_job(
                ForegroundAlignmentJob(self.project, self), "Preparing foreground alignment…"
            )

    def _review_terrain_points(self) -> None:
        if self._is_running() or len(self.project.foreground_inputs()) < 2:
            return
        dialog = TerrainPointEditor(self.project, self)
        try:
            if not dialog.exec() or dialog.aligned_project is None:
                return
            previous = self.project
            self.project = dialog.aligned_project
        finally:
            dialog.deleteLater()
        self._foreground_report = None
        self._foreground_panels = None
        self._refresh(self.panels.currentIndex().row())
        self.layer_box.setCurrentIndex(_LAYERS.index("foreground"))
        assert self.project.foreground is not None
        terrain = self.project.foreground.terrain
        assert terrain is not None
        summary = f"Applied foreground {terrain.model} alignment."
        if previous.composition is not None and self.project.composition is None:
            summary += " Set the composition placement for the new alignment."
        self._report_operation(summary)

    def _foreground_alignment_details(self) -> None:
        report = self._foreground_report
        if (
            report is None
            or self._is_running()
            or self._foreground_panels is not self.project.panels
        ):
            return
        names = tuple(panel.source.path.name for panel in self.project.panels)
        dialog = ForegroundAlignmentDetails(report, names, self)
        try:
            dialog.exec()
            if dialog.selected_panel is not None:
                self.panels.selectRow(dialog.selected_panel)
                self._open_mask_editor(propose=False)
            elif dialog.review_requested:
                self._review_terrain_points()
        finally:
            dialog.deleteLater()

    def _propose_placement(self) -> None:
        if not self._is_running():
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
                self._refresh(self.panels.currentIndex().row())
                self.layer_box.setCurrentIndex(_LAYERS.index("composition"))
                self._report_operation("Composition settings applied.")
                break
        finally:
            dialog.deleteLater()

    def _launch_job(self, job: _Job, message: str) -> None:
        self._detail_timer.stop()
        self.job = job
        if isinstance(job, PlateSolveJob):
            job.solve_progress.connect(self._plate_solve_progress)
            self._set_solve_elapsed(0)
            self.progress.setToolTip("Plate Solve progress is based on completed steps.")
            self._solve_timer.start()
        else:
            job.progress.connect(self._progress)
            job.stage_changed.connect(self._job_stage)
            self.progress.setToolTip("")
        job.finished.connect(self._finished)
        self.progress.setValue(0)
        self.status.setToolTip("")
        self._set_running()
        self._report_operation(message)
        if self._detail_job is None:
            job.start()
        else:
            self._detail_job.cancel()

    def _show_job_progress(self, visible: bool, *, timed: bool = False) -> None:
        self.progress.setVisible(visible)
        self.progress_percent.setVisible(visible)
        self.progress_elapsed.setVisible(visible and timed)

    @Slot(int)
    def _show_job_percentage(self, percentage: int) -> None:
        self.progress_percent.setText(f"{percentage}%")

    def _set_solve_elapsed(self, seconds: float) -> None:
        minutes, seconds_int = divmod(int(seconds), 60)
        self.progress_elapsed.setText(f"Elapsed {minutes}:{seconds_int:02d}")

    @Slot()
    def _update_solve_elapsed(self) -> None:
        if isinstance(self.job, PlateSolveJob):
            self._set_solve_elapsed(monotonic() - self.job.queued_at)

    @Slot(bool)
    def _focus_command_panel(self, visible: bool) -> None:
        if visible:
            self.command_panel.entry.setFocus()

    @Slot()
    def _command_running_changed(self) -> None:
        if self.command_panel.is_running and self._detail_job is not None:
            self._detail_job.cancel()
        self._set_running()
        self._finish_close_if_ready()

    def _set_running(self) -> None:
        running = self._is_running()
        can_edit = not running and self._crop_draft is None
        self._show_job_progress(self.job is not None, timed=isinstance(self.job, PlateSolveJob))
        self.cancel_button.setVisible(self.job is not None)
        for action in self._file_actions:
            action.setEnabled(can_edit)
        self.plate_solve_settings_action.setEnabled(can_edit)
        self._editor.setEnabled(can_edit)
        self.settings_button.setEnabled(can_edit)
        self._layer_controls()
        self.cancel_button.setEnabled(self.job is not None)
        self.command_panel.set_available(self.job is None and self._crop_draft is None)
        self._selection_changed()

    @Slot(object, object)
    def _progress(self, done: int, total: int) -> None:
        job = self.job
        self.progress.setValue((100 * done) // total)
        if job is not None and self.cancel_button.isEnabled():
            self.status.setText(f"{job.progress_label} {done:,} / {total:,} {job.progress_units}.")

    @Slot(str)
    def _job_stage(self, stage: str) -> None:
        if self.job is None or not self.cancel_button.isEnabled():
            return
        if stage == "photo-overlap":
            self.status.setText("Measuring photo overlaps…")
        elif stage == "photo-stars":
            self.status.setText("Checking stellar flux…")

    @Slot(int, str)
    def _plate_solve_progress(self, percentage: int, status: str) -> None:
        if isinstance(self.job, PlateSolveJob) and self.cancel_button.isEnabled():
            self.status.setText(status)
            self.progress.setValue(percentage)

    @Slot()
    def _finished(self) -> None:
        job, self.job = self.job, None
        assert job is not None
        self._set_running()
        if isinstance(job, PreviewJob):
            self._finish_preview(job)
        elif isinstance(job, ForegroundJob):
            self._finish_foreground_check(job)
        elif isinstance(job, MaskEditorJob):
            self._finish_mask_editor(job)
        elif isinstance(job, (ForegroundAlignmentJob, CompositionProposalJob)):
            self._finish_layer_job(job)
        elif isinstance(job, PlateSolveJob):
            self._finish_plate_solve(job)
        elif job.result is not None:
            self.progress.setValue(100)
            text = f"Saved {job.destination.name} · {job.result.covered_pixels:,} covered pixels."
            if job.result.common_pixels is not None:
                text += f" Both layers cover {job.result.common_pixels:,} pixels."
            self._report_operation(text)
            if job.result.photo is not None:
                for line in job.result.photo.lines():
                    self.command_panel.append_summary(line)
        elif job.cancelled:
            self.progress.setValue(0)
            self._report_operation("Mosaic cancelled.")
        else:
            self.progress.setValue(0)
            self._report_render_failure("Mosaic failed.", job)
            self._refresh(self.panels.currentIndex().row())
        job.deleteLater()
        self._finish_close_if_ready()

    def _finish_plate_solve(self, job: PlateSolveJob) -> None:
        self._solve_timer.stop()
        panels = list(self.project.panels)
        solved = 0
        for outcome in job.outcomes:
            if outcome.sidecar is not None:
                panels[outcome.index] = replace(panels[outcome.index], wcs_sidecar=outcome.sidecar)
                solved += 1
        if solved:
            self.project = replace(self.project, panels=tuple(panels))
        self._solved_panels = self.project.panels
        self._solve_outcomes = {outcome.index: outcome for outcome in job.outcomes}
        self._refresh(self.panels.currentIndex().row())
        completed = len(job.outcomes)
        if not job.cancelled and job.error is None:
            self.progress.setValue(100)
        summary = f"{solved} solved, {completed - solved} failed."
        self.status.setToolTip(
            f"Batch elapsed {job.elapsed_seconds:.2f} s. Queue {job.queue_seconds:.2f} s. "
            f"Eligibility check {job.eligibility_seconds:.2f} s."
        )
        if job.cancelled:
            self._report_operation(f"Plate solve cancelled. {summary}")
        elif job.error is not None:
            self._report_operation(f"Plate solve stopped. {summary}", detail=job.error)
        elif not job.total:
            self._report_operation("All sky panels already have a usable WCS.")
        else:
            self._report_operation(f"Plate solve finished. {summary}")
        self._set_solve_elapsed(job.elapsed_seconds)
        self._show_job_progress(True, timed=True)

    def _finish_preview(self, job: PreviewJob) -> None:
        if job.crop_grid is not None:
            draft = self._crop_draft
            assert draft is not None
            if job.result is None:
                self._restore_crop_preview()
                if job.cancelled:
                    self._report_operation("Crop preview cancelled.")
                else:
                    self._report_render_failure("Crop preview failed.", job)
                return
            draft.suggested = job.suggested_crop
            self._overview_edge = job.adaptive_edge or 0
            self.preview_title.setText("Crop Preview")
            self._set_display_frame(job.result)
            self._set_running()
            self._report_operation("Drag the crop edges or handles, then apply the selection.")
            return
        if job.result is not None:
            self._preview_project = job.project
            self._overview_edge = job.adaptive_edge or 0
            self._suggested_rotation = job.suggested_rotation
            if job.result.has_coverage:
                self._preview_grid = job.fitted_grid
            self.preview_title.setText("Visual Preview" if job.visual_only else "Preview")
            self._set_display_frame(job.result)
            self._layer_controls()
            self.progress.setValue(100)
            width, height = job.result.size
            label = (
                "Visual sky preview (sRGB)"
                if job.visual_only
                else f"{job.layer.capitalize()} preview"
            )
            text = (
                f"{label} · {width} × {height} samples."
                if job.result.has_coverage
                else "No coverage at this preview resolution."
            )
            if job.layer == "sky" and not job.result.has_coverage:
                if job.project.auto_frame_preview:
                    text += " Try a smaller selection or choose a sky grid in Mosaic Settings."
                else:
                    text += " Enable Auto Frame or choose a grid that covers the sky panels."
            if job.result.common_coverage is not None:
                text += (
                    f" Both layers cover {int(job.result.common_coverage.sum()):,} preview samples."
                )
            self._report_operation(text)
            if job.photo_report is not None:
                for line in job.photo_report.lines():
                    self.command_panel.append_summary(line)
            self._view_changed()
        else:
            self._clear_preview()
            self.progress.setValue(0)
            if job.cancelled:
                self._report_operation("Preview cancelled.")
            else:
                self._report_render_failure("Preview failed.", job)
                self._refresh(self.panels.currentIndex().row())

    def _finish_layer_job(self, job: ForegroundAlignmentJob | CompositionProposalJob) -> None:
        details = ""
        if isinstance(job, ForegroundAlignmentJob):
            self._foreground_report = job.report()
            self._foreground_panels = job.project.panels
            self._layer_controls()
            if self._foreground_report is not None:
                details = " See Layers → Foreground Alignment Details."
        if job.result is None:
            self.progress.setValue(0)
            label = job.label.capitalize()
            if job.cancelled:
                self._report_operation(f"{label} cancelled.")
            else:
                self._report_operation(
                    f"{label} failed.", detail=(job.error or "No result was returned.") + details
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
        self._refresh(self.panels.currentIndex().row())
        self.layer_box.setCurrentIndex(_LAYERS.index(layer))
        self.progress.setValue(100)
        self._report_operation(message + details)

    def _finish_foreground_check(self, job: ForegroundJob) -> None:
        if job.result is None:
            self._mask_job_status(job)
            return
        self.project, problems = job.result
        self._refresh(self.panels.currentIndex().row())
        self.progress.setValue(100)
        if problems:
            self._report_operation(
                f"Foreground check failed for {len(problems)} panel(s).", detail=problems[0]
            )
        else:
            self._report_operation(f"Checked {len(job.indices)} panel(s) for foreground.")

    def _finish_mask_editor(self, job: MaskEditorJob) -> None:
        if job.result is None:
            self._mask_job_status(job)
            return
        if self._close_after_job:
            self._report_operation("Sky mask editing cancelled.")
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
            self._report_operation("Sky mask editing cancelled.")
            return
        if (panel.sky_mask is not None and mask is not None and mask == job.result.saved) or (
            panel.sky_mask is None and mask == panel.source_mask
        ):
            self._report_operation("Sky mask kept.")
            return
        message = "Sky mask applied." if mask is not None else "Sky mask removed."
        previous = panel.source_mask.sky_fingerprint if panel.source_mask is not None else None
        current = mask.sky_fingerprint if mask is not None else None
        if panel.wcs_sidecar is not None and (panel.sky_mask is not None or previous != current):
            message += " Recompute or clear the WCS sidecar for the new mask revision."
        self._update_panel(
            job.index, replace(panel, source_mask=mask, sky_mask=None), summary=message
        )

    def _mask_job_status(self, job: ForegroundJob | MaskEditorJob) -> None:
        self.progress.setValue(0)
        name = job.label.capitalize()
        if job.cancelled:
            self._report_operation(f"{name} cancelled.")
        else:
            self._report_operation(f"{name} failed.", detail=job.error or "No result was returned.")

    def _cancel(self) -> None:
        if self.job is not None:
            self.job.cancel()
            self.cancel_button.setEnabled(False)
            self.status.setText(f"Cancelling {self.job.label}…")

    def _report_operation(self, summary: str, *, detail: str = "") -> None:
        if self.job is None:
            self._show_job_progress(False)
        self.status.setText(f"{summary} {detail}" if detail else summary)
        self.command_panel.append_summary(summary)

    def _report_render_failure(self, summary: str, job: MosaicJob | PreviewJob) -> None:
        requirement = job.calibration_requirement
        if requirement is not None:
            self._report_operation(f"{summary} {_CALIBRATION_GUIDANCE[requirement]}")
        else:
            self._report_operation(summary, detail=job.error or "No result was returned.")

    def _error(self, title: str, error: Exception) -> None:
        self.command_panel.append_summary(f"{title}.")
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(str(error))
        box.exec()
        box.deleteLater()

    def _finish_close_if_ready(self) -> None:
        if (
            self._close_after_job and not self._is_running()
            and self._inspection_job is None and self._detail_job is None
        ):
            self._close_after_job = False
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._is_running() or self._inspection_job is not None or self._detail_job is not None:
            self._close_after_job = True
            self._preview_timer.stop()
            self._detail_timer.stop()
            self._cancel()
            self.command_panel.cancel()
            if self._inspection_job is not None:
                self._inspection_job.cancel()
            if self._detail_job is not None:
                self._detail_job.cancel()
            event.ignore()
        elif self._confirm_discard():
            self.viewport.release_opengl()
            self._clear_preview()
            event.accept()
        else:
            event.ignore()
            self._start_panel_inspection()
