"""Desktop project and background render workflow."""

import json
import re
from argparse import Namespace
from dataclasses import asdict, replace
from importlib.metadata import version
from pathlib import Path
from time import monotonic
from typing import cast

from PySide6.QtCore import (
    QRect,
    QSettings,
    QSignalBlocker,
    QSize,
    QStandardPaths,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence, QScreen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from astromosaic.astrometry.hints import PanelOptics
from astromosaic.astrometry.solve import read_solution_diagnostics
from astromosaic.core import Region
from astromosaic.display import DisplayFrame
from astromosaic.pipeline.mosaic import MAX_DETAIL_PIXELS, SkyCalibrationRequirement
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
from astromosaic.ui.appearance import ResponsiveRow, add_theme_menu
from astromosaic.ui.command_panel import CommandPanel
from astromosaic.ui.edit_history import EditHistory
from astromosaic.ui.export_review import (
    ExportDescription,
    ExportRequest,
    ExportReview,
    OutputFormat,
)
from astromosaic.ui.foreground_details import ForegroundAlignmentDetails
from astromosaic.ui.mask_editor import MaskEditor
from astromosaic.ui.mosaic_job import (
    CompositionProposalJob,
    ExportReviewJob,
    ForegroundAlignmentJob,
    ForegroundAlignmentReport,
    ForegroundJob,
    MaskEditorJob,
    MosaicJob,
    PanelInspectionJob,
    PanelIntakeJob,
    PlateSolveJob,
    PreviewDetailJob,
    PreviewJob,
)
from astromosaic.ui.panel_table import VIEWS, PanelTable, panel_row
from astromosaic.ui.plate_solve_details import PlateSolveDetails
from astromosaic.ui.plate_solve_settings import PlateSolveSettings, load_plate_solve_settings
from astromosaic.ui.preview_state import PreviewSelection, PreviewState
from astromosaic.ui.project_settings import (
    PANEL_FILES,
    CompositionSettings,
    PanelSettings,
    ProjectSettings,
)
from astromosaic.ui.sky_viewport import SkyViewport
from astromosaic.ui.terrain_editor import TerrainPointEditor
from astromosaic.ui.workspace_settings import (
    LAYOUT_KEY,
    RECENT_KEY,
    CommandDisplay,
    WindowPlacement,
    WorkspaceSettings,
    recent_projects,
)

_PROJECT_FILTER = "AstroMosaic project (*.astromosaic)"
_GPU_ACCELERATION_SETTING = "preview/gpuAcceleration"
_PANELS, _PREVIEW = range(2)
_PANEL_SUFFIXES = frozenset((".fits", ".fit", ".fts", ".tif", ".tiff", ".xisf"))
_Button = QMessageBox.StandardButton
_Job = (
    MosaicJob
    | PanelIntakeJob
    | ExportReviewJob
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


class _WorkspaceNavigation(QListWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("workspaceNavigation")
        self.setAccessibleName("Workspace views")
        self.addItems(["Panels", "Preview"])
        self.setCurrentRow(_PANELS)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def sizeHint(self) -> QSize:
        return QSize(self.fontMetrics().horizontalAdvance("Preview") + 26, super().sizeHint().height())

    def minimumSizeHint(self) -> QSize:
        return QSize(self.sizeHint().width(), 0)


class _CommandDock(QDockWidget):
    closed = Signal()

    def closeEvent(self, event: QCloseEvent) -> None:
        super().closeEvent(event)
        if event.isAccepted():
            self.closed.emit()


class ProjectWindow(QMainWindow):
    def __init__(self, *, use_gpu: bool = True, preferences: QSettings | None = None) -> None:
        super().__init__()
        app_version = version("astromosaic")
        beta_label = " (Beta)" if re.match(r"(?:\d+!)?[\d.]+b\d+", app_version) else ""
        self._app_title = f"AstroMosaic {app_version}{beta_label}"
        self._history = EditHistory(MosaicProject(auto_frame_preview=True))
        self._revision = self._job_revision = self._inspection_revision = self._detail_revision = 0
        self._saved = self.project
        self.project_path: Path | None = None
        self.job: _Job | None = None
        self._inspection_job: PanelInspectionJob | None = None
        self._inspected_panels: tuple[ProjectPanel, ...] = ()
        self._inspections: tuple[PanelInspection, ...] = ()
        self._solved_panels: tuple[ProjectPanel, ...] = ()
        self._solve_outcomes: dict[int, PanelSolveOutcome] = {}
        self._selected_panel: Path | None = None
        self._foreground_report: ForegroundAlignmentReport | None = None
        self._foreground_panels: tuple[ProjectPanel, ...] | None = None
        self._panel_dialog: tuple[int, PanelSettings] | None = None
        self._preview_state = PreviewState()
        self._preview_needs_panels = True
        self._selected_sky_band: str | None = None
        self._detail_job: PreviewDetailJob | None = None
        self._live_ready = False
        self._live_pending = False
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(350)
        self._preview_timer.timeout.connect(self._live_preview)
        self._detail_timer = QTimer(self)
        self._detail_timer.setSingleShot(True)
        self._detail_timer.setInterval(160)
        self._detail_timer.timeout.connect(self._request_detail)
        self._adaptive_timer = QTimer(self)
        self._adaptive_timer.setSingleShot(True)
        self._adaptive_timer.setInterval(350)
        self._adaptive_timer.timeout.connect(self._refresh_adaptive_preview)
        self._close_after_job = False
        self.resize(1140, 780)
        self.setMinimumWidth(630)
        self.setAcceptDrops(True)
        self._workspace_restored = False
        self._recent_projects: tuple[Path, ...] = ()
        self._dock_size: int | None = None

        file_menu = self.menuBar().addMenu("&File")
        self._file_actions = (
            file_menu.addAction("&New Project", "Ctrl+N", self._new),
            file_menu.addAction("&Open Project…", "Ctrl+O", self._open),
            file_menu.addAction("&Save Project", "Ctrl+S", self._save),
            file_menu.addAction("Save Project &As…", "Ctrl+Shift+S", self._save_as),
        )
        self.recent_menu = file_menu.addMenu("Recent Projects")
        self.recent_menu.setToolTipsVisible(True)
        file_menu.addSeparator()
        self.scientific_export = file_menu.addAction(
            "Export Scientific Mosaic…", self._start_scientific
        )
        edit_menu = self.menuBar().addMenu("&Edit")
        self.undo_action = edit_menu.addAction("&Undo", "Ctrl+Z", self._undo)
        self.redo_action = edit_menu.addAction("&Redo", self._redo)
        self.redo_action.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        view_menu = self.menuBar().addMenu("&View")
        self._preferences = (
            preferences if preferences is not None else QSettings("AstroMosaic", "AstroMosaic")
        )
        self._allow_gpu_preview = use_gpu
        self._use_gpu_preview = use_gpu and self._gpu_acceleration_preference()
        self.live_preview_action = view_menu.addAction("Live Sky Preview")
        self.live_preview_action.setCheckable(True)
        self.live_preview_action.setChecked(bool(
            self._preferences.value("view/liveSkyPreview", True, type=bool)
        ))
        self.live_preview_action.toggled.connect(self._toggle_live_preview)
        self.live_preview_action.toggled.connect(
            lambda enabled: self._preferences.setValue("view/liveSkyPreview", enabled)
        )
        add_theme_menu(view_menu, self._preferences)
        self.focus_mode_action = view_menu.addAction("Preview Focus Mode")
        self.focus_mode_action.setCheckable(True)
        self.focus_mode_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.focus_mode_action.setEnabled(False)
        self.focus_mode_action.toggled.connect(self._set_preview_focus_mode)
        view_menu.addAction("Reset Workspace", self._reset_workspace)
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
        settings_menu = self.menuBar().addMenu("&Settings")
        self.gpu_settings_action = settings_menu.addAction("GPU Acceleration…", self._gpu_settings)
        tools_menu = self.menuBar().addMenu("&Tools")
        self.plate_solve_settings_action = tools_menu.addAction(
            "Plate Solve Settings…", self._plate_solve_settings
        )
        self.command_panel = CommandPanel(self, self._session_command)
        self.command_panel.running_changed.connect(self._command_running_changed)
        self.command_panel.feedback_changed.connect(self._command_feedback)
        self._command_display: CommandDisplay = "collapsed"
        self.command_dock = _CommandDock("Command Panel", self)
        self.command_dock.setWidget(self.command_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.command_dock)
        self.command_dock.hide()
        self.command_dock.closed.connect(lambda: self._show_command_panel(False))
        self.command_panel_action = tools_menu.addAction("Command Panel")
        self.command_panel_action.setCheckable(True)
        self.command_panel_action.setChecked(True)
        self.command_panel_action.toggled.connect(self._show_command_panel)
        self.revalidate_solve_action = panel_menu.addAction(
            "Revalidate Plate Solution", self._revalidate_plate_solve
        )
        self.solve_details_action = panel_menu.addAction(
            "Plate Solve Details…", self._plate_solve_details
        )

        body = QWidget(self)
        self.setCentralWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 3, 16, 3)
        layout.setSpacing(4)
        workspace = QHBoxLayout()
        workspace.setSpacing(8)
        self.navigation = _WorkspaceNavigation()
        workspace.addWidget(self.navigation)
        self.pages = QStackedWidget()
        workspace.addWidget(self.pages, 1)
        layout.addLayout(workspace, 1)
        self.viewport = SkyViewport(use_gpu=self._use_gpu_preview)
        self.viewport.resolution_box.currentIndexChanged.connect(self._resolution_changed)
        self.viewport.view_changed.connect(self._view_changed)
        self.viewport.crop_changed.connect(self._show_crop_bounds)
        self.viewport.crop_cancelled.connect(self._restore_crop_preview)
        self.viewport.outline_selected.connect(self._select_preview_panel)
        self._editor = QWidget(body)
        controls = QVBoxLayout(self._editor)
        controls.setContentsMargins(0, 0, 0, 2)
        main_panel_controls = QWidget()
        main_panel_row = QHBoxLayout(main_panel_controls)
        main_panel_row.setContentsMargins(0, 0, 0, 0)
        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        self.panel_heading = QLabel("Panels")
        self.panel_heading.setProperty("sectionTitle", True)
        main_panel_row.addWidget(self.panel_heading)
        self.open_button = QPushButton("Open Project…")
        self.open_button.clicked.connect(self._open)
        main_panel_row.addWidget(self.open_button)
        buttons.addStretch()
        self.table_view = QComboBox()
        self.table_view.addItems(list(VIEWS))
        self.table_view.setAccessibleName("Panel table columns")
        self.table_view.setToolTip("Choose the panel properties to display")
        buttons.addWidget(self.table_view)
        self.add_button = QPushButton("Add Panels…")
        self.add_button.clicked.connect(self._add)
        main_panel_row.addWidget(self.add_button)
        self.panel_button = QPushButton("Panel Settings…")
        self.panel_button.clicked.connect(self._panel_settings)
        buttons.addWidget(self.panel_button)
        self.plate_solve_button = QPushButton("Plate Solve")
        self.plate_solve_button.setToolTip("Solve sky panels that need a usable WCS.")
        self.plate_solve_button.clicked.connect(self._plate_solve)
        main_panel_row.addWidget(self.plate_solve_button)
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
        controls.addWidget(ResponsiveRow(main_panel_controls, buttons))
        filter_name = QWidget()
        filter_name_row = QHBoxLayout(filter_name)
        filter_name_row.setContentsMargins(0, 0, 0, 0)
        self.filename_filter = QLineEdit()
        self.filename_filter.setAccessibleName("Filter panels by filename")
        self.filename_filter.setPlaceholderText("Filter filename")
        self.filename_filter.setClearButtonEnabled(True)
        self.filename_filter.textChanged.connect(self._filter_panels)
        filter_name_row.addWidget(self.filename_filter)
        filter_choices = QHBoxLayout()
        self.band_filter = QComboBox()
        self.band_filter.setAccessibleName("Filter panels by sky band")
        self.band_filter.addItem("All bands", None)
        self.band_filter.currentIndexChanged.connect(self._filter_panels)
        filter_choices.addWidget(self.band_filter)
        self.wcs_filter = QComboBox()
        self.wcs_filter.setAccessibleName("Filter panels by WCS state")
        self.wcs_filter.addItem("All WCS states", None)
        for state in ("Embedded", "Sidecar", "Missing", "Invalid", "Unavailable", "Checking…"):
            self.wcs_filter.addItem(state, state)
        self.wcs_filter.currentIndexChanged.connect(self._filter_panels)
        filter_choices.addWidget(self.wcs_filter)
        self.clear_filters_button = QPushButton("Clear Filters")
        self.clear_filters_button.clicked.connect(self._clear_panel_filters)
        filter_choices.addWidget(self.clear_filters_button)
        self.panel_filters = ResponsiveRow(filter_name, filter_choices)
        controls.addWidget(self.panel_filters)
        solve_feedback = QHBoxLayout()
        self.solve_summary = QLabel()
        self.solve_summary.setTextFormat(Qt.TextFormat.PlainText)
        self.solve_summary.setWordWrap(True)
        self.solve_summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        solve_feedback.addWidget(self.solve_summary, 1)
        self.solve_summary_details = QPushButton("Plate Solve Details…")
        self.solve_summary_details.clicked.connect(self._plate_solve_details)
        solve_feedback.addWidget(self.solve_summary_details)
        controls.addLayout(solve_feedback)
        self._set_solve_summary("")
        self.panels = PanelTable()
        self.table_view.currentTextChanged.connect(self.panels.show_view)
        self.panels.properties.panelEdited.connect(self._update_panel)
        self.panels.selectionModel().currentRowChanged.connect(self._selection_changed)
        self.recent_list = QListWidget()
        self.recent_list.setAccessibleName("Recent projects")
        self.recent_list.itemActivated.connect(self._open_recent_item)
        self.panel_content = QStackedWidget()
        self.panel_content.addWidget(self.panels)
        self.panel_content.addWidget(self.recent_list)
        controls.addWidget(self.panel_content, 1)
        self.pages.addWidget(self._editor)
        preview = QWidget()
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(0, 2, 0, 0)
        preview_heading = QWidget()
        heading_layout = QHBoxLayout(preview_heading)
        heading_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_title = QLabel("Preview")
        self.preview_title.setProperty("sectionTitle", True)
        heading_layout.addWidget(self.preview_title)
        self.auto_frame_check = QCheckBox("Auto Frame")
        self.auto_frame_check.setToolTip("Fit the preview to the solved sky panels.")
        self.auto_frame_check.toggled.connect(self._set_auto_frame)
        heading_layout.addWidget(self.auto_frame_check)
        self.panel_outlines = QCheckBox("Panel Outlines")
        self.panel_outlines.setToolTip("Show each panel's projected detector boundary.")
        self.panel_outlines.toggled.connect(self._update_outlines)
        preview_header = QHBoxLayout()
        preview_header.addStretch()
        preview_header.addWidget(self.panel_outlines)
        self.band_label = QLabel("Sky band")
        self.band_box = QComboBox()
        self.band_box.setAccessibleName("Sky band")
        self.band_box.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.band_box.setMinimumContentsLength(12)
        self.band_label.setBuddy(self.band_box)
        self.band_box.currentIndexChanged.connect(self._band_changed)
        preview_header.addWidget(self.band_label)
        preview_header.addWidget(self.band_box)
        self.use_preview_grid_button = QPushButton("Use Preview Grid")
        self.use_preview_grid_button.setToolTip(
            "Use this framing as the saved sky grid for export."
        )
        self.use_preview_grid_button.clicked.connect(self._adopt_preview_grid)
        preview_header.addWidget(self.use_preview_grid_button)
        self.exit_focus_button = QPushButton("Exit Focus Mode")
        self.exit_focus_button.clicked.connect(lambda: self.focus_mode_action.setChecked(False))
        self.exit_focus_button.hide()
        heading_layout.addWidget(self.exit_focus_button)
        preview_layout.addWidget(ResponsiveRow(preview_heading, preview_header))
        self.grid_summary = QLabel()
        self.grid_summary.setTextFormat(Qt.TextFormat.PlainText)
        self.grid_summary.setWordWrap(True)
        grid_controls = QHBoxLayout()
        grid_controls.addWidget(self.grid_summary, 1)
        self.edit_crop_button = QPushButton("Edit Crop…")
        self.edit_crop_button.clicked.connect(self._start_crop)
        grid_controls.addWidget(self.edit_crop_button)
        preview_layout.addLayout(grid_controls)
        self.outline_status = QLabel()
        self.outline_status.setTextFormat(Qt.TextFormat.PlainText)
        self.outline_status.setWordWrap(True)
        self.outline_status.hide()
        preview_layout.addWidget(self.outline_status)
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
        self.pages.addWidget(preview)
        self.navigation.itemSelectionChanged.connect(self._switch_workspace)
        self._workspace_focus: dict[int, QWidget] = {}
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        app.focusChanged.connect(self._remember_workspace_focus)

        actions = QHBoxLayout()
        self.settings_button = QPushButton("Mosaic Settings…")
        self.settings_button.clicked.connect(self._settings)
        self.preview_button = QPushButton("Build Preview")
        self.preview_button.clicked.connect(self._preview)
        self.start_button = QPushButton("Export Mosaic…")
        self.start_button.clicked.connect(self._start)
        self._primary_action: QPushButton | None = None
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
        left_actions = QWidget()
        left_layout = QHBoxLayout(left_actions)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.settings_button)
        left_layout.addWidget(self.overlap_check)
        self.show_panels_button = QPushButton("Show Panels")
        self.show_panels_button.clicked.connect(self._show_preview_panel)
        left_layout.addWidget(self.show_panels_button)
        actions.addStretch()
        actions.addWidget(self.layer_box)
        actions.addWidget(self.preview_button)
        actions.addWidget(self.start_button)
        preview_layout.addWidget(ResponsiveRow(left_actions, actions))

        self.progress = QProgressBar()
        self.progress.setObjectName("workspaceProgress")
        self.progress.setAccessibleName("Job progress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setMinimumHeight(24)
        self.progress.setMinimumWidth(90)
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
        self.status.setAccessibleName("Workspace status")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        status_row = QHBoxLayout()
        self.command_toggle = QPushButton("Expand Command Panel")
        self.command_toggle.clicked.connect(self._toggle_command_panel)
        status_row.addWidget(self.command_toggle)
        status_row.addWidget(self.progress_elapsed)
        status_row.addWidget(self.progress, 1)
        status_row.addWidget(self.progress_percent)
        status_row.addWidget(self.cancel_button)
        self._show_job_progress(False)
        layout.addWidget(ResponsiveRow(self.status, status_row))
        self.panels.properties.invalidEdit.connect(self._invalid_panel_edit)
        self._refresh_recent()
        self._refresh()

    def show_workspace(self, screen: QScreen | None = None) -> None:
        self._workspace_restored = True
        self._recent_projects = recent_projects(self._preferences.value(RECENT_KEY))
        self._refresh_recent()
        layout = WorkspaceSettings.read(self._preferences.value(LAYOUT_KEY))
        if layout is None:
            self._default_workspace(screen)
            return
        target = screen or self._screen_named(layout.window.screen) or self.screen()
        self._place_window(layout.window, target)
        area = Qt.DockWidgetArea(layout.area)
        self.addDockWidget(area, self.command_dock)
        self._dock_size = layout.dock_size
        self._command_display = layout.display
        if layout.maximized:
            self.showMaximized()
        else:
            self.showNormal()
            self._place_window(layout.window, target)
        floating = layout.floating
        if floating is not None and (dock_screen := self._screen_named(floating.screen)) is not None:
            work = dock_screen.availableGeometry()
            if work.intersects(floating.rect.translated(work.topLeft())):
                self.command_dock.setFloating(True)
                self.command_dock.setScreen(dock_screen)
                self.command_dock.setGeometry(floating.absolute(work, self.command_dock.minimumSizeHint()))
        self._sync_command_display()

    @staticmethod
    def _screen_named(name: str) -> QScreen | None:
        return next((screen for screen in QApplication.screens() if screen.name() == name), None)

    def _place_window(self, placement: WindowPlacement, target: QScreen) -> None:
        self.setScreen(target)
        handle = self.windowHandle()
        work = target.availableGeometry()
        minimum = self.minimumSizeHint().expandedTo(self.minimumSize())
        rect = placement.absolute(work, minimum, handle.frameMargins()) if handle else placement.absolute(work, minimum)
        self.setGeometry(rect)

    def _default_workspace(self, target: QScreen | None = None) -> None:
        self._command_display = "collapsed"
        self.focus_mode_action.setChecked(False)
        self.navigation.setCurrentRow(_PANELS)
        self.command_dock.setFloating(False)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.command_dock)
        self._sync_command_display()
        self._dock_size = None
        target = target or self.screen()
        work = target.availableGeometry()
        size = QSize(1140, 780).boundedTo(work.size())
        bounds = QRect(0, 0, size.width(), size.height())
        bounds.moveCenter(work.center() - work.topLeft())
        self.setWindowState(Qt.WindowState.WindowNoState)
        self._place_window(WindowPlacement(target.name(), bounds), target)
        self.showMaximized()

    @Slot()
    def _reset_workspace(self) -> None:
        self._preferences.remove(LAYOUT_KEY)
        self._default_workspace()

    def _save_workspace(self) -> None:
        if not self._workspace_restored:
            return
        dock = self.command_dock
        area = self.dockWidgetArea(dock)
        floating = WindowPlacement.capture(dock.geometry(), dock.screen()) if dock.isFloating() else None
        size = self._current_dock_size(area) if dock.isVisible() and floating is None else self._dock_size
        rect = self.normalGeometry()
        placement = WindowPlacement.capture(rect, QApplication.screenAt(rect.center()) or self.screen())
        layout = WorkspaceSettings(placement, self.isMaximized(), self._command_display, area.value, size, floating)
        self._preferences.setValue(LAYOUT_KEY, layout.settings())
        self._preferences.sync()

    @property
    def project(self) -> MosaicProject:
        return self._history.value

    def _commit_project(self, project: MosaicProject, label: str) -> bool:
        if not self._history.commit(project, label):
            return False
        self._revision += 1
        return True

    def _can_navigate_history(self) -> bool:
        return (
            not self._close_after_job
            and not self.command_panel.is_running
            and (self.job is None or isinstance(self.job, PreviewJob))
            and self._preview_state.crop is None
        )

    def _refresh_history_actions(self) -> None:
        available = self._can_navigate_history()
        for action, verb, label in (
            (self.undo_action, "Undo", self._history.undo_label),
            (self.redo_action, "Redo", self._history.redo_label),
        ):
            text = f"&{verb} {label}" if label is not None else f"&{verb}"
            if action is self.undo_action and self._history.limit_reached:
                text = "&Undo (history limit reached)"
            action.setText(text)
            action.setEnabled(available and label is not None)

    @Slot()
    def _undo(self) -> None:
        if self._can_navigate_history() and (label := self._history.undo()) is not None:
            self._refresh_restored_project(f"Undid {label}.")

    @Slot()
    def _redo(self) -> None:
        if self._can_navigate_history() and (label := self._history.redo()) is not None:
            self._refresh_restored_project(f"Redid {label}.")

    def _refresh_restored_project(self, summary: str) -> None:
        self._revision += 1
        self._set_solve_summary("")
        self._invalidate_panel_inspection()
        self._refresh(self.panels.currentIndex().row())
        self._report_operation(summary)

    def _refresh(self, selected: int = -1) -> None:
        if self._solved_panels is not self.project.panels:
            self._solved_panels = ()
            if self._solve_outcomes and not isinstance(self.job, PlateSolveJob):
                self._set_solve_summary("")
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
        with QSignalBlocker(self.panels.selectionModel()):
            self.panels.properties.refresh(rows)
            if 0 <= selected < len(rows):
                self._selected_panel = rows[selected].panel.source.path
            elif all(row.panel.source.path != self._selected_panel for row in rows):
                self._selected_panel = rows[0].panel.source.path if rows else None
            self._refresh_panel_filters()
        self._refresh_project_start()
        linked = all(row.linked for row in rows)
        self._refresh_bands()
        if self._preview_state.is_stale(self._preview_selection(), linked=linked):
            self._clear_preview()
            self._queue_live_preview()
        self._selection_changed()
        name = self.project_path.name if self.project_path else "Untitled"
        marker = "*" if self.project != self._saved else ""
        self.setWindowTitle(f"{name}{marker} — {self._app_title}")
        self.command_panel.set_project_path(self.project_path)
        self._refresh_history_actions()
        self._layer_controls()
        self._start_panel_inspection()
        if self._live_pending and not self._is_running():
            self._preview_timer.start()

    def _refresh_panel_filters(self) -> None:
        last = self.band_filter.currentData()
        bands = {row.values["Band"] for row in self.panels.properties.rows}
        bands.add(last)
        with QSignalBlocker(self.band_filter):
            self.band_filter.clear()
            self.band_filter.addItem("All bands", None)
            for band in sorted(value for value in bands if isinstance(value, str)):
                self.band_filter.addItem(band, band)
            self.band_filter.setCurrentIndex(max(0, self.band_filter.findData(last)))
        self._filter_panels()

    @Slot()
    def _filter_panels(self) -> None:
        name = self.filename_filter.text().strip().casefold()
        band, wcs = self.band_filter.currentData(), self.wcs_filter.currentData()
        rows = self.panels.properties.rows
        self.panel_filters.setVisible(bool(rows))
        visible = 0
        selected = -1
        with QSignalBlocker(self.panels.selectionModel()):
            for index, row in enumerate(rows):
                path = row.panel.source.path
                matches = (
                    name in path.name.casefold() and (band is None or row.values["Band"] == band)
                    and (wcs is None or row.values["WCS"] == wcs)
                )
                self.panels.setRowHidden(index, not matches)
                visible += matches
                if matches and path == self._selected_panel:
                    selected = index
            if selected < 0:
                self.panels.selectionModel().clear()
            elif self.panels.currentIndex().row() != selected:
                self.panels.selectRow(selected)
        active = bool(name) or band is not None or wcs is not None
        count = f"{visible}/{len(rows)}" if active else str(len(rows))
        self.panel_heading.setText(f"Panels ({count})" if rows else "Panels")
        self.clear_filters_button.setEnabled(active)
        self.panels.viewport().update()
        self._selection_changed()

    @Slot()
    def _clear_panel_filters(self) -> None:
        with QSignalBlocker(self.filename_filter), QSignalBlocker(self.band_filter), QSignalBlocker(self.wcs_filter):
            self.filename_filter.clear()
            self.band_filter.setCurrentIndex(0)
            self.wcs_filter.setCurrentIndex(0)
        self._filter_panels()

    def _panel_inspection(self, index: int) -> PanelInspection | None:
        if self._inspected_panels is self.project.panels and 0 <= index < len(self._inspections):
            return self._inspections[index]
        return None

    def _invalidate_panel_inspection(self) -> None:
        if self._inspection_job is not None:
            self._inspection_job.cancel()
        self._inspected_panels, self._inspections = (), ()

    def _start_panel_inspection(self) -> None:
        if self._inspection_job is not None:
            if self._inspection_revision != self._revision:
                self._inspection_job.cancel()
            return
        if (
            not self._close_after_job
            and self.project.panels
            and self.project.panels is not self._inspected_panels
        ):
            job = PanelInspectionJob(self.project, self)
            self._inspection_job = job
            self._inspection_revision = self._revision
            job.finished.connect(self._finish_panel_inspection)
            job.start()

    @Slot()
    def _finish_panel_inspection(self) -> None:
        job, self._inspection_job = self._inspection_job, None
        assert job is not None
        if self._inspection_revision == self._revision and not job.cancellation_requested:
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
        return self._selected_sky_band if self._layer() == "sky" else None

    def _preview_selection(self) -> PreviewSelection:
        return PreviewSelection(self.project, self._layer(), self._sky_band())

    def _refresh_bands(self) -> None:
        bands: dict[str, None] = {}
        for index in self.project.sky_indices():
            info = self._panel_inspection(index)
            if info is not None and info.wcs_status != "Unavailable":
                label = self.project.panels[index].sky_band(
                    info.filter_name, self.project.filter_name
                )
                bands[label] = None
        # A pending inspection temporarily removes metadata for every panel.
        if self._inspected_panels is self.project.panels and self._selected_sky_band not in bands:
            self._selected_sky_band = None
        with QSignalBlocker(self.band_box):
            self.band_box.clear()
            self.band_box.addItem("Select a band" if len(bands) > 1 else "All sky panels")
            for label in bands:
                self.band_box.addItem(label, label)
            self.band_box.setCurrentIndex(max(0, self.band_box.findData(self._selected_sky_band)))

    def _references_ready(self, layer: Layer, band: str | None = None) -> bool:
        rows = self.panels.properties.rows
        if layer != "sky" and any(
            not rows[index].source_linked for index, _ in self.project.foreground_inputs()
        ):
            return False
        if layer != "foreground":
            for index in self.project.sky_indices():
                row = rows[index]
                if not row.source_linked:
                    return False
                if band is not None and row.values["Band"] != band:
                    continue
                if not row.linked or (
                    row.panel.wcs_sidecar is not None and row.values["WCS"] == "Invalid"
                ):
                    return False
        return True

    def _layer_controls(self) -> None:
        draft = self._preview_state.crop
        cropping = draft is not None
        idle = not self._is_running() and not cropping
        layer = self._layer()
        selection = self._preview_selection()
        overview = self._preview_state.current(selection)
        fitted_grid = overview.fitted_grid if overview is not None else None
        frame = self._preview_state.frame
        ground = self.project.current_foreground()
        sky = bool(self.project.sky_indices())
        ground_count = len(self.project.foreground_inputs())
        ground_linked = self._references_ready("foreground")
        self.align_menu.setEnabled(idle and ground_linked and ground_count > 0)
        self.align_action.setEnabled(idle and ground_linked and ground_count > 0)
        self.review_points_action.setEnabled(idle and ground_linked and ground_count > 1)
        if self._foreground_panels is not self.project.panels:
            self._foreground_report = None
            self._foreground_panels = None
        self.foreground_details_action.setEnabled(idle and self._foreground_report is not None)
        self.placement_action.setEnabled(
            idle and ground is not None and sky and self._references_ready("composition")
        )
        self.composition_action.setEnabled(idle and ground is not None and sky)
        self.layer_box.setEnabled(idle and bool(self.project.panels))
        show_band = layer == "sky" and self.band_box.count() > 2
        self.band_label.setVisible(show_band)
        self.band_box.setVisible(show_band)
        self.band_box.setEnabled(idle and show_band)
        self.overlap_check.setVisible(layer == "composition")
        self.overlap_check.setEnabled(frame is not None and frame.common_coverage is not None)
        self.auto_frame_check.setVisible(layer == "sky")
        self.panel_outlines.setVisible(layer == "sky")
        self.auto_frame_check.setEnabled(idle and layer == "sky")
        with QSignalBlocker(self.auto_frame_check):
            self.auto_frame_check.setChecked(self.project.auto_frame_preview)
        can_adopt = layer == "sky" and fitted_grid is not None
        self.use_preview_grid_button.setVisible(can_adopt)
        self.use_preview_grid_button.setEnabled(idle and can_adopt)
        self.edit_crop_button.setVisible(layer == "sky" and not cropping)
        self.edit_crop_button.setEnabled(
            idle and self._preview_state.sky_overview(selection) is not None
        )
        self.crop_controls.setVisible(cropping)
        self.grid_summary.setVisible(not cropping)
        crop_ready = cropping and self.job is None
        self.apply_crop_button.setEnabled(crop_ready and self.viewport.crop is not None)
        self.auto_crop_button.setEnabled(
            crop_ready and draft is not None and draft.suggested is not None
        )
        self.cancel_crop_button.setEnabled(crop_ready)
        spec = self.project.render
        region = spec.output_region()
        ready = False
        if layer == "sky":
            if draft is not None:
                width, height = draft.grid.size
                summary = f"Full sky grid · {width:,} × {height:,} px"
            elif self.project.auto_frame_preview and fitted_grid is None:
                summary = "Fit to solved sky panels"
            else:
                preview_spec = fitted_grid or spec
                ra, dec = preview_spec.center
                framing = preview_spec.output_region()
                summary = (
                    f"ICRS {preview_spec.projection}  ·  RA {ra:.7g}°, Dec {dec:.7g}°"
                    f"  ·  {framing.width} × {framing.height} px"
                    f"  ·  {preview_spec.scale_arcsec:g} arcsec/px"
                )
            band = self._sky_band()
            ready = (
                sky
                and self._inspected_panels is self.project.panels
                and (self.band_box.count() <= 2 or band is not None)
            )
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
        references_ready = self._references_ready(layer, self._sky_band())
        ready = ready and references_ready
        self._preview_needs_panels = not ready
        photo = self._photo_preview_ready()
        self.start_button.setText("Export Photo Mosaic…" if photo else "Export Mosaic…")
        self.start_button.setEnabled(idle and ready)
        self.scientific_export.setEnabled(idle and ready and layer == "sky")
        self.preview_button.setEnabled(idle and ready)
        self.plate_solve_button.setEnabled(idle and sky)
        action = None
        if idle:
            if not self.project.panels:
                action = self.add_button
            elif ready:
                action = self.start_button if frame is not None else self.preview_button
        self._set_primary_action(action)

        if not self.project.panels:
            hint = "In Panels, choose Add Panels… to add linear FITS, TIFF, or XISF files."
        elif isinstance(self.job, PreviewJob):
            hint = "Preparing the preview…"
        elif not idle:
            hint = "Wait for the current operation to finish."
        elif layer == "sky" and not sky:
            hint = "Enable Sky for a panel in the table to build a sky preview."
        elif layer == "sky" and self._inspected_panels is not self.project.panels:
            hint = "Checking panel metadata…"
        elif show_band and self._sky_band() is None:
            hint = "Select a sky band to build a preview."
        elif not references_ready:
            hint = "Check the panel file and WCS links before building a preview."
        elif ready:
            hint = "Choose Build Preview to see the mosaic."
        else:
            hint = summary
        self.viewport.set_empty_hint(hint)
        self._update_outlines()

    def _set_primary_action(self, button: QPushButton | None) -> None:
        previous = self._primary_action
        if previous is button:
            return
        self._primary_action = button
        for action in (previous, button):
            if action is not None:
                action.setProperty("primary", action is button)
                action.style().unpolish(action)
                action.style().polish(action)
                action.update()

    @Slot()
    def _band_changed(self) -> None:
        self._selected_sky_band = cast(str | None, self.band_box.currentData())
        self._layer_changed()

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
        rows = self.panels.properties.rows
        if 0 <= index < len(rows):
            self._selected_panel = rows[index].panel.source.path
        self.viewport.select_outline(self._selected_panel)
        selected = 0 <= index < len(rows) and not self._is_running()
        editable = selected and self._preview_state.crop is None
        source_ready = editable and rows[index].source_linked
        for control in (
            self.relink_action,
            self.panel_button,
            self.remove_action,
        ):
            control.setEnabled(editable)
        self.mask_action.setEnabled(source_ready)
        self.check_foreground.setEnabled(source_ready)
        self.propose_mask.setEnabled(
            source_ready and self.project.panels[index].foreground_tag in ("mixed", "uncertain")
        )
        self.revalidate_solve_action.setEnabled(source_ready and index in self.project.sky_indices())
        info = self._panel_inspection(index)
        self.solve_details_action.setEnabled(
            selected
            and (
                index in self._solve_outcomes
                or (info is not None and info.wcs_status in ("Embedded", "Sidecar"))
            )
        )
        self.solve_summary_details.setEnabled(self.solve_details_action.isEnabled())

    @Slot(object)
    def _select_preview_panel(self, path: Path) -> None:
        self._selected_panel = path
        self._filter_panels()

    @Slot()
    def _show_preview_panel(self) -> None:
        self.navigation.setCurrentRow(_PANELS)
        index = self.panels.currentIndex()
        if index.isValid():
            self.panels.scrollTo(index)
            self.panels.setFocus()
        elif self._selected_panel is not None and self.clear_filters_button.isEnabled():
            self.status.setText("The selected panel is hidden. Choose Clear Filters to reveal it.")
            self.clear_filters_button.setFocus()

    @Slot()
    def _update_outlines(self) -> None:
        if not hasattr(self, "show_panels_button"):
            return
        selection = self._preview_selection()
        visible = self.panel_outlines.isChecked() and selection.layer == "sky"
        self.viewport.show_outlines(visible)
        overview = self._preview_state.current(selection)
        missing = [f"{item.source.name}: {item.reason}" for item in overview.outlines
                   if item.reason] if visible and overview else []
        self.outline_status.setText(missing[0] if missing else "")
        self.outline_status.setToolTip("\n".join(missing))
        self.outline_status.setVisible(bool(missing))
        self.show_panels_button.setText("Show in Panels" if visible else "Show Panels")
        self.show_panels_button.setVisible(
            (visible or self._preview_needs_panels) and self._preview_state.crop is None
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
        self._solved_panels = ()
        self._solve_outcomes.clear()
        self._selected_panel = None
        self._set_solve_summary("")
        self._selected_sky_band = None
        self._invalidate_panel_inspection()
        self._history = EditHistory(project)
        self._revision += 1
        self._saved = project
        self.project_path = path
        self.progress.setValue(0)
        self._show_job_progress(False)
        self._refresh()
        self._clear_panel_filters()

    def _new(self) -> None:
        if self._confirm_discard():
            self._new_project()

    def _new_project(self) -> None:
        self.navigation.setCurrentRow(_PANELS)
        self._set_project(MosaicProject(auto_frame_preview=True), None)
        self._report_operation("New project.")

    def _open(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, "Open Project", "", _PROJECT_FILTER)
        if not name:
            return
        self._open_from_desktop(Path(name))

    def _open_from_desktop(self, path: Path) -> None:
        try:
            self._open_project(path, confirm_discard=True)
        except (OSError, ValueError) as error:
            self._error("Open failed", error)

    def _open_project(self, path: Path, *, confirm_discard: bool = False) -> None:
        project = load_project(path)
        if confirm_discard:
            saved = self._saved
            if not self._confirm_discard():
                return
            if (
                saved is not self._saved
                and self.project_path is not None
                and self.project_path.resolve() == path.resolve()
            ):
                # The discard prompt saved this file after we loaded it.
                project = self._saved
        self._set_project(project, path)
        self._remember_recent(path)
        self._report_operation(f"Opened {path.name}.")

    def _refresh_project_start(self) -> None:
        empty = self.project_path is None and not self.project.panels
        self.open_button.setVisible(empty)
        self.panel_content.setCurrentWidget(self.recent_list if empty and self._recent_projects else self.panels)

    def _set_recent(self, projects: tuple[Path, ...]) -> None:
        if not self._workspace_restored:
            return
        self._recent_projects = recent_projects([str(path) for path in projects])
        self._preferences.setValue(RECENT_KEY, [str(path) for path in self._recent_projects])
        self._refresh_recent()

    def _remember_recent(self, path: Path) -> None:
        self._set_recent((path.absolute(), *self._recent_projects))

    def _refresh_recent(self) -> None:
        self.recent_menu.clear()
        self.recent_list.clear()
        for path in self._recent_projects:
            label = f"{path.name} — {path.parent}"
            item = QListWidgetItem(label)
            item.setToolTip(str(path))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.recent_list.addItem(item)
            action = self.recent_menu.addAction(label.replace("&", "&&"))
            action.setToolTip(str(path))
            action.triggered.connect(lambda _checked=False, path=path: self._open_from_desktop(path))
        if self._recent_projects:
            self.recent_menu.addSeparator()
            self.recent_menu.addAction("Remove Unavailable Projects", self._remove_unavailable_recents)
            self.recent_menu.addAction("Clear Recent Projects", lambda: self._set_recent(()))
        else:
            self.recent_menu.addAction("No recent projects").setEnabled(False)
        self._refresh_project_start()

    @Slot(QListWidgetItem)
    def _open_recent_item(self, item: QListWidgetItem) -> None:
        self._open_from_desktop(Path(item.data(Qt.ItemDataRole.UserRole)))

    @Slot()
    def _remove_unavailable_recents(self) -> None:
        available = tuple(path for path in self._recent_projects if path.is_file())
        removed = len(self._recent_projects) - len(available)
        self._set_recent(available)
        self._report_operation(f"Removed {removed} unavailable recent project(s).")

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
        self._remember_recent(path)
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
        self._add_sources(tuple(FileReference.capture(path) for path in paths))

    def _add_sources(self, sources: tuple[FileReference, ...]) -> None:
        known = {panel.source.path for panel in self.project.panels}
        additions = []
        for source in sources:
            if source.path not in known:
                additions.append(ProjectPanel(source))
                known.add(source.path)
        start = len(self.project.panels)
        added = self._commit_project(
            replace(self.project, panels=self.project.panels + tuple(additions)), "Add Panels"
        )
        self._refresh(start)
        if added:
            count = len(sources) - len(additions)
            skipped = f" Skipped {count} duplicate panel(s)." if count else ""
            self._report_operation(f"Added {len(additions)} panel(s).{skipped}")
            indices = tuple(range(start, len(self.project.panels)))
            self._launch_job(
                ForegroundJob(self.project, indices, self, after_add=True), "Checking foreground…"
            )
        else:
            self._report_operation("Panels already added.")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if not event.mimeData().hasUrls() or not event.possibleActions() & Qt.DropAction.CopyAction:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if not urls or not event.possibleActions() & Qt.DropAction.CopyAction:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        if self._is_running() or self._close_after_job or self._preview_state.crop is not None:
            self._report_operation("Finish or cancel the current operation before dropping files.")
            return
        if any(not url.isLocalFile() for url in urls):
            self._report_operation("Drop local project or panel files.")
            return
        paths = tuple(Path(url.toLocalFile()) for url in urls)
        suffixes = {path.suffix.casefold() for path in paths}
        if suffixes == {".astromosaic"} and len(paths) == 1:
            self._open_from_desktop(paths[0])
        elif ".astromosaic" in suffixes:
            self._report_operation("Drop one project by itself or a group of panel files.")
        elif suffixes <= _PANEL_SUFFIXES:
            self._launch_job(PanelIntakeJob(paths, self), "Checking dropped panel files…")
        else:
            self._report_operation("Drop an AstroMosaic project or FITS, TIFF or XISF panels.")

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
        if not self._commit_project(self.project.relink_panel(index, path), "Relink Panel"):
            self._invalidate_panel_inspection()
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
                    if not self._references_ready(self._layer(), self._sky_band()):
                        raise ValueError("Check the panel Link and WCS columns before building a preview.")
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
                    if not self._references_ready(layer, band if layer == "sky" else None):
                        raise ValueError("Check the panel Link and WCS columns before exporting.")
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
        self._commit_project(
            replace(self.project, panels=panels[:index] + panels[index + 1 :]), "Remove Panel"
        )
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

    def _update_panel(
        self,
        index: int,
        panel: ProjectPanel,
        *,
        summary: str | None = None,
        label: str = "Change Panel Settings",
    ) -> None:
        panels = self.project.panels
        previous = panels[index]
        if not self._commit_project(
            replace(self.project, panels=panels[:index] + (panel,) + panels[index + 1 :]), label
        ):
            return
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
        overview = self._preview_state.current(self._preview_selection())
        dialog = ProjectSettings(
            self.project,
            self,
            preview_grid=overview.fitted_grid if overview is not None else None,
            suggested_rotation=overview.suggested_rotation if overview is not None else None,
            input_metadata=", ".join(sorted(inputs)),
        )
        try:
            while dialog.exec():
                try:
                    previous = self.project
                    settings = dialog.settings()
                except (OSError, ValueError, OverflowError) as error:
                    self._error("Invalid mosaic settings", error)
                    continue
                self._commit_project(settings, "Change Mosaic Settings")
                self._refresh(self.panels.currentIndex().row())
                summary = "Mosaic settings applied."
                if previous.composition is not None and self.project.composition is None:
                    summary += " Set the composition placement for the new sky grid."
                self._report_operation(summary)
                break
        finally:
            dialog.deleteLater()

    def _gpu_acceleration_preference(self) -> bool:
        return bool(self._preferences.value(_GPU_ACCELERATION_SETTING, True, type=bool))

    def _gpu_settings(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("GPU Acceleration")
        dialog.setMinimumWidth(370)
        layout = QVBoxLayout(dialog)
        enabled = QCheckBox("Enable GPU acceleration for previews")
        enabled.setChecked(self._gpu_acceleration_preference())
        enabled.setEnabled(self._allow_gpu_preview)
        layout.addWidget(enabled)
        help_text = QLabel(
            "AstroMosaic uses the CPU automatically when GPU acceleration is unavailable."
            if self._allow_gpu_preview else "CPU preview is forced for this session by --cpu-preview."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted and self._allow_gpu_preview:
                requested = enabled.isChecked()
                if requested != self._use_gpu_preview:
                    self._preferences.setValue(_GPU_ACCELERATION_SETTING, requested)
                    self._use_gpu_preview = requested
                    if self._detail_job is not None:
                        self._detail_job.cancel()
                    self.viewport.set_gpu_enabled(requested)
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
        self._set_solve_summary("Checking WCS eligibility…")
        job.batch_progress.connect(self._plate_solve_batch_progress)
        message = "Preparing plate solve for sky panels that need a WCS…"
        if selected_panel is not None:
            name = self.project.panels[selected_panel].source.path.name
            message = f"Revalidating plate solution for {name}…"
        self._launch_job(job, message)

    @Slot(str)
    def _plate_solve_batch_progress(self, text: str) -> None:
        if self.sender() is self.job and self.cancel_button.isEnabled():
            self._set_solve_summary(text)

    def _set_solve_summary(self, text: str) -> None:
        self.solve_summary.setText(text)
        self.solve_summary.setVisible(bool(text))
        self.solve_summary_details.setVisible(bool(text))

    def _photo_preview_ready(self) -> bool:
        return self._preview_state.photo_overview(self._preview_selection()) is not None

    def _start(self) -> None:
        self._choose_export_path(photo=self._photo_preview_ready())

    def _start_scientific(self) -> None:
        self._choose_export_path(photo=False)

    def _choose_export_path(self, *, photo: bool) -> None:
        if self._is_running() or not self.project.panels:
            return
        request = self._export_request(photo=photo)
        if request is None:
            self._report_operation("Build a covered sRGB sky preview before exporting a photo.")
            return
        self._launch_job(ExportReviewJob(request, self), "Checking export settings…")

    def _export_request(self, *, photo: bool) -> ExportRequest | None:
        selection = self._preview_selection()
        if not photo:
            return ExportRequest(selection.project, selection.layer, selection.band)
        overview = self._preview_state.photo_overview(selection)
        if overview is None:
            return None
        return ExportRequest(selection.project, selection.layer, selection.band,
                             overview.grid, self.viewport.photo_tone())

    def _confirm_export_review(self, description: ExportDescription) -> OutputFormat | None:
        dialog = ExportReview(description, self)
        try:
            return dialog.output if dialog.exec() else None
        finally:
            dialog.deleteLater()

    def _finish_export_review(self, job: ExportReviewJob) -> None:
        if job.cancellation_requested or self._close_after_job:
            self._report_operation("Export review cancelled.")
            return
        if job.result is None:
            self._report_render_failure("Export review failed.", job)
            return
        revision = self._revision
        photo = job.request.photo_grid is not None
        output = self._confirm_export_review(job.result)
        if output is None:
            self._report_operation("Export review cancelled.")
            return
        name, _ = QFileDialog.getSaveFileName(
            self, "Export Photo Mosaic" if photo else "Render Mosaic", "", output.file_filter,
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not name:
            self._report_operation("Export destination selection cancelled.")
            return
        if revision != self._revision or job.request != self._export_request(photo=photo):
            self._report_operation("Export settings changed. Review the export again.")
            return
        try:
            path = output.destination(Path(name))
        except ValueError as error:
            self._report_operation("Invalid export destination.", detail=str(error))
            return
        if photo:
            self._export_photo_to(path)
        else:
            self._export_to(path, job.request.layer, job.request.band)

    def _export_photo_to(self, path: Path) -> None:
        overview = self._preview_state.photo_overview(self._preview_selection())
        if overview is None:
            raise ValueError("Build a covered sRGB sky preview before exporting a photo.")
        self._launch_job(
            MosaicJob(
                overview.selection.project,
                path,
                self,
                band=overview.selection.band,
                photo_grid=overview.grid,
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
        self._preview_state.clear()
        if isinstance(self.job, PreviewJob):
            self.job.cancel()
        self._clear_preview_view()

    def _clear_preview_view(self) -> None:
        self._detail_timer.stop()
        if self._detail_job is not None:
            self._detail_job.cancel()
        self.preview_title.setText("Preview")
        self.overlap_check.setEnabled(False)
        self.viewport.set_crop(None)
        self.viewport.set_frame(None)
        self.viewport.set_outlines(())
        self._update_outlines()

    @Slot(bool)
    def _toggle_live_preview(self, enabled: bool) -> None:
        if enabled and self._preview_state.current(self._preview_selection()) is None:
            self._queue_live_preview()
        elif not enabled:
            self._preview_timer.stop()
            self._adaptive_timer.stop()
            self._live_pending = False

    def _queue_live_preview(self) -> None:
        if self._live_ready and self.live_preview_action.isChecked() and self._layer() == "sky":
            self._live_pending = True
            self._preview_timer.start()

    @Slot()
    def _live_preview(self) -> None:
        if not self._live_pending or self._close_after_job or self._preview_state.crop is not None:
            return
        if self._is_running() or self._inspection_job is not None or QApplication.activeModalWidget():
            self._preview_timer.start()
            return
        selected = self._sky_band()
        if self._layer() != "sky" or (self.band_box.count() > 2 and selected is None):
            return
        if not self._references_ready("sky", selected):
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
            self._start_preview()

    @Slot()
    def _view_changed(self) -> None:
        if self.pages.currentIndex() != _PREVIEW:
            return
        overview = self._preview_state.current(self._preview_selection())
        if (
            overview is None or self.viewport.frame is None
            or self.job is not None or self._close_after_job
        ):
            return
        edge = self.viewport.overview_edge()
        if (
            self.live_preview_action.isChecked()
            and self._preview_state.crop is None
            and overview.selection.layer == "sky"
            and self.viewport.visible_detail() is None
            and overview.overview_edge
            and abs(edge - overview.overview_edge) >= 256
        ):
            self._adaptive_timer.start()
        else:
            self._adaptive_timer.stop()
        self._detail_timer.start()

    @Slot()
    def _refresh_adaptive_preview(self) -> None:
        if (self.pages.currentIndex() != _PREVIEW or self._is_running() or self._close_after_job
            or QApplication.activeModalWidget() is not None):
            return
        selection = self._preview_selection()
        edge = self.viewport.overview_edge()
        overview = self._preview_state.current(selection)
        if (
            overview is None
            or self._preview_state.crop is not None
            or self.viewport.visible_detail() is not None
            or abs(edge - overview.overview_edge) < 256
        ):
            return
        request = self._preview_state.start_adaptive(overview)
        job = PreviewJob(
            request, self, adaptive_edge=edge, resolution_scale=self.viewport.resolution_scale(),
            use_gpu=self._use_gpu_preview,
        )
        self._launch_job(job, "Updating the preview for this window size…")

    @Slot()
    def _request_detail(self) -> None:
        if self.pages.currentIndex() != _PREVIEW:
            return
        window = self.viewport.visible_detail()
        if window is None:
            self.viewport.clear_detail()
            if self._detail_job is not None:
                self._detail_job.cancel()
            return
        overview = self._preview_state.current(self._preview_selection())
        if (
            overview is None or overview.frame.tone_levels is None
            or self._is_running() or self._close_after_job
        ):
            return
        if self.viewport.detail is not None and self.viewport.detail.contains(window):
            return
        if self._detail_job is not None:
            if not self._detail_job.window.contains(window):
                self._detail_job.cancel()
            return
        padded = window.with_halo(*overview.frame.output_size, 48)
        if padded.width * padded.height <= MAX_DETAIL_PIXELS:
            window = padded
        job = self._detail_job = PreviewDetailJob(
            overview, self, window, use_gpu=self._use_gpu_preview
        )
        self._detail_revision = self._revision
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
            self._detail_revision == self._revision
            and self._preview_state.current(self._preview_selection()) is job.overview
        ):
            if (
                not job.cancellation_requested
                and job.result is not None and job.window.contains(request)
            ):
                self.viewport.set_detail(job.window, job.result)
            elif job.error is None:
                self._detail_timer.start()
        job.deleteLater()
        self._finish_close_if_ready()

    @Slot(bool)
    def _set_auto_frame(self, enabled: bool) -> None:
        if enabled != self.project.auto_frame_preview:
            self._commit_project(
                replace(self.project, auto_frame_preview=enabled), "Change Sky Framing"
            )
            self._refresh(self.panels.currentIndex().row())

    @Slot()
    def _adopt_preview_grid(self) -> None:
        overview = self._preview_state.sky_overview(self._preview_selection())
        grid = overview.fitted_grid if overview is not None else None
        if self._is_running() or grid is None:
            raise ValueError("Build an automatically framed sky preview first.")
        previous = self.project
        composition = previous.composition if grid == previous.render else None
        self._commit_project(
            replace(previous, render=grid, auto_frame_preview=False, composition=composition),
            "Use Preview Grid",
        )
        self._preview_state.adopt_grid(self.project)
        self._refresh(self.panels.currentIndex().row())
        text = "Applied the preview grid to the sky export settings."
        if previous.composition is not None and composition is None:
            text += " Set the composition placement for the new sky grid."
        self._report_operation(text)

    @Slot()
    def _resolution_changed(self) -> None:
        if (
            not self._close_after_job and self._preview_state.crop is None
            and self._preview_state.current(self._preview_selection()) is not None
        ):
            self._preview()

    def _preview(self) -> None:
        if self._is_running() or not self.project.panels:
            return
        self.navigation.setCurrentRow(_PREVIEW)
        self._start_preview()

    def _start_preview(self) -> None:
        if self._is_running() or not self.project.panels:
            return
        edge = self.viewport.overview_edge()
        selection = self._preview_selection()
        request = self._preview_state.start(selection)
        self._clear_preview_view()
        self._live_pending = False
        self._preview_timer.stop()
        layer = selection.layer
        self._live_ready = self._live_ready or layer == "sky"
        job = PreviewJob(
            request, self, adaptive_edge=edge, resolution_scale=self.viewport.resolution_scale(),
            use_gpu=self._use_gpu_preview,
        )
        job.proxy_ready.connect(self._show_proxy)
        self._launch_job(job, f"Preparing {layer} preview…")

    @Slot()
    def _start_crop(self) -> None:
        if self._is_running():
            return
        request = self._preview_state.start_crop(self._preview_selection())
        if request is None:
            return
        draft = self._preview_state.crop
        assert draft is not None
        self._clear_preview_view()
        self._show_crop_bounds(draft.grid.output_region())
        job = PreviewJob(
            request, self, adaptive_edge=self.viewport.overview_edge(),
            resolution_scale=self.viewport.resolution_scale(), use_gpu=self._use_gpu_preview,
        )
        job.proxy_ready.connect(self._show_proxy)
        self._launch_job(job, "Preparing the full sky grid for crop editing…")

    @Slot(object)
    def _show_crop_bounds(self, crop: Region) -> None:
        draft = self._preview_state.crop
        if draft is not None:
            width, height = draft.grid.size
            self.crop_bounds.setText(
                f"Crop {crop.x}, {crop.y} · {crop.width} × {crop.height} / {width} × {height} px"
            )

    @Slot()
    def _reset_crop(self) -> None:
        draft = self._preview_state.crop
        if draft is not None and (crop := draft.suggested) is not None:
            self.viewport.set_crop(crop, editing=True)
            self._show_crop_bounds(crop)

    @Slot()
    def _apply_crop(self) -> None:
        crop = self.viewport.crop
        if self._is_running() or crop is None:
            return
        grid = self._preview_state.grid_for_crop(self._preview_selection(), crop)
        if grid is None:
            return
        previous = self.project
        self._commit_project(
            replace(
                previous, render=grid, auto_frame_preview=False,
                frame_locks=previous.frame_locks | {"crop"},
                composition=previous.composition if grid == previous.render else None,
            ),
            "Apply Crop",
        )
        self._clear_preview()
        self._refresh(self.panels.currentIndex().row())
        self._preview()

    @Slot()
    def _restore_crop_preview(self) -> None:
        if self._preview_state.crop is None:
            return
        overview = self._preview_state.restore_crop(self._preview_selection())
        self._clear_preview_view()
        if overview is not None:
            self.preview_title.setText("Visual Preview" if overview.visual_only else "Preview")
            self._update_preview_view()
        self._set_running()
        if self.pages.currentIndex() == _PREVIEW and self.edit_crop_button.isEnabled():
            self.edit_crop_button.setFocus()
        self._report_operation("Crop changes discarded.")

    @Slot(object, bool)
    def _show_proxy(self, frame: DisplayFrame, visual_only: bool) -> None:
        job = self.job
        if (
            isinstance(job, PreviewJob) and self.sender() is job
            and self._job_revision == self._revision and not job.cancellation_requested
            and self._preview_state.show_proxy(job.request, self._preview_selection(), frame)
        ):
            self.preview_title.setText("Visual Preview" if visual_only else "Preview")
            self._update_preview_view()

    def _update_preview_view(self) -> None:
        frame = self._preview_state.frame
        assert frame is not None
        self.overlap_check.setEnabled(frame.common_coverage is not None)
        self._paint_display()
        overview = self._preview_state.current(self._preview_selection())
        self.viewport.set_outlines(overview.outlines if overview is not None else ())
        self._update_outlines()
        if self._layer() == "sky":
            draft = self._preview_state.crop
            crop = Region(0, 0, *frame.output_size) if draft is None else draft.grid.output_region()
            self.viewport.set_crop(crop, editing=draft is not None and self.job is None)

    @Slot()
    def _paint_display(self) -> None:
        frame = self._preview_state.frame
        if frame is not None:
            self.viewport.set_frame(frame, highlight_common=self.overlap_check.isChecked())

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
            self._commit_project(dialog.aligned_project, "Apply Terrain Alignment")
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
                self._commit_project(
                    replace(self.project, composition=composition), "Change Composition Settings"
                )
                self._refresh(self.panels.currentIndex().row())
                self.layer_box.setCurrentIndex(_LAYERS.index("composition"))
                self._report_operation("Composition settings applied.")
                break
        finally:
            dialog.deleteLater()

    def _launch_job(self, job: _Job, message: str) -> None:
        self._adaptive_timer.stop()
        self._detail_timer.stop()
        self.job = job
        self._job_revision = self._revision
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

    @Slot(QWidget, QWidget)
    def _remember_workspace_focus(self, previous: QWidget | None, current: QWidget | None) -> None:
        if current is None or not isValid(self.pages):
            return
        page = self.pages.currentWidget()
        if page is not None and page.isAncestorOf(current):
            self._workspace_focus[self.pages.currentIndex()] = current

    def _focus_workspace(self, reason: Qt.FocusReason = Qt.FocusReason.OtherFocusReason) -> bool:
        index = self.pages.currentIndex()
        remembered = self._workspace_focus.get(index)
        default: QWidget = self.add_button if not self.project.panels else self.panels
        alternatives: tuple[QWidget, ...]
        if index == _PREVIEW:
            default = self.auto_frame_check
            alternatives = (self.layer_box, self.viewport.fit_button, self.exit_focus_button)
        else:
            alternatives = (self.add_button,)
        targets = (remembered, default, *alternatives)
        for target in targets:
            if (
                target is not None and isValid(target) and target.isVisibleTo(self)
                and target.isEnabled() and target.focusPolicy() != Qt.FocusPolicy.NoFocus
            ):
                target.setFocus(reason)
                return True
        return False

    def focusNextPrevChild(self, next: bool) -> bool:
        if (
            next and self.focusWidget() is self.navigation
            and self._focus_workspace(Qt.FocusReason.TabFocusReason)
        ):
            return True
        return super().focusNextPrevChild(next)

    @Slot()
    def _switch_workspace(self) -> None:
        selected = self.navigation.selectedIndexes()
        if not selected:
            return
        index = selected[0].row()
        if index == self.pages.currentIndex():
            return
        self.navigation.setCurrentRow(index)
        remembered = self._workspace_focus.get(index)
        self.pages.setCurrentIndex(index)
        if remembered is not None and isValid(remembered):
            self._workspace_focus[index] = remembered
        if index == _PANELS:
            self.focus_mode_action.setChecked(False)
            self._adaptive_timer.stop()
            self._detail_timer.stop()
        else:
            QTimer.singleShot(0, self._view_changed)
        self.focus_mode_action.setEnabled(index == _PREVIEW)
        self.navigation.setFocus()

    @Slot(bool)
    def _set_preview_focus_mode(self, active: bool) -> None:
        focused = self.focusWidget()
        restore_focus = focused is self.exit_focus_button or (active and focused is self.command_toggle) or (
            focused is not None and self.command_dock.isAncestorOf(focused)
        )
        self.exit_focus_button.setVisible(active)
        self._sync_command_display()
        if restore_focus and not self._focus_workspace():
            self.navigation.setFocus()

    @Slot()
    def _toggle_command_panel(self) -> None:
        if self._command_display == "expanded":
            self._command_display = "collapsed"
            self._sync_command_display()
        else:
            self._show_command_panel(True)

    @Slot(bool)
    def _show_command_panel(self, visible: bool) -> None:
        focused = self.focusWidget()
        restore_focus = not visible and focused is not None and (
            self.command_dock.isAncestorOf(focused) or focused is self.command_toggle
        )
        self._command_display = "expanded" if visible else "hidden"
        if visible:
            self.focus_mode_action.setChecked(False)
        self._sync_command_display()
        if visible and self.command_panel.entry.isEnabled():
            self.command_panel.entry.setFocus()
        elif restore_focus and not self._focus_workspace():
            self.navigation.setFocus()

    def _sync_command_display(self) -> None:
        display = "hidden" if self.focus_mode_action.isChecked() else self._command_display
        expand = display == "expanded"
        was_hidden = self.command_dock.isHidden()
        area = self.dockWidgetArea(self.command_dock)
        if not expand and not was_hidden and not self.command_dock.isFloating():
            self._dock_size = self._current_dock_size(area)
        self.command_dock.setVisible(expand)
        if expand and was_hidden and not self.command_dock.isFloating():
            output_height = self.command_panel.output.minimumSizeHint().height()
            transcript_height = 68 if self.height() < 720 else 100
            dock_height = self.command_dock.minimumSizeHint().height() + max(
                0, transcript_height - output_height
            )
            self.resizeDocks([self.command_dock], [self._dock_size or dock_height], self._dock_orientation(area))
        self.command_toggle.setText("Collapse Command Panel" if expand else "Expand Command Panel")
        self.command_toggle.setVisible(display != "hidden")
        with QSignalBlocker(self.command_panel_action):
            self.command_panel_action.setChecked(display != "hidden")

    @staticmethod
    def _dock_orientation(area: Qt.DockWidgetArea) -> Qt.Orientation:
        sides = (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea)
        return Qt.Orientation.Horizontal if area in sides else Qt.Orientation.Vertical

    def _current_dock_size(self, area: Qt.DockWidgetArea) -> int:
        if self._dock_orientation(area) == Qt.Orientation.Horizontal:
            return self.command_dock.width()
        return self.command_dock.height()

    @Slot()
    def _command_running_changed(self) -> None:
        if self.command_panel.is_running and self._detail_job is not None:
            self._detail_job.cancel()
        self._set_running()
        self._finish_close_if_ready()

    @Slot()
    def _command_feedback(self) -> None:
        if self.job is not None:
            return
        panel = self.command_panel
        self.status.setText(panel.status.text())
        self.cancel_button.setEnabled(panel.cancel_button.isEnabled())
        if panel.is_running:
            self.progress.setRange(0, panel.progress.maximum())
            self.progress.setValue(panel.progress.value())
            self._show_job_progress(True)
            self.progress_percent.setVisible(panel.progress.maximum() > 0)

    def _set_running(self) -> None:
        running = self._is_running()
        can_edit = not running and self._preview_state.crop is None
        self._show_job_progress(running, timed=isinstance(self.job, PlateSolveJob))
        self.cancel_button.setVisible(running)
        if self.command_panel.is_running:
            self._command_feedback()
        else:
            self.progress.setRange(0, 100)
            self.cancel_button.setEnabled(
                self.job is not None and not self.job.cancellation_requested
            )
        for action in self._file_actions:
            action.setEnabled(can_edit)
        self.recent_menu.setEnabled(can_edit)
        self.plate_solve_settings_action.setEnabled(can_edit)
        self.gpu_settings_action.setEnabled(can_edit)
        self.viewport.resolution_box.setEnabled(can_edit)
        self._editor.setEnabled(can_edit)
        self.settings_button.setEnabled(can_edit)
        self._layer_controls()
        self.command_panel.set_available(self.job is None and self._preview_state.crop is None)
        self._refresh_history_actions()
        self._selection_changed()

    @Slot(object, object)
    def _progress(self, done: int, total: int) -> None:
        job = self.job
        if self._job_revision != self._revision:
            return
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
        if self._job_revision != self._revision:
            if isinstance(job, PlateSolveJob):
                self._solve_timer.stop()
            self._refresh(self.panels.currentIndex().row())
        elif isinstance(job, PreviewJob):
            self._finish_preview(job)
        elif isinstance(job, ExportReviewJob):
            self._finish_export_review(job)
        elif isinstance(job, PanelIntakeJob):
            if job.result is not None and not job.cancellation_requested:
                self.navigation.setCurrentRow(_PANELS)
                self._add_sources(job.result)
            elif job.cancellation_requested:
                self._report_operation("Panel intake cancelled.")
            else:
                self._report_operation("Could not add dropped panels.", detail=job.error or "Unknown error.")
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
            self._commit_project(
                replace(self.project, panels=tuple(panels)), "Apply Plate Solve"
            )
        self._solved_panels = self.project.panels
        self._solve_outcomes = {outcome.index: outcome for outcome in job.outcomes}
        self._refresh(self.panels.currentIndex().row())
        completed = len(job.outcomes)
        if not job.cancelled and job.error is None:
            self.progress.setValue(100)
        summary = f"{solved} solved, {completed - solved} failed."
        mask_needed = any(
            outcome.error and "Apply a sky mask or mark the panel Sky only" in outcome.error
            for outcome in job.outcomes
        )
        guidance = " Apply a sky mask to affected panels." if mask_needed else ""
        terminal = "Cancelled. " if job.cancelled else f"Stopped. {job.error} " if job.error else ""
        self._set_solve_summary(terminal + job.summary() + guidance)
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
            self._report_operation(f"Plate solve finished. {summary}{guidance}")
        self._set_solve_elapsed(job.elapsed_seconds)
        self._show_job_progress(True, timed=True)

    def _finish_preview(self, job: PreviewJob) -> None:
        request = job.request
        selection = self._preview_selection()
        result = job.result
        if result is None or job.cancellation_requested:
            if not self._preview_state.accepts(request, selection):
                return
            if request.adaptive_from is not None:
                self._preview_state.finish_adaptive()
                if job.cancellation_requested:
                    self._report_operation("Preview update cancelled.")
                else:
                    self._report_render_failure("Preview update failed.", job)
                return
            if request.crop_grid is not None:
                self._restore_crop_preview()
                if job.cancellation_requested:
                    self._report_operation("Crop preview cancelled.")
                else:
                    self._report_render_failure("Crop preview failed.", job)
                return
            self._clear_preview()
            self.progress.setValue(0)
            if job.cancellation_requested:
                self._report_operation("Preview cancelled.")
            else:
                self._report_render_failure("Preview failed.", job)
                self._refresh(self.panels.currentIndex().row())
            return

        overview = self._preview_state.complete(request, selection, result)
        if overview is None:
            return
        if request.crop_grid is not None:
            self.preview_title.setText("Crop Preview")
            self._update_preview_view()
            self._set_running()
            if self.pages.currentIndex() == _PREVIEW:
                self.viewport.focus_crop()
            self._report_operation(
                "Arrows move the crop. Shift+arrows resize. Ctrl+arrows pan. Esc cancels."
            )
            return

        self.preview_title.setText("Visual Preview" if overview.visual_only else "Preview")
        self._update_preview_view()
        self._layer_controls()
        self.progress.setValue(100)
        frame = overview.frame
        width, height = frame.size
        layer = overview.selection.layer
        label = "Visual sky preview (sRGB)" if overview.visual_only else f"{layer.capitalize()} preview"
        text = (
            f"{label} · {width} × {height} samples."
            if frame.has_coverage
            else "No coverage at this preview resolution."
        )
        if layer == "sky" and frame.has_coverage:
            text += " OpenGL GPU sampling." if job.gpu_sampled else " CPU sampling."
        if layer == "sky" and not frame.has_coverage:
            if job.project.auto_frame_preview:
                text += " Try a smaller selection or choose a sky grid in Mosaic Settings."
            else:
                text += " Enable Auto Frame or choose a grid that covers the sky panels."
        if frame.common_coverage is not None:
            text += f" Both layers cover {int(frame.common_coverage.sum()):,} preview samples."
        self._report_operation(text)
        if result.photo is not None:
            for line in result.photo.lines():
                self.command_panel.append_summary(line)
        self._view_changed()

    def _finish_layer_job(self, job: ForegroundAlignmentJob | CompositionProposalJob) -> None:
        details = ""
        if isinstance(job, ForegroundAlignmentJob):
            self._foreground_report = job.report()
            self._foreground_panels = job.project.panels
            self._layer_controls()
            if self._foreground_report is not None:
                details = " See Layers → Foreground Alignment Details."
        if job.result is None or job.cancellation_requested:
            self.progress.setValue(0)
            label = job.label.capitalize()
            if job.cancellation_requested:
                self._report_operation(f"{label} cancelled.")
            else:
                self._report_operation(
                    f"{label} failed.", detail=(job.error or "No result was returned.") + details
                )
            return
        if isinstance(job, ForegroundAlignmentJob):
            self._commit_project(job.result, "Align Foreground")
            assert self.project.foreground is not None
            alignment = self.project.foreground.alignment
            layer = "foreground"
            message = f"Aligned {len(alignment.panels)} foreground panel(s) across {len(alignment.overlaps)} overlap(s)."
        else:
            placement = job.result
            self._commit_project(
                replace(self.project, composition=placement), "Apply Placement Proposal"
            )
            assert placement.reference_panel is not None and placement.placement_rms_px is not None
            layer = "composition"
            message = f"Placement from panel {placement.reference_panel + 1} · {placement.placement_rms_px:.2f} px RMS."
        self._refresh(self.panels.currentIndex().row())
        self.layer_box.setCurrentIndex(_LAYERS.index(layer))
        self.progress.setValue(100)
        self._report_operation(message + details)

    def _finish_foreground_check(self, job: ForegroundJob) -> None:
        if job.result is None or job.cancellation_requested:
            self._mask_job_status(job)
            return
        project, problems = job.result
        if job.after_add:
            if self._history.complete_edit(job.project, project):
                self._revision += 1
        else:
            self._commit_project(project, "Check Foreground")
        self._refresh(self.panels.currentIndex().row())
        self.progress.setValue(100)
        if problems:
            self._report_operation(
                f"Foreground check failed for {len(problems)} panel(s).", detail=problems[0]
            )
        else:
            self._report_operation(f"Checked {len(job.indices)} panel(s) for foreground.")

    def _finish_mask_editor(self, job: MaskEditorJob) -> None:
        if job.result is None or job.cancellation_requested:
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
        revision = self._revision
        try:
            accepted = dialog.exec()
            mask = dialog.result_mask
        finally:
            dialog.deleteLater()
        if not accepted or revision != self._revision:
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
            job.index,
            replace(panel, source_mask=mask, sky_mask=None),
            summary=message,
            label="Edit Sky Mask",
        )

    def _mask_job_status(self, job: ForegroundJob | MaskEditorJob) -> None:
        self.progress.setValue(0)
        name = job.label.capitalize()
        if job.cancellation_requested:
            self._report_operation(f"{name} cancelled.")
        else:
            self._report_operation(f"{name} failed.", detail=job.error or "No result was returned.")

    def _cancel(self) -> None:
        if self.job is not None:
            self.job.cancel()
            self.cancel_button.setEnabled(False)
            self.status.setText(f"Cancelling {self.job.label}…")
            if isinstance(self.job, PlateSolveJob):
                self._set_solve_summary("Cancelling Plate Solve…")
        else:
            self.command_panel.cancel()

    def _report_operation(self, summary: str, *, detail: str = "") -> None:
        if not self._is_running():
            self._show_job_progress(False)
        message = f"{summary} {detail}" if detail else summary
        self.status.setText(message)
        self.command_panel.append_summary(summary)

    def _report_render_failure(self, summary: str, job: ExportReviewJob | MosaicJob | PreviewJob) -> None:
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
            self._adaptive_timer.stop()
            self._detail_timer.stop()
            self._cancel()
            if self._inspection_job is not None:
                self._inspection_job.cancel()
            if self._detail_job is not None:
                self._detail_job.cancel()
            event.ignore()
        elif self._confirm_discard():
            self._save_workspace()
            self.viewport.release_opengl()
            self._set_project(MosaicProject(auto_frame_preview=True), None)
            event.accept()
        else:
            event.ignore()
            self._start_panel_inspection()
