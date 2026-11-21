"""Dialogs for project geometry, render settings, and panel attachments."""

from dataclasses import replace
from math import isfinite
from pathlib import Path
from typing import Literal, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from astromosaic.astrometry.hints import PanelOptics
from astromosaic.core import Region
from astromosaic.core.masks import ForegroundTag
from astromosaic.geometry import SkyProjection
from astromosaic.geometry.image import CompositionSpec, LayerPlacement
from astromosaic.pipeline.mosaic import DEFAULT_SKY_BAND
from astromosaic.pipeline.refinement import RefinementSpec
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    default_composition,
)

PANEL_FILES = "Linear panels (*.fits *.fit *.fts *.tif *.tiff *.xisf);;All files (*)"
_OVERRIDES: tuple[ForegroundTag | None, ...] = (None, "mixed", "sky-only")


class _SettingsDialog(QDialog):
    def __init__(self, title: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.form = QFormLayout(self)

    def field(self, label: str, value: object) -> QLineEdit:
        edit = QLineEdit(str(value))
        self.form.addRow(label, edit)
        return edit

    def buttons(self) -> None:
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.form.addRow(buttons)


class ProjectSettings(_SettingsDialog):
    def __init__(self, project: MosaicProject, parent: QWidget) -> None:
        super().__init__("Mosaic settings", parent)
        self.project = project
        spec = project.render
        self.ra = self.field("Right ascension (°)", spec.center[0])
        self.dec = self.field("Declination (°)", spec.center[1])
        self.projection = QComboBox()
        self.projection.addItem("TAN (Gnomonic)", "TAN")
        self.projection.addItem("ZEA (Zenithal equal area)", "ZEA")
        self.projection.setCurrentIndex(self.projection.findData(spec.projection))
        self.form.addRow("Sky projection", self.projection)
        self.output_width = self.field("Width (px)", spec.size[0])
        self.output_height = self.field("Height (px)", spec.size[1])
        self.scale = self.field("Pixel scale (arcsec/px)", spec.scale_arcsec)
        self.rotation = self.field("Rotation (°)", spec.rotation_deg)
        crop = spec.crop
        self.crop = self.field(
            "Crop (x, y, width, height)",
            f"{crop.x}, {crop.y}, {crop.width}, {crop.height}" if crop else "",
        )
        self.filter = self.field("Common filter", project.filter_name or "")
        self.filter.setPlaceholderText(DEFAULT_SKY_BAND)
        self.filter.setToolTip("Assign a known label to panels without a filter or band override.")
        self.assume = QCheckBox("Declare a common surface-brightness scale")
        self.assume.setToolTip("Use this for already-linear panels that share a brightness scale.")
        self.assume.setChecked(project.assume_surface_brightness)
        self.form.addRow(self.assume)
        self.background = QComboBox()
        self.background.addItems(["Disabled", "None", "Offset", "Plane"])
        self.background.setCurrentText(
            project.refinement.background.title() if project.refinement else "Disabled"
        )
        self.form.addRow("Mono refinement background", self.background)
        self.match = self.field(
            "Stellar match radius (px)",
            project.refinement.max_shift_px if project.refinement else 6.0,
        )
        self.buttons()

    def settings(self) -> MosaicProject:
        crop = None
        if self.crop.text().strip():
            fields = self.crop.text().split(",")
            if len(fields) != 4:
                raise ValueError("Enter four comma-separated crop coordinates.")
            crop = Region(*(int(field) for field in fields))
        previous = self.project.render
        projection = cast(SkyProjection, self.projection.currentData())
        spec = replace(
            previous,
            center=(float(self.ra.text()), float(self.dec.text())),
            size=(int(self.output_width.text()), int(self.output_height.text())),
            scale_arcsec=float(self.scale.text()),
            rotation_deg=float(self.rotation.text()),
            crop=crop,
            projection=projection,
        )
        background = self.background.currentText().lower()
        refinement = (
            None
            if background == "disabled"
            else RefinementSpec(
                float(self.match.text()), cast(Literal["none", "offset", "plane"], background)
            )
        )
        project = replace(
            self.project,
            render=spec,
            filter_name=self.filter.text().strip() or None,
            assume_surface_brightness=self.assume.isChecked(),
            refinement=refinement,
            composition=self.project.composition if projection == previous.projection else None,
        )
        project.validate()
        return project


class PanelSettings(_SettingsDialog):
    def __init__(self, panel: ProjectPanel, parent: QWidget) -> None:
        super().__init__("Panel settings", parent)
        self.panel = panel
        self._autofilled: dict[QLineEdit, str] = {}
        source = QLabel()
        source.setTextFormat(Qt.TextFormat.PlainText)
        source.setText(panel.source.path.name)
        self.form.addRow("Source", source)
        self.weight = self.field("Blend weight", panel.weight)
        self.band_override = self.field("Sky band override", panel.band_override or "")
        self.band_override.setToolTip("Assign a saved filter label for this panel's sky samples.")
        self.foreground_override = QComboBox()
        self.foreground_override.addItems(
            ["Use suggestion", "Mixed sky and foreground", "Sky only"]
        )
        self.foreground_override.setCurrentIndex(_OVERRIDES.index(panel.foreground_override))
        self.form.addRow("Foreground tag", self.foreground_override)
        self.include_sky = QCheckBox("Include in sky layer")
        self.include_sky.setToolTip(
            "Clear this to use the panel's foreground while its sky has no solution."
        )
        self.include_sky.setChecked(panel.include_sky)
        self.form.addRow(self.include_sky)
        self.focal_length = self._optical_field("Focal length (mm)", panel.optics.focal_length_mm)
        self.camera_model = QLabel("Not available")
        self.camera_model.setTextFormat(Qt.TextFormat.PlainText)
        self.form.addRow("Camera (metadata)", self.camera_model)
        self.pixel_size_x = self._optical_field(
            "Effective X pixel size (µm)", panel.optics.pixel_size_x_um
        )
        self.pixel_size_y = self._optical_field(
            "Effective Y pixel size (µm)", panel.optics.pixel_size_y_um
        )
        self.wcs = self._attachment("WCS sidecar", panel.wcs_sidecar, "WCS sidecar (*.json)")
        self.sky_mask = self._attachment(
            "FITS sky mask", panel.sky_mask, "FITS image (*.fits *.fit *.fts)"
        )
        self.buttons()

    def _optical_field(self, label: str, value: float | None) -> QLineEdit:
        field = self.field(label, "" if value is None else value)
        if value is None:
            self._autofilled[field] = ""
        field.setToolTip("Enter an override for this panel. Clear it to use embedded metadata.")
        return field

    def show_embedded_optics(self, optics: PanelOptics, camera_model: str | None = None) -> None:
        self.camera_model.setText(camera_model or "Not available")
        for field, value in (
            (self.focal_length, optics.focal_length_mm),
            (self.pixel_size_x, optics.pixel_size_x_um),
            (self.pixel_size_y, optics.pixel_size_y_um),
        ):
            text = format(value, ".9g") if value is not None else ""
            hint = f"{text} (embedded)" if text else "No usable embedded value"
            field.setPlaceholderText(hint)
            field.setToolTip(f"{hint}. Edit to override. Clear to use the file value.")
            if field.text() == self._autofilled.get(field) and not field.isModified():
                field.setText(text)
                self._autofilled[field] = text

    def _optical_override(self, field: QLineEdit) -> float | None:
        entered = field.text().strip()
        if not entered or (entered == self._autofilled.get(field) and not field.isModified()):
            return None
        return float(entered)

    def _attachment(self, label: str, reference: FileReference | None, names: str) -> QLineEdit:
        path = QLineEdit(str(reference.path) if reference else "")
        path.setReadOnly(True)
        browse = QPushButton("Browse…")
        clear = QPushButton("Clear")

        def choose() -> None:
            name, _ = QFileDialog.getOpenFileName(self, label, path.text(), names)
            if name:
                path.setText(name)
                path.setModified(True)

        browse.clicked.connect(choose)
        clear.clicked.connect(path.clear)
        row = QHBoxLayout()
        row.addWidget(path, 1)
        row.addWidget(browse)
        row.addWidget(clear)
        self.form.addRow(label, row)
        return path

    def settings(self) -> ProjectPanel:
        weight = float(self.weight.text())
        if not isfinite(weight) or weight <= 0:
            raise ValueError("Enter a positive finite blend weight.")

        def attachment(edit: QLineEdit, previous: FileReference | None) -> FileReference | None:
            if not edit.text():
                return None
            path = Path(edit.text())
            if previous and previous.path == path and not edit.isModified():
                return previous
            return FileReference.capture(path)

        sky_mask = attachment(self.sky_mask, self.panel.sky_mask)
        optics = PanelOptics(
            self._optical_override(self.focal_length),
            self._optical_override(self.pixel_size_x),
            self._optical_override(self.pixel_size_y),
        )
        return replace(
            self.panel,
            weight=weight,
            wcs_sidecar=attachment(self.wcs, self.panel.wcs_sidecar),
            sky_mask=sky_mask,
            source_mask=None if sky_mask is not None else self.panel.source_mask,
            foreground_override=_OVERRIDES[self.foreground_override.currentIndex()],
            include_sky=self.include_sky.isChecked(),
            optics=optics,
            band_override=self.band_override.text().strip() or None,
        )


class CompositionSettings(_SettingsDialog):
    def __init__(self, project: MosaicProject, parent: QWidget) -> None:
        super().__init__("Composition settings", parent)
        self.project = project
        self.initial = spec = default_composition(project)
        self.x_offset = self.field("Foreground X in sky grid (px)", spec.placement.offset[0])
        self.y_offset = self.field("Foreground Y in sky grid (px)", spec.placement.offset[1])
        self.rotation = self.field("Foreground rotation (°)", spec.placement.rotation_deg)
        self.scale = self.field("Foreground scale", spec.placement.scale)
        self.seam_y = self.field("Seam row in sky grid (px)", spec.seam_y)
        self.overlap = self.field("Overlap (% of shorter layer)", spec.overlap_percent)
        self.crop = self.field("Sky rows to crop from bottom", spec.sky_crop_bottom)
        self.buttons()

    def settings(self) -> CompositionSpec:
        placement = LayerPlacement(
            (float(self.x_offset.text()), float(self.y_offset.text())),
            float(self.rotation.text()),
            float(self.scale.text()),
        )
        seam = float(self.seam_y.text())
        spec = replace(
            self.initial,
            placement=placement,
            seam_y=seam,
            overlap_percent=float(self.overlap.text()),
            sky_crop_bottom=int(self.crop.text()),
        )
        if placement != self.initial.placement or seam != self.initial.seam_y:
            spec = replace(spec, reference_panel=None, placement_rms_px=None)
        sky = self.project.render.output_region()
        ground = self.project.current_foreground()
        if ground is None:
            raise ValueError("Align the current foreground panels first.")
        spec.frame((sky.width, sky.height), (ground.canvas.width, ground.canvas.height))
        return spec
