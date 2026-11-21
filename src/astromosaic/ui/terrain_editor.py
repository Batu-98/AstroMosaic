"""Review source-pixel point pairs and apply a verified terrain fit."""

from dataclasses import replace
from typing import Literal

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSignalBlocker,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from astromosaic.pipeline.control_points import (
    XY,
    ControlPointDiagnostic,
    ControlPointFit,
    GroundControlPoint,
    ModelChoice,
)
from astromosaic.storage.project import MosaicProject
from astromosaic.ui.terrain_job import TerrainFitJob, TerrainImageJob
from astromosaic.ui.terrain_view import TerrainView

_ROOT = QModelIndex()
_POINT_COLUMNS = (
    "Point",
    "Use",
    "Held Out",
    "Panel A (x, y)",
    "Panel B (x, y)",
    "Result",
    "Error (px)",
)
_MODELS: tuple[ModelChoice, ...] = ("auto", "translation", "similarity")
_FIT_GUIDANCE = {
    "disconnected": "Add at least three well-spread training pairs on shared ground between groups, "
    "or exclude panels without shared terrain.",
    "ill-conditioned": "Spread training pairs over a wider area in both panels.",
    "unsupported-scale": "Check point identity and choose panels with similar image scales.",
    "graph-disagreement": "Review the high residuals and inconsistent links.",
    "audit-unavailable": "Check that independent points lie on supported links.",
}
_NO_MEASURE = "—"
type _EditMode = Literal["add", "move"]


def _coordinate(point: GroundControlPoint, panel: int) -> XY:
    return point.left_xy if panel == point.panels[0] else point.right_xy


def _label(status: str) -> str:
    return status.replace("-", " ").capitalize()


def _residual(value: float | None) -> str:
    return _NO_MEASURE if value is None else f"{value:.2f}"


class _PointTable(QAbstractTableModel):
    edited = Signal(object)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.rows: list[GroundControlPoint] = []
        self.panels = (0, 1)
        self.diagnostics: dict[str, ControlPointDiagnostic] = {}

    def set_rows(
        self,
        rows: list[GroundControlPoint],
        panels: tuple[int, int],
        diagnostics: dict[str, ControlPointDiagnostic],
    ) -> None:
        self.beginResetModel()
        self.rows, self.panels, self.diagnostics = rows, panels, diagnostics
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(_POINT_COLUMNS)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _POINT_COLUMNS[section]
        return None

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        flags = super().flags(index)
        if index.isValid() and index.column() in (1, 2):
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | Qt.CheckState | None:
        if not index.isValid():
            return None
        row, column = index.row(), index.column()
        point = self.rows[row]
        if role == Qt.ItemDataRole.CheckStateRole and column in (1, 2):
            selected = point.enabled if column == 1 else point.held_out
            return Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked
        result = self.diagnostics.get(point.id)
        forward = result.forward_error_px if result is not None else None
        reverse = result.reverse_error_px if result is not None else None
        if role == Qt.ItemDataRole.ToolTipRole and forward is not None and reverse is not None:
            return f"Forward {forward:.3f} px · Reverse {reverse:.3f} px"
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        a, b = (_coordinate(point, panel) for panel in self.panels)
        state = _label(result.status) if result is not None else _NO_MEASURE
        if not point.enabled:
            state = "Disabled"
        error = max(forward, reverse) if forward is not None and reverse is not None else None
        return (
            f"{row + 1}. {point.id}",
            "",
            "",
            f"{a[0]:.2f}, {a[1]:.2f}",
            f"{b[0]:.2f}, {b[1]:.2f}",
            state,
            _residual(error),
        )[column]

    def setData(  # noqa: N802
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: object,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if role != Qt.ItemDataRole.CheckStateRole or not index.isValid():
            return False
        point = self.rows[index.row()]
        checked = value in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)
        if index.column() == 1:
            self.edited.emit(replace(point, enabled=checked))
        elif index.column() == 2:
            self.edited.emit(replace(point, held_out=checked))
        else:
            return False
        return True


