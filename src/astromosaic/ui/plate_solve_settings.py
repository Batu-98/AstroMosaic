"""Edit and check the per-user paths for local plate solving."""

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from astromosaic.astrometry.astap_probe import ASTAP_DATABASE_CHOICES
from astromosaic.astrometry.hints import positive_number
from astromosaic.astrometry.solve import SolveOptions
from astromosaic.astrometry.solve_budget import DEFAULT_PANEL_SECONDS
from astromosaic.astrometry.solver_setup import check_solver_paths
from astromosaic.core.job import JobContext
from astromosaic.ui.mosaic_job import BackgroundJob

_SETTINGS_KEY = "plate_solve"
_CHECK_HINT = "Check Paths to verify the selected local solvers."


def _settings() -> QSettings:
    settings = QSettings("AstroMosaic", "AstroMosaic")
    settings.setFallbacksEnabled(False)
    return settings


def _path(value: object) -> Path | None:
    if isinstance(value, str) and (text := value.strip()):
        return Path(text).absolute()
    return None


def load_plate_solve_settings() -> SolveOptions:
    """Load local backend paths for a desktop solve."""
    saved = _settings().value(_SETTINGS_KEY, {})
    if not isinstance(saved, dict):
        return SolveOptions()
    database = saved.get("astap_database")
    return SolveOptions(
        gaia_catalog=_path(saved.get("gaia_catalog")),
        gaia_index=_path(saved.get("gaia_index")),
        astap=_path(saved.get("astap")),
        astap_catalog=_path(saved.get("astap_catalog")),
        astap_database=database if database in ASTAP_DATABASE_CHOICES else "auto",
        timeout_seconds=positive_number(saved.get("timeout_seconds")) or 60,
        total_seconds=positive_number(saved.get("total_seconds")) or DEFAULT_PANEL_SECONDS,
        job_seconds=positive_number(saved.get("job_seconds")),
        strict_edges=saved.get("strict_edges") is True,
    )


def _save_plate_solve_settings(options: SolveOptions) -> None:
    settings = _settings()
    settings.setValue(
        _SETTINGS_KEY,
        {
            "gaia_catalog": str(options.gaia_catalog or ""),
            "gaia_index": str(options.gaia_index or ""),
            "astap": str(options.astap or ""),
            "astap_catalog": str(options.astap_catalog or ""),
            "astap_database": options.astap_database,
            "timeout_seconds": options.timeout_seconds,
            "total_seconds": options.total_seconds,
            "job_seconds": options.job_seconds,
            "strict_edges": options.strict_edges,
        },
    )
    settings.sync()
    if settings.status() != QSettings.Status.NoError:
        raise OSError("Could not save the local plate solve settings. Check settings access.")


class _SolverPathCheck(BackgroundJob[tuple[str, str]]):
    def __init__(self, options: SolveOptions, parent: QDialog) -> None:
        super().__init__(parent)
        self.options = options

    def perform(self, context: JobContext) -> tuple[str, str]:
        return check_solver_paths(self.options, context)


