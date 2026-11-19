"""Inspect solve attempts, catalog queries and measured source-pixel errors."""

from collections.abc import Sequence
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from astromosaic.astrometry.solve_validation import MODEL_GRID

_SOLVERS = {
    "existing-wcs": "Existing WCS",
    "astap-hinted": "ASTAP hinted",
    "astap-blind": "ASTAP recovery",
    "gaia-dr3": "Gaia DR3",
}
_REJECTION_STAGES = {
    "catalog-resource": "Catalog resource limit",
    "catalog-query": "Catalog query",
    "association": "Association confidence",
    "rms": "Catalog RMS",
    "held-out": "Held-out residuals",
    "edge-support": "Field-edge support",
    "existing-wcs": "Existing WCS verification",
}


def _value(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and isfinite(value) else None


def _pair(value: object) -> tuple[float, float] | None:
    if isinstance(value, tuple | list) and len(value) == 2:
        first, second = map(_value, value)
        if first is not None and second is not None:
            return first, second
    return None


class PlateSolveDetails(QDialog):
    def __init__(
        self,
        quality: dict[str, object],
        parent: QWidget,
        *,
        attempts: Sequence[dict[str, object]] = (),
        solve_error: str | None = None,
        has_wcs: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Plate Solve Details")
        self.resize(860 if attempts else 700, 540 if attempts else 510)
        self.quality = quality
        self.attempts = attempts
        layout = QVBoxLayout(self)
        summary = QLabel()
        summary.setTextFormat(Qt.TextFormat.PlainText)
        summary.setWordWrap(True)
        layout.addWidget(summary)
        field = quality.get("field_geometry")
        rms = _value(quality.get("rms_arcsec"))
        has_measurements = isinstance(field, dict) and rms is not None
        if solve_error:
            summary.setText(solve_error)
        elif not has_wcs:
            summary.setText("Review the attempted solvers and their outcomes.")
        elif not has_measurements:
            summary.setText("This WCS has geometric validation. Catalog residuals are unavailable.")
        else:
            assert isinstance(field, dict) and rms is not None
            skew = _value(field.get("linear_skew_deg"))
            summary.setText(
                f"{quality.get('model')}  ·  {quality.get('unique_matches')} matched stars"
                f"  ·  RMS {rms:.2f}″  ·  Edge support {quality.get('edge_status')}"
                + (f"  ·  Linear skew {skew:.2f}°" if skew is not None else "")
            )
        measurements = QWidget()
        measured_layout = QVBoxLayout(measurements)
        measured_layout.setContentsMargins(0, 0, 0, 0)
        if has_measurements:
            self.mode = QComboBox()
            self.mode.addItems(["Model displacement (px)", "Measured error P95 (px)"])
            self.mode.currentIndexChanged.connect(self._refresh)
            measured_layout.addWidget(self.mode)
            self.caption = QLabel()
            self.caption.setWordWrap(True)
            measured_layout.addWidget(self.caption)
            self.grid = QTableWidget(MODEL_GRID, MODEL_GRID)
            self.grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.grid.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            measured_layout.addWidget(self.grid)
            self._refresh()
        if attempts and has_measurements:
            tabs = QTabWidget()
            tabs.addTab(self._attempt_view(), "Attempts")
            tabs.addTab(measurements, "Field Measurements")
            layout.addWidget(tabs, 1)
        elif attempts:
            layout.addWidget(self._attempt_view(), 1)
        elif has_measurements:
            layout.addWidget(measurements, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _attempt_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        self.attempt_box = QComboBox()
        self.attempt_box.setAccessibleName("Plate solve attempts")
        for attempt in self.attempts:
            backend = str(attempt.get("stage", "Solver"))
            method = attempt.get("method")
            name = _SOLVERS.get(backend, backend)
            if backend == "gaia-dr3" or method == "fov-recovery":
                name += f" · {method or 'search'}"
            self.attempt_box.addItem(f"{name} · {attempt.get('outcome', 'recorded')}")
        layout.addWidget(self.attempt_box)
        self.attempt_detail = QLabel()
        self.attempt_detail.setTextFormat(Qt.TextFormat.PlainText)
        self.attempt_detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.attempt_detail.setWordWrap(True)
        layout.addWidget(self.attempt_detail)
        self.catalog_table = QTableWidget(0, 9)
        self.catalog_table.setAccessibleName("ASTAP regional catalog reads")
        self.catalog_table.setHorizontalHeaderLabels(
            [
                "Row",
                "Column",
                "Detections",
                "Area (deg²)",
                "Decoded",
                "Retained",
                "Read (MiB)",
                "Time (s)",
                "Result",
            ]
        )
        self.catalog_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.catalog_table.verticalHeader().hide()
        self.catalog_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.catalog_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.catalog_table, 1)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        selected = next(
            (
                i
                for outcome in ("solved", "rejected", "budget-exhausted", "failed", "timeout")
                for i, attempt in enumerate(self.attempts)
                if attempt.get("outcome") == outcome and attempt.get("stage") != "existing-wcs"
            ),
            len(self.attempts) - 1,
        )
        self.attempt_box.setCurrentIndex(selected)
        self.attempt_box.currentIndexChanged.connect(self._show_attempt)
        self._show_attempt(selected)
        return view

    def _show_attempt(self, index: int) -> None:
        if not 0 <= index < len(self.attempts):
            return
        attempt = self.attempts[index]
        lines = []
        stage = attempt.get("failure_stage")
        if isinstance(stage, str):
            lines.append(_REJECTION_STAGES.get(stage, stage.replace("-", " ").capitalize()))
        if detail := attempt.get("detail"):
            lines.append(str(detail))
        catalog = attempt.get("catalog") or attempt.get("resolved_catalog")
        identities = []
        if version := attempt.get("backend_version"):
            identities.append(str(version))
        if catalog:
            identities.append(f"Catalog {catalog}")
        if identities:
            lines.append(" · ".join(identities))
        pointing = _pair(attempt.get("effective_position_deg"))
        scales = _pair(attempt.get("effective_scale_interval_arcsec_px"))
        scale = _value(attempt.get("effective_scale_arcsec_px"))
        fov = _value(attempt.get("effective_fov_deg"))
        hints = []
        if pointing is not None:
            hints.append(f"RA {pointing[0]:.6g}°, Dec {pointing[1]:.6g}°")
        if scale is not None:
            hints.append(f"Scale {scale:.5g} ″/px")
        if scales is not None:
            hints.append(f"Scale range {scales[0]:g}–{scales[1]:g} ″/px")
        if fov is not None:
            hints.append(f"Field height {fov:.5g}°" if fov else "Automatic field height")
        if hints:
            lines.append(" · ".join(hints))

        evidence = attempt.get("rejection_evidence")
        if isinstance(evidence, dict):
            metrics = (
                ("detected_stars", "Detections", ""),
                ("unique_matches", "Catalog matches", ""),
                ("chance_control_matches", "Shifted control matches", ""),
                ("native_match_count", "Native matches", ""),
                ("native_false_match_probability", "False-match probability", ""),
                ("rms_arcsec", "RMS", "″"),
                ("rms_limit_arcsec", "RMS limit", "″"),
                ("held_out_p95_source_px", "Held-out P95", " px"),
                ("held_out_outer_p95_source_px", "Edge P95", " px"),
                ("held_out_outer_matches", "Held-out edge stars", ""),
                ("held_out_outer_sectors", "Supported edge sectors", ""),
            )
            values = []
            for key, label, units in metrics:
                value = _value(evidence.get(key))
                if value is not None:
                    values.append(f"{label} {value:.4g}{units}")
            if values:
                lines.append(" · ".join(values))
        self.attempt_detail.setText("\n".join(lines))

        raw_regions = attempt.get("catalog_regions")
        regions = (
            [r for r in raw_regions if isinstance(r, dict)]
            if isinstance(raw_regions, tuple | list)
            else []
        )
        self.catalog_table.setVisible(bool(regions))
        self.catalog_table.setRowCount(len(regions))
        for row, region in enumerate(regions):
            area, read, elapsed = (
                _value(region.get(key)) for key in ("area_sq_deg", "read_bytes", "elapsed_seconds")
            )
            fields = (
                str(region.get("row", "—")),
                str(region.get("column", "—")),
                str(region.get("detected_stars", "—")),
                f"{area:.3f}" if area is not None else "—",
                str(region.get("decoded_stars", "—")),
                str(region.get("retained_stars", "—")),
                f"{read / 1024**2:.3f}" if read is not None else "—",
                f"{elapsed:.3f}" if elapsed is not None else "—",
                str(region.get("outcome", "—")),
            )
            for column, text in enumerate(fields):
                self.catalog_table.setItem(row, column, QTableWidgetItem(text))

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
