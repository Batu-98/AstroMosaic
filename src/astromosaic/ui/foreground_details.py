"""Show measured foreground overlap evidence for the current panel set."""

from math import ceil

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from astromosaic.pipeline.foreground import (
    MIN_GROUND_CORRELATION,
    MIN_GROUND_PEAK_SEPARATION,
    ForegroundPairStage,
)
from astromosaic.ui.mosaic_job import ForegroundAlignmentReport

_OUTCOMES: dict[ForegroundPairStage, str] = {
    "support": "Insufficient mask overlap",
    "texture": "Insufficient texture",
    "correlation": "Low correlation",
    "ambiguity": "Ambiguous peak",
    "refinement": "Refinement failed",
    "accepted": "Accepted",
}
_COLUMNS = ("Panel A", "Panel B", "Result", "Shared / min", "Peak", "Competing peak", "Patches")
_ROOT = QModelIndex()
_DASH = "—"


class _PairTable(QAbstractTableModel):
    def __init__(
        self, report: ForegroundAlignmentReport, names: tuple[str, ...], parent: QWidget
    ) -> None:
        super().__init__(parent)
        self.report = report
        self.names = names
        self.disagreements = dict(report.residuals)

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(self.report.pairs)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(_COLUMNS)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _COLUMNS[section]
        return None

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if not index.isValid() or role not in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.ToolTipRole,
        ):
            return None
        pair = self.report.pairs[index.row()]
        a, b = pair.panels
        thumb = pair.thumbnail
        shared = _DASH
        if thumb.peak_shared_samples is not None:
            shared = f"{thumb.peak_shared_samples:,} / {ceil(thumb.shared_threshold):,}"
        elif thumb.maximum_shared_samples is not None:
            shared = f"Max {thumb.maximum_shared_samples:,} / {ceil(thumb.shared_threshold):,}"
        patches = pair.refinement
        cells = (
            f"{a + 1}. {self.names[a]}",
            f"{b + 1}. {self.names[b]}",
            "Graph disagreement" if pair.panels in self.disagreements else _OUTCOMES[pair.stage],
            shared,
            f"{thumb.peak:.3f}" if thumb.peak is not None else _DASH,
            f"{thumb.competing_peak:.3f}" if thumb.competing_peak is not None else _DASH,
            f"{patches.agreeing_patches} / {patches.tested_patches}"
            if patches is not None
            else _DASH,
        )
        return cells[index.column()]


class ForegroundAlignmentDetails(QDialog):
    def __init__(
        self, report: ForegroundAlignmentReport, names: tuple[str, ...], parent: QWidget
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Foreground Alignment Details")
        self.resize(950, 450)
        self.selected_panel: int | None = None
        self.review_requested = False
        self.model = _PairTable(report, names, self)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setAccessibleName("Foreground panel pair measurements")
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        for column, width in enumerate((143, 143, 165, 132, 70, 110, 80)):
            self.table.setColumnWidth(column, width)
        self.table.selectionModel().currentRowChanged.connect(self._update_selection)

        layout = QVBoxLayout(self)
        summary_text = report.error or f"{len(report.pairs):,} foreground pairs evaluated."
        if len(report.groups) > 1:
            groups = " | ".join(", ".join(str(i + 1) for i in group) for group in report.groups)
            summary_text = f"{len(report.groups):,} disconnected groups. Panel groups {groups}."
        summary = QLabel(summary_text)
        summary.setTextFormat(Qt.TextFormat.PlainText)
        summary.setWordWrap(True)
        layout.addWidget(summary)
        layout.addWidget(self.table, 1)
        self.detail = QLabel()
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.mask_a = buttons.addButton("Inspect Mask A…", QDialogButtonBox.ButtonRole.ActionRole)
        self.mask_b = buttons.addButton("Inspect Mask B…", QDialogButtonBox.ButtonRole.ActionRole)
        review = buttons.addButton("Review Control Points…", QDialogButtonBox.ButtonRole.ActionRole)
        self.mask_a.clicked.connect(lambda: self._inspect(0))
        self.mask_b.clicked.connect(lambda: self._inspect(1))
        review.clicked.connect(self._review_points)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.table.selectRow(0)

    def _review_points(self) -> None:
        self.review_requested = True
        self.accept()

    def _update_selection(self, current: QModelIndex) -> None:
        self.mask_a.setEnabled(current.isValid())
        self.mask_b.setEnabled(current.isValid())
        if not current.isValid():
            self.detail.clear()
            return
        pair = self.model.report.pairs[current.row()]
        a_count, b_count = pair.thumbnail.usable_samples
        message = (
            f"Usable thumbnail samples  A {a_count:,} · B {b_count:,}. "
            f"Required shared samples {ceil(pair.thumbnail.shared_threshold):,}.\n"
            f"Required peak ≥ {MIN_GROUND_CORRELATION:.2f} · "
            f"Required separation from competing peak ≥ {MIN_GROUND_PEAK_SEPARATION:.2f}."
        )
        if pair.refinement is not None:
            patches = pair.refinement
            message += (
                f"\nFull resolution  {patches.tested_patches} tested · "
                f"{patches.matched_patches} matched near the thumbnail shift · "
                f"{patches.agreeing_patches} agreed."
            )
        if pair.panels in self.model.disagreements:
            residual = self.model.disagreements[pair.panels]
            message += f"\nThe overlap differs from the graph fit by {residual:.2f} source px."
        self.detail.setText(message)

    def _inspect(self, side: int) -> None:
        index = self.table.currentIndex()
        if index.isValid():
            self.selected_panel = self.model.report.pairs[index.row()].panels[side]
            self.accept()
