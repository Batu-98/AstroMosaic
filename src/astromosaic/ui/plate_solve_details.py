"""Inspect bounded model predictions and measured source-pixel errors."""

from math import isfinite

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from astromosaic.astrometry.solve_validation import MODEL_GRID


def _value(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and isfinite(value) else None


class PlateSolveDetails(QDialog):
    def __init__(self, quality: dict[str, object], parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Plate Solve Details")
        self.resize(700, 510)
        self.quality = quality
        layout = QVBoxLayout(self)
        summary = QLabel()
        summary.setTextFormat(Qt.TextFormat.PlainText)
        summary.setWordWrap(True)
        layout.addWidget(summary)
        field = quality.get("field_geometry")
        rms = _value(quality.get("rms_arcsec"))
        if not isinstance(field, dict) or rms is None:
            summary.setText("This WCS has geometric validation. Catalog residuals are unavailable.")
        else:
            skew = _value(field.get("linear_skew_deg"))
            summary.setText(
                f"{quality.get('model')}  ·  {quality.get('unique_matches')} matched stars"
                f"  ·  RMS {rms:.2f}″  ·  Edge support {quality.get('edge_status')}"
                + (f"  ·  Linear skew {skew:.2f}°" if skew is not None else "")
            )
            self.mode = QComboBox()
            self.mode.addItems(["Model displacement (px)", "Measured error P95 (px)"])
            self.mode.currentIndexChanged.connect(self._refresh)
            layout.addWidget(self.mode)
            self.caption = QLabel()
            self.caption.setWordWrap(True)
            layout.addWidget(self.caption)
            self.grid = QTableWidget(MODEL_GRID, MODEL_GRID)
            self.grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.grid.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            layout.addWidget(self.grid)
            self._refresh()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh(self) -> None:
        model = self.mode.currentIndex() == 0
        self.caption.setText(
            "Predicted shifts relative to the linear TAN model in original image coordinates."
            if model
            else "Measured source-to-catalog residuals. A dash marks cells with fewer than five matched stars."
        )
        field = self.quality.get("field_geometry")
        assert isinstance(field, dict)
        cells = field.get("model_grid") if model else self.quality.get("measured_regions")
        if not isinstance(cells, list) or len(cells) != MODEL_GRID**2:
            self.grid.clearContents()
            return
        key = "model_displacement_source_px" if model else "p95_source_px"
        values = [_value(cell.get(key)) if isinstance(cell, dict) else None for cell in cells]
        high = max((value for value in values if value is not None), default=0.0)
        for index, (cell, value) in enumerate(zip(cells, values, strict=True)):
            item = QTableWidgetItem(f"{value:.2f}" if value is not None else "—")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if value is not None:
                strength = min(1, max(0, value / high)) if high > 0 else 0
                item.setBackground(QColor.fromHsvF(0.60 - 0.48 * strength, 0.25, 0.95))
                item.setForeground(QColor(25, 25, 25))
            if isinstance(cell, dict):
                if model:
                    vector = cell.get("model_vector_source_px")
                    if isinstance(vector, list) and len(vector) == 2:
                        dx, dy = map(_value, vector)
                        if dx is not None and dy is not None:
                            item.setToolTip(f"Δx {dx:+.3f} px, Δy {dy:+.3f} px")
                else:
                    item.setToolTip(
                        f"{cell.get('matches', 0)} matches, "
                        f"{cell.get('held_out_matches', 0)} held out. {cell.get('support', '')}"
                    )
            self.grid.setItem(index // MODEL_GRID, index % MODEL_GRID, item)
