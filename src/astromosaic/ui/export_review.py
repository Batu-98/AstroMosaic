"""Review the effective desktop export before choosing a filename."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QWidget

from astromosaic.core.job import JobContext
from astromosaic.photometry.photo import PhotoTone
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.storage.project import Layer, MosaicProject, inspect_project_export


@dataclass(frozen=True, slots=True)
class OutputFormat:
    name: str
    suffixes: tuple[str, ...]

    @property
    def file_filter(self) -> str:
        return f"{self.name} ({' '.join('*' + suffix for suffix in self.suffixes)})"

    def destination(self, path: Path) -> Path:
        if not path.suffix:
            return path.with_suffix(self.suffixes[0])
        if path.suffix.casefold() not in self.suffixes:
            raise ValueError(f"Choose a {self.name} filename ({', '.join(self.suffixes)}).")
        return path


TIFF = OutputFormat("TIFF", (".tiff", ".tif"))
FITS = OutputFormat("FITS", (".fits", ".fit", ".fts"))
XISF = OutputFormat("XISF", (".xisf",))


@dataclass(frozen=True, slots=True)
class ExportRequest:
    project: MosaicProject
    layer: Layer
    band: str | None
    photo_grid: RenderSpec | None = None
    tone: PhotoTone | None = None

    def review(self, context: JobContext) -> "ExportDescription":
        layout = inspect_project_export(
            self.project, self.layer, self.band, self.photo_grid, context
        )
        grid = self.photo_grid or self.project.render
        photo = self.photo_grid is not None
        fields = [
            ("Intent", "sRGB photo" if photo else "Linear mosaic"),
            ("Layer", self.layer.capitalize()),
            ("Dimensions", f"{layout.width:,} × {layout.height:,} px"),
        ]
        if self.layer == "sky":
            ra, dec = grid.center
            fields.append(("Sky band", self.band or self.project.filter_name or "All sky panels"))
            effective = "Fitted preview grid" if photo else "Saved scientific grid"
            fields.append(
                (
                    "Grid",
                    f"{effective} · {grid.projection} · RA {ra:.7g}°, Dec {dec:.7g}°\n"
                    f"{grid.scale_arcsec:g} arcsec/px · Rotation {grid.rotation_deg:g}°",
                )
            )
            crop = grid.crop
            fields.append(
                (
                    "Crop",
                    "Full grid"
                    if crop is None
                    else f"{crop.x}, {crop.y} · {crop.width} × {crop.height} px",
                )
            )
        elif self.layer == "composition":
            assert self.project.composition is not None
            offset = self.project.composition.placement.offset
            fields.append(
                (
                    "Grid",
                    f"Composition canvas · Foreground offset ({offset[0]:g}, {offset[1]:g}) px",
                )
            )
            fields.append(
                ("Crop", f"Sky bottom crop · {self.project.composition.sky_crop_bottom} px")
            )
        else:
            fields.append(("Grid", "Aligned foreground canvas (pixel coordinates)"))
            fields.append(("Crop", "Full foreground canvas"))
        if photo:
            fields.extend(
                (
                    ("ICC profile", "sRGB"),
                    ("Tone", "Preserve Tone" if self.tone is None else "Use Preview Tone"),
                )
            )
        formats = (TIFF,) if photo else (TIFF, FITS, XISF) if layout.channels == 1 else (TIFF, XISF)
        return ExportDescription(tuple(fields), formats, photo, self.layer == "composition")


@dataclass(frozen=True, slots=True)
class ExportDescription:
    fields: tuple[tuple[str, str], ...]
    formats: tuple[OutputFormat, ...]
    photo: bool
    layers: bool

    def coverage(self, output: OutputFormat) -> str:
        if self.photo:
            return "Transparent alpha channel"
        descriptions = {
            TIFF: ("Coverage SubIFD", "Layer contributions SubIFD"),
            FITS: ("COVERAGE extension", "LAYERS extension"),
            XISF: ("Coverage attachment", "Layer contributions attachment"),
        }
        coverage, layers = descriptions[output]
        return f"{coverage} · {layers}" if self.layers else coverage


class ExportReview(QDialog):
    def __init__(self, description: ExportDescription, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Review Mosaic Export")
        self._description = description
        form = QFormLayout(self)
        self.formats = QComboBox()
        self.formats.setAccessibleName("Export file format")
        for output in description.formats:
            self.formats.addItem(output.name)
        form.addRow("Format", self.formats)
        for name, value in description.fields:
            label = QLabel(value)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            form.addRow(name, label)
        self._coverage = QLabel()
        self._coverage.setWordWrap(True)
        form.addRow("Coverage", self._coverage)
        self.formats.currentIndexChanged.connect(self._update_coverage)
        self._update_coverage()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Choose File…")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @property
    def output(self) -> OutputFormat:
        return self._description.formats[self.formats.currentIndex()]

    def _update_coverage(self) -> None:
        self._coverage.setText(self._description.coverage(self.output))