class PlateSolveSettings(QDialog):
    operation_summary = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Plate Solve Settings")
        self.resize(640, 420)
        self._job: _SolverPathCheck | None = None
        self._dismiss_pending = False

        options = load_plate_solve_settings()
        layout = QVBoxLayout(self)
        self._fields = QWidget(self)
        fields = QVBoxLayout(self._fields)
        fields.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._fields)

        gaia = QGroupBox("Gaia DR3")
        fields.addWidget(gaia)
        gaia_form = QFormLayout(gaia)
        self.gaia_catalog = self._path_row(
            gaia_form, "Star catalog", options.gaia_catalog, "Seiza star catalogs (*.bin)"
        )
        self.gaia_index = self._path_row(
            gaia_form, "Blind index (optional)", options.gaia_index, "Seiza blind indexes (*.idx)"
        )
        self.gaia_index.setToolTip(
            "Choose the matching index for panels without pointing and plate scale hints."
        )

        astap = QGroupBox("ASTAP")
        fields.insertWidget(0, astap)
        astap_form = QFormLayout(astap)
        self.astap = self._path_row(astap_form, "CLI executable", options.astap, "Programs (*.exe)")
        self.astap_catalog = self._path_row(astap_form, "Catalog folder", options.astap_catalog)
        self.astap_database = QComboBox()
        self.astap_database.addItems(
            ["Automatic", *(name.upper() for name in ASTAP_DATABASE_CHOICES[1:])]
        )
        self.astap_database.setCurrentIndex(ASTAP_DATABASE_CHOICES.index(options.astap_database))
        astap_form.addRow("Database", self.astap_database)

        solve_limits = QGroupBox("Solve Limits")
        fields.addWidget(solve_limits)
        limits = QFormLayout(solve_limits)
        self.total_seconds = self._seconds(options.total_seconds)
        self.total_seconds.setToolTip("Includes preparation, searching, validation and saving.")
        limits.addRow("Per panel", self.total_seconds)
        self.timeout_seconds = self._seconds(options.timeout_seconds)
        self.timeout_seconds.setToolTip("Upper limit for one native search. Stage caps also apply.")
        limits.addRow("Per attempt", self.timeout_seconds)
        self.job_seconds = self._seconds(options.job_seconds or 0, optional=True)
        limits.addRow("Entire batch", self.job_seconds)
        self.strict_edges = QCheckBox("Require held-out field-edge validation")
        self.strict_edges.setChecked(options.strict_edges)
        limits.addRow(self.strict_edges)

        self.message = QLabel(_CHECK_HINT)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        for field in (self.gaia_catalog, self.gaia_index, self.astap, self.astap_catalog):
            field.textChanged.connect(self._clear_check)
        self.astap_database.currentIndexChanged.connect(self._clear_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.check_button = buttons.addButton("Check Paths", QDialogButtonBox.ButtonRole.ActionRole)
        self.check_button.clicked.connect(self._start_check)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _seconds(value: float, *, optional: bool = False) -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setDecimals(1)
        field.setRange(0 if optional else 0.1, 999999.0)
        field.setSingleStep(5)
        field.setSuffix(" s")
        if optional:
            field.setSpecialValueText("No limit")
        field.setValue(value)
        return field

    def _path_row(
        self, form: QFormLayout, label: str, path: Path | None, file_filter: str | None = None
    ) -> QLineEdit:
        field = QLineEdit(str(path or ""))
        field.setAccessibleName(label)
        browse = QPushButton("Browse…")
        browse.setAccessibleName(f"Browse for {label.lower()}")

        def choose() -> None:
            if file_filter is None:
                selected = QFileDialog.getExistingDirectory(self, label, field.text())
            else:
                selected, _ = QFileDialog.getOpenFileName(
                    self, label, field.text(), f"{file_filter};;All files (*)"
                )
            if selected:
                field.setText(selected)

        browse.clicked.connect(choose)
        row = QHBoxLayout()
        row.addWidget(field, 1)
        row.addWidget(browse)
        form.addRow(label, row)
        return field

    def _options(self) -> SolveOptions:
        return SolveOptions(
            gaia_catalog=_path(self.gaia_catalog.text()),
            gaia_index=_path(self.gaia_index.text()),
            astap=_path(self.astap.text()),
            astap_catalog=_path(self.astap_catalog.text()),
            astap_database=ASTAP_DATABASE_CHOICES[self.astap_database.currentIndex()],
            timeout_seconds=self.timeout_seconds.value(),
            total_seconds=self.total_seconds.value(),
            job_seconds=self.job_seconds.value() or None,
            strict_edges=self.strict_edges.isChecked(),
        )

    @Slot()
    def _clear_check(self) -> None:
        self.message.setText(_CHECK_HINT)

    @Slot()
    def _start_check(self) -> None:
        if self._job is not None:
            return
        self._job = _SolverPathCheck(self._options(), self)
        self._job.finished.connect(self._finish_check)
        self._fields.setEnabled(False)
        self.save_button.setEnabled(False)
        self.check_button.setEnabled(False)
        message = "Checking local solver paths…"
        self.message.setText(message)
        self.operation_summary.emit(message)
        self._job.start()

    @Slot()
    def _finish_check(self) -> None:
        job, self._job = self._job, None
        assert job is not None
        job.deleteLater()
        if self._dismiss_pending:
            self.operation_summary.emit("Local solver path check cancelled.")
            super().reject()
            return
        self._fields.setEnabled(True)
        self.save_button.setEnabled(True)
        self.check_button.setEnabled(True)
        if job.result is None:
            self.message.setText(job.error or "The path check did not complete.")
            self.operation_summary.emit("Local solver path check failed.")
        else:
            gaia, astap = job.result
            self.message.setText(f"ASTAP\n{astap}\n\nGaia DR3\n{gaia}")
            self.operation_summary.emit("Local solver path check completed.")

    def accept(self) -> None:
        if self._job is not None:
            return
        try:
            _save_plate_solve_settings(self._options())
        except OSError as error:
            self.message.setText(str(error))
            self.operation_summary.emit("Could not save local plate solve settings.")
            return
        super().accept()

    def reject(self) -> None:
        if self._job is None:
            super().reject()
        else:
            self._dismiss_pending = True
            self._job.cancel()
            self.message.setText("Cancelling the path check…")