class TerrainPointEditor(QDialog):
    def __init__(self, project: MosaicProject, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Align Foreground — Control Points")
        self.resize(1100, 760)
        self.project = project
        self.aligned_project: MosaicProject | None = None
        self._candidate: MosaicProject | None = None
        self._fit: ControlPointFit | None = None
        self._job: TerrainImageJob | TerrainFitJob | None = None
        self._cancel_requested = False
        self._close_pending = False
        self._mode: _EditMode | None = None
        self._pending: dict[int, XY] = {}
        self._image_panels: list[int | None] = [None, None]
        self._panels = tuple(index for index, _ in project.foreground_inputs())
        if len(self._panels) < 2:
            raise ValueError("Apply foreground masks to at least two panels.")
        terrain = project.reviewable_terrain()
        self._points = list(terrain.points) if terrain is not None else []
        self._serial = 1
        current = project.current_foreground()

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.model = QComboBox(self)
        self.model.addItems([item.capitalize() for item in _MODELS])
        self.model.setCurrentText(terrain.model.capitalize() if terrain is not None else "Auto")
        self.model.setAccessibleName("Terrain model")
        top.addWidget(QLabel("Model"))
        top.addWidget(self.model)
        self.anchor = self._panel_selector("Anchor")
        if terrain is not None and project.foreground is not None:
            saved_anchor = project.foreground.alignment.anchor
            if saved_anchor is not None and saved_anchor in self._panels:
                self.anchor.setCurrentIndex(self._panels.index(saved_anchor))
        top.addWidget(QLabel("Anchor"))
        top.addWidget(self.anchor)
        top.addStretch()
        layout.addLayout(top)

        if current is None and terrain is not None:
            active = "Saved points loaded. Fit them against the current masks."
        elif current is None:
            active = "Add pairs on matching ground features visible in both panels."
        elif project.foreground is not None and project.foreground.terrain is None:
            active = f"Active alignment · Translation · Anchor panel {current.panels[0].index + 1}"
        else:
            assert terrain is not None and current.anchor is not None
            active = f"Active alignment · {terrain.model.capitalize()} · Anchor panel {current.anchor + 1}"
            if terrain.held_out_p95_px is not None:
                active += f" · Held-out P95 {terrain.held_out_p95_px:.2f} px"
        layout.addWidget(QLabel(active))

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        pair_widget = QWidget(splitter)
        pair_layout = QHBoxLayout(pair_widget)
        pair_layout.setContentsMargins(0, 0, 0, 0)
        self.selectors = (self._panel_selector("Panel A"), self._panel_selector("Panel B"))
        initial_pair = next(
            (
                point.panels
                for point in self._points
                if point.panels[0] != point.panels[1]
                and all(panel in self._panels for panel in point.panels)
            ),
            (self._panels[0], self._panels[1]),
        )
        for selector, panel in zip(self.selectors, initial_pair, strict=True):
            selector.setCurrentIndex(self._panels.index(panel))
        self.views = (TerrainView(pair_widget), TerrainView(pair_widget))
        self.overview_buttons = (QPushButton("Overview"), QPushButton("Overview"))
        for side, (selector, view, overview) in enumerate(
            zip(self.selectors, self.views, self.overview_buttons, strict=True)
        ):
            panel_layout = QVBoxLayout()
            label = "Panel A" if side == 0 else "Panel B"
            heading = QHBoxLayout()
            heading.addWidget(QLabel(label))
            heading.addWidget(selector, 1)
            heading.addWidget(overview)
            panel_layout.addLayout(heading)
            panel_layout.addWidget(view, 1)
            pair_layout.addLayout(panel_layout, 1)
            view.setAccessibleName(f"{label} ground preview")
            view.picked.connect(lambda xy, side=side: self._pick(side, xy))
            view.detail_requested.connect(lambda xy, side=side: self._detail(side, xy))
            overview.clicked.connect(lambda _checked=False, side=side: self._overview(side))
            selector.currentIndexChanged.connect(self._pair_changed)
        splitter.addWidget(pair_widget)

        self.point_model = _PointTable(self)
        self.points_table = QTableView(self)
        self.points_table.setModel(self.point_model)
        self.points_table.setAccessibleName("Terrain control point pairs")
        self.points_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.points_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.points_table.verticalHeader().hide()
        header = self.points_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        points_tab = QWidget(self)
        point_layout = QVBoxLayout(points_tab)
        controls = QHBoxLayout()
        self.add_pair = QPushButton("Add Pair")
        self.move_point = QPushButton("Move Point")
        self.remove_pair = QPushButton("Remove Pair")
        self.cancel_edit = QPushButton("Cancel Edit")
        for button in (self.add_pair, self.move_point, self.remove_pair, self.cancel_edit):
            controls.addWidget(button)
        controls.addStretch()
        point_layout.addLayout(controls)
        point_layout.addWidget(self.points_table, 1)

        self.links = QTableWidget(0, 5, self)
        self.links.setHorizontalHeaderLabels(
            ("Panels", "Result", "Inliers", "Fit P95 (px)", "Held-out P95 (px)")
        )
        self.links.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.links.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.links.verticalHeader().hide()
        self.links.horizontalHeader().setStretchLastSection(True)
        self.links.setAccessibleName("Terrain panel links and residuals")
        self.tabs = QTabWidget(splitter)
        self.tabs.addTab(points_tab, "Point Pairs")
        self.tabs.addTab(self.links, "Panel Links")
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.hint = QLabel(
            "Wheel to zoom. Drag between edits to pan. Right-click for original-pixel detail."
        )
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.fit_button = QPushButton("Fit Points")
        self.cancel_job = QPushButton("Cancel Job")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.apply_button = QPushButton("Apply Alignment")
        close = QPushButton("Close")
        buttons.addWidget(self.fit_button)
        buttons.addWidget(self.cancel_job)
        buttons.addWidget(self.progress, 1)
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self.add_pair.clicked.connect(lambda: self._set_mode("add"))
        self.move_point.clicked.connect(lambda: self._set_mode("move"))
        self.cancel_edit.clicked.connect(lambda: self._set_mode(None))
        self.remove_pair.clicked.connect(self._remove_pair)
        self.point_model.edited.connect(self._update_point)
        self.points_table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.links.cellDoubleClicked.connect(self._open_link)
        self.model.currentIndexChanged.connect(lambda: self._invalidate_fit())
        self.anchor.currentIndexChanged.connect(lambda: self._invalidate_fit())
        self.fit_button.clicked.connect(self._run_fit)
        self.cancel_job.clicked.connect(self._cancel)
        self.apply_button.clicked.connect(self._apply)
        close.clicked.connect(self.reject)
        for button in (
            *self.overview_buttons,
            self.add_pair,
            self.move_point,
            self.remove_pair,
            self.cancel_edit,
            self.fit_button,
            self.cancel_job,
            self.apply_button,
            close,
        ):
            button.setAutoDefault(False)
        self._pair_changed()

    def _panel_selector(self, label: str) -> QComboBox:
        combo = QComboBox(self)
        combo.setAccessibleName(label)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(18)
        for index in self._panels:
            combo.addItem(f"{index + 1}. {self.project.panels[index].source.path.name}")
        return combo

    def _pair(self) -> tuple[int, int]:
        return (
            self._panels[self.selectors[0].currentIndex()],
            self._panels[self.selectors[1].currentIndex()],
        )

    def _pair_changed(self) -> None:
        self._set_mode(None)
        pair = self._pair()
        for side, panel in enumerate(pair):
            if panel != self._image_panels[side]:
                self.views[side].show_image(None)
                self._image_panels[side] = None
        self._sync_points()
        if pair[0] == pair[1]:
            self.status.setText("Choose two different panels to compare.")
            return
        missing = tuple(panel for panel in pair if panel not in self._image_panels)
        if missing:
            self._load_images(missing)

    def _load_images(self, panels: tuple[int, ...], focus: XY | None = None) -> None:
        self._start(TerrainImageJob(self.project, panels, self, focus=focus), "Reading foreground…")

    def _overview(self, side: int) -> None:
        self._load_images((self._pair()[side],))

    def _detail(self, side: int, xy: XY) -> None:
        self._load_images((self._pair()[side],), xy)

    def _selected(self) -> GroundControlPoint | None:
        index = self.points_table.currentIndex()
        if index.isValid() and index.row() < len(self.point_model.rows):
            return self.point_model.rows[index.row()]
        return None

    def _sync_points(self, selected_id: str | None = None) -> None:
        left, right = self._pair()
        pair = left, right
        reverse = right, left
        rows = [point for point in self._points if point.panels in (pair, reverse)]
        diagnostics = {point.id: point for point in self._fit.points} if self._fit else {}
        self.point_model.set_rows(rows, pair, diagnostics)
        if selected_id is not None:
            for index, point in enumerate(rows):
                if point.id == selected_id:
                    self.points_table.selectRow(index)
                    break
        self._selection_changed()

    def _selection_changed(self) -> None:
        selected = self._selected()
        for side, (panel, view) in enumerate(zip(self._pair(), self.views, strict=True)):
            markers = []
            for number, point in enumerate(self.point_model.rows, 1):
                state = self.point_model.diagnostics.get(point.id)
                if point == selected:
                    color = "#50def4"
                elif not point.enabled:
                    color = "#aab5c3"
                elif state is not None and state.status not in ("inlier", "held-out", "usable"):
                    color = "#ff817c"
                else:
                    color = "#ffc46b"
                markers.append((_coordinate(point, panel), color, str(number)))
            if side in self._pending:
                markers.append((self._pending[side], "#50def4", "+"))
            view.set_markers(markers)
        self._controls()

    def _controls(self) -> None:
        idle = self._job is None
        editing = self._mode is not None
        distinct = self._pair()[0] != self._pair()[1]
        images = distinct and all(view.has_image for view in self.views)
        selected = self._selected() is not None
        self.add_pair.setEnabled(idle and images and not editing)
        self.move_point.setEnabled(idle and images and selected and not editing)
        self.remove_pair.setEnabled(idle and selected and not editing)
        self.cancel_edit.setEnabled(idle and editing)
        self.fit_button.setEnabled(idle and not editing and any(p.enabled for p in self._points))
        self.apply_button.setEnabled(idle and not editing and self._candidate is not None)
        self.cancel_job.setEnabled(not idle and not self._cancel_requested)
        self.cancel_job.setVisible(not idle)
        self.progress.setVisible(not idle)
        for control in (*self.selectors, self.anchor, self.model, self.links, *self.views):
            control.setEnabled(idle)
        self.points_table.setEnabled(idle and not editing)
        for button in self.overview_buttons:
            button.setEnabled(idle and distinct)

    def _set_mode(self, mode: _EditMode | None) -> None:
        self._mode = mode
        self._pending.clear()
        for view in self.views:
            view.set_editing(mode is not None)
        self._selection_changed()
        if mode == "add":
            self.status.setText("Click the same terrain feature in each panel.")
        elif mode == "move":
            self.status.setText("Click the new position in the panel you want to change.")
        else:
            self._show_fit()

    def _pick(self, side: int, xy: XY) -> None:
        if self._job is not None:
            return
        if self._mode == "add":
            self._pending[side] = xy
            if len(self._pending) < 2:
                self.status.setText(
                    f"Click the corresponding point in Panel {'B' if side == 0 else 'A'}."
                )
                self._selection_changed()
                return
            identifiers = {point.id for point in self._points}
            while f"Point {self._serial}" in identifiers:
                self._serial += 1
            point = GroundControlPoint(
                f"Point {self._serial}", self._pair(), self._pending[0], self._pending[1]
            )
            self._serial += 1
            self._points.append(point)
        elif self._mode == "move":
            selected = self._selected()
            if selected is None:
                return
            panel = self._pair()[side]
            point = (
                replace(selected, left_xy=xy)
                if panel == selected.panels[0]
                else replace(selected, right_xy=xy)
            )
            self._points[self._points.index(selected)] = point
        else:
            return
        self._set_mode(None)
        self._invalidate_fit(point.id)

    def _update_point(self, point: GroundControlPoint) -> None:
        index = next(i for i, old in enumerate(self._points) if old.id == point.id)
        self._points[index] = point
        self._invalidate_fit(point.id)

    def _remove_pair(self) -> None:
        point = self._selected()
        if point is not None:
            self._points.remove(point)
            self._invalidate_fit()

    def _open_link(self, row: int, _column: int) -> None:
        if self._fit is None:
            return
        for selector, panel in zip(self.selectors, self._fit.edges[row].panels, strict=True):
            with QSignalBlocker(selector):
                selector.setCurrentIndex(self._panels.index(panel))
        self.tabs.setCurrentIndex(0)
        self._pair_changed()

    def _invalidate_fit(self, selected_id: str | None = None) -> None:
        self._candidate = None
        self._fit = None
        self._sync_points(selected_id)
        self._show_fit()

    def _show_fit(self) -> None:
        fit = self._fit
        if fit is None:
            self.links.setRowCount(0)
            self.status.setText("Fit enabled point pairs to review their residuals.")
            return
        self.links.setRowCount(len(fit.edges))
        for row, edge in enumerate(fit.edges):
            a, b = edge.panels
            cells = (
                f"{a + 1} ↔ {b + 1}",
                _label(edge.status),
                f"{edge.inliers} / {edge.training_points}",
                _residual(edge.training_p95_px),
                _residual(edge.held_out_p95_px),
            )
            for column, value in enumerate(cells):
                self.links.setItem(row, column, QTableWidgetItem(value))
        self.links.resizeColumnsToContents()
        summary = (
            f"{fit.model.capitalize()} · Anchor panel {fit.anchor + 1} · {_label(fit.status)}."
        )
        if len(fit.groups) > 1:
            groups = " | ".join(
                ", ".join(str(panel + 1) for panel in group) for group in fit.groups
            )
            summary += f" Panel groups {groups}."
        guidance = _FIT_GUIDANCE.get(fit.status)
        self.status.setText(f"{summary} {guidance}" if guidance else summary)

    def _run_fit(self) -> None:
        self._invalidate_fit()
        model = _MODELS[self.model.currentIndex()]
        anchor = self._panels[self.anchor.currentIndex()]
        self._start(
            TerrainFitJob(self.project, tuple(self._points), model, anchor, self),
            "Fitting foreground control points…",
        )

    def _start(self, job: TerrainImageJob | TerrainFitJob, message: str) -> None:
        self._job = job
        self._cancel_requested = False
        self.progress.setRange(0, 0)
        self.status.setText(message)
        job.progress.connect(self._progress)
        job.finished.connect(self._finished)
        self._controls()
        job.start()

    @Slot(object, object)
    def _progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(done)

    @Slot()
    def _finished(self) -> None:
        job, self._job = self._job, None
        assert job is not None
        job.deleteLater()
        if self._close_pending:
            super().reject()
            return
        if self._cancel_requested or job.cancelled:
            self.status.setText(f"{job.label.capitalize()} cancelled.")
        elif job.result is None:
            self.status.setText(job.error or f"{job.label.capitalize()} failed.")
        elif isinstance(job, TerrainFitJob):
            self._fit, self._candidate = job.result
            self._sync_points()
            self._show_fit()
        else:
            for side, panel in enumerate(self._pair()):
                if panel in job.result:
                    self._image_panels[side] = panel
                    self.views[side].show_image(job.result[panel])
            self._selection_changed()
            if self._mode is None:
                self._show_fit()
            else:
                self.status.setText("Click to continue editing the selected point pair.")
        self._controls()

    def _cancel(self) -> None:
        if self._job is not None:
            self._cancel_requested = True
            self._job.cancel()
            self.status.setText(f"Cancelling {self._job.label}…")
            self._controls()

    def _apply(self) -> None:
        if self._job is None and self._candidate is not None and self._mode is None:
            self.aligned_project = self._candidate
            self.accept()

    def reject(self) -> None:
        if self._job is not None:
            self._close_pending = True
            self._cancel()
        else:
            super().reject()
