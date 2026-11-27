"""Dialogs for project geometry, render settings, and panel attachments."""

from dataclasses import replace
from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from astromosaic.astrometry.hints import PanelOptics
from astromosaic.core import Region
from astromosaic.core.masks import ForegroundTag
from astromosaic.geometry import SkyProjection
from astromosaic.geometry.image import CompositionSpec, LayerPlacement
from astromosaic.photometry.background import BackgroundMode
from astromosaic.photometry.photo_settings import (
    BRIGHTNESS_LABELS,
    EXPOSURE_LABELS,
    PROFILE_LABELS,
    BrightnessMode,
    ExposureMode,
    PhotoProfile,
    PhotoSettings,
    ProfileMode,
)
from astromosaic.pipeline.framing import FrameLock
from astromosaic.pipeline.mosaic import DEFAULT_SKY_BAND, RenderSpec
from astromosaic.pipeline.refinement import RefinementSpec
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    default_composition,
    validate_composition,
)
from astromosaic.ui.decimal_input import format_decimal, parse_decimal

PANEL_FILES = "Linear panels (*.fits *.fit *.fts *.tif *.tiff *.xisf);;All files (*)"
_OVERRIDES: tuple[ForegroundTag | None, ...] = (None, "mixed", "sky-only")


class _SettingsDialog(QDialog):
    def __init__(self, title: str, parent: QWidget, *, tab: str | None = None) -> None:
        super().__init__(parent)
        self.setLocale(parent.locale())
        self.setWindowTitle(title)
        self.tabs = None
        self.outer = None
        if tab is None:
            self.form = QFormLayout(self)
        else:
            self.tabs = QTabWidget(self)
            self.outer = QVBoxLayout(self)
            self.outer.addWidget(self.tabs)
            self.form = self.tab_form(tab)

    def tab_form(self, label: str) -> QFormLayout:
        assert self.tabs is not None
        page = QWidget(self.tabs)
        self.tabs.addTab(page, label)
        return QFormLayout(page)

    def field(self, label: str, value: object) -> QLineEdit:
        edit = QLineEdit(self.form.parentWidget())
        edit.setAccessibleName(label)
        edit.setText(format_decimal(value, edit.locale()) if isinstance(value, float) else str(value))
        self.form.addRow(label, edit)
        return edit

    @staticmethod
    def decimal(edit: QLineEdit) -> float:
        try:
            return parse_decimal(edit.text(), edit.locale())
        except ValueError as error:
            raise ValueError(f"{edit.accessibleName()}. {error}") from error

    def buttons(self) -> None:
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        if self.outer is None:
            self.form.addRow(buttons)
        else:
            self.outer.addWidget(buttons)


class _PhotoProfileFields:
    def __init__(
        self, form: QFormLayout, parent: QWidget, profile: PhotoProfile | None, *, inherit: bool
    ) -> None:
        self.previous = profile
        self.mode = QComboBox()
        if inherit:
            self.mode.addItem("Use project profile", "inherit")
        for choice, label in PROFILE_LABELS.items():
            self.mode.addItem(label, choice)
        self.mode.setCurrentIndex(self.mode.findData(profile.mode if profile else "inherit"))
        form.addRow("Input profile", self.mode)
        label = "ICC file"
        self.path = QLineEdit(str(profile.path) if profile is not None and profile.path else "")
        self.path.setReadOnly(True)
        self.path.setAccessibleName(label)
        browse = QPushButton("Browse…")
        browse.setAccessibleName(f"Browse for {label}")

        def choose() -> None:
            name, _ = QFileDialog.getOpenFileName(
                parent, "Assign an ICC profile", self.path.text(), "ICC profiles (*.icc *.icm)"
            )
            if name:
                self.path.setText(name)
                self.path.setModified(True)

        browse.clicked.connect(choose)
        file = QHBoxLayout()
        file.addWidget(self.path, 1)
        file.addWidget(browse)
        form.addRow(label, file)

        def toggle() -> None:
            enabled = self.mode.currentData() == "icc"
            self.path.setEnabled(enabled)
            browse.setEnabled(enabled)

        self.mode.currentIndexChanged.connect(toggle)
        toggle()

    def settings(self) -> PhotoProfile | None:
        mode = self.mode.currentData()
        if mode == "inherit":
            return None
        if mode != "icc":
            return PhotoProfile(cast(ProfileMode, mode))
        if not self.path.text():
            raise ValueError("Choose an ICC file.")
        path = Path(self.path.text())
        if self.previous is not None and self.previous.path == path and not self.path.isModified():
            return self.previous
        return PhotoProfile.capture(path)


class ProjectSettings(_SettingsDialog):
    def __init__(
        self, project: MosaicProject, parent: QWidget, *,
        preview_grid: RenderSpec | None = None,
        suggested_rotation: float | None = None,
        input_metadata: str = "",
    ) -> None:
        super().__init__("Mosaic settings", parent, tab="Sky Grid")
        self.project = project
        self.visible_grid = spec = preview_grid or project.render
        self.auto_frame = QCheckBox("Auto Frame")
        self.auto_frame.setChecked(project.auto_frame_preview)
        self.form.addRow(self.auto_frame)
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
        if suggested_rotation is not None:
            angle = self.locale().toString(suggested_rotation, "f", 1)
            suggestion = QPushButton(f"Use suggested rotation ({angle}°)")
            suggestion.setToolTip("Use a rotation that reduces the fitted footprint's rectangle.")
            suggestion.clicked.connect(lambda: self.rotation.setText(
                format_decimal(suggested_rotation, self.rotation.locale())
            ))
            self.form.addRow(suggestion)
        crop = spec.crop
        self.crop = self.field(
            "Crop (x, y, width, height)",
            f"{crop.x}, {crop.y}, {crop.width}, {crop.height}" if crop else "",
        )
        locks = QHBoxLayout()
        self.locks: dict[FrameLock, QCheckBox] = {}
        fields: tuple[FrameLock, ...] = ("center", "projection", "size", "scale", "crop")
        for field in fields:
            lock = QCheckBox(field.capitalize())
            lock.setAccessibleName(f"Lock {field} for Auto Frame")
            if field == "crop":
                lock.setToolTip("A fixed pixel crop also keeps its full grid size.")
            lock.setChecked(field in project.frame_locks)
            self.locks[field] = lock
            locks.addWidget(lock)
        self.form.addRow("Auto Frame locks", locks)
        self.auto_frame.toggled.connect(self._update_locks)
        self._update_locks(project.auto_frame_preview)
        self.filter = self.field("Common filter", project.filter_name or "")
        self.filter.setPlaceholderText(DEFAULT_SKY_BAND)
        self.filter.setToolTip("Assign a known label to panels without a filter or band override.")
        self.assume = QCheckBox("Declare a common surface-brightness scale")
        self.assume.setToolTip("Use this for already-linear panels that share a brightness scale.")
        self.assume.setChecked(project.assume_surface_brightness)
        if input_metadata:
            metadata = QLabel(input_metadata)
            metadata.setTextFormat(Qt.TextFormat.PlainText)
            metadata.setWordWrap(True)
            self.form.addRow("Selected sky inputs", metadata)
        self.form.addRow(self.assume)
        self.background = QComboBox()
        self.background.addItems(["Disabled", "Auto", "None", "Offset", "Plane"])
        self.background.setToolTip(
            "Auto selects a supported background model using independent overlap samples."
        )
        self.background.setCurrentText(
            project.refinement.background.title() if project.refinement else "Disabled"
        )
        self.form.addRow("Mono refinement background", self.background)
        self.match = self.field(
            "Stellar match radius (px)",
            "Auto" if project.refinement is None or project.refinement.max_shift_px is None
            else project.refinement.max_shift_px,
        )
        self.match.setToolTip("Auto uses qualified WCS errors with a 1–6 output pixel limit.")
        self.match.setEnabled(project.refinement is not None)
        self.background.currentTextChanged.connect(
            lambda value: self.match.setEnabled(value != "Disabled")
        )
        photo = self.tab_form("Photo")
        self.photo_profile = _PhotoProfileFields(
            photo, self, project.photo_settings.profile, inherit=False
        )
        self.photo_exposure = QComboBox()
        for choice, label in EXPOSURE_LABELS.items():
            self.photo_exposure.addItem(label, choice)
        self.photo_exposure.setCurrentIndex(self.photo_exposure.findData(project.photo_settings.exposure))
        self.photo_exposure.setToolTip("Enter manual EV per panel in Panel Settings.")
        photo.addRow("Exposure", self.photo_exposure)
        self.photo_brightness = QComboBox()
        for brightness, label in BRIGHTNESS_LABELS.items():
            self.photo_brightness.addItem(label, brightness)
        self.photo_brightness.setCurrentIndex(
            self.photo_brightness.findData(project.photo_settings.brightness)
        )
        photo.addRow("Brightness matching", self.photo_brightness)
        self.buttons()

    def _update_locks(self, auto_frame: bool) -> None:
        for lock in self.locks.values():
            lock.setEnabled(auto_frame)

    def settings(self) -> MosaicProject:
        crop = None
        if self.crop.text().strip():
            fields = self.crop.text().split(",")
            if len(fields) != 4:
                raise ValueError("Enter four comma-separated crop coordinates.")
            crop = Region(*(int(field) for field in fields))
        previous = self.project.render
        projection = cast(SkyProjection, self.projection.currentData())
        entered = replace(
            previous,
            center=(self.decimal(self.ra), self.decimal(self.dec)),
            size=(int(self.output_width.text()), int(self.output_height.text())),
            scale_arcsec=self.decimal(self.scale),
            rotation_deg=self.decimal(self.rotation),
            crop=crop,
            projection=projection,
        )
        auto_frame = self.auto_frame.isChecked()
        locks: set[FrameLock] = {field for field, box in self.locks.items() if box.isChecked()}
        entered_fields = {
            field for field in self.locks
            if getattr(entered, field if field != "scale" else "scale_arcsec")
            != getattr(self.visible_grid, field if field != "scale" else "scale_arcsec")
        }
        if auto_frame:
            locks.update(entered_fields)
        spec = entered
        if auto_frame:
            spec = replace(
                previous,
                center=entered.center if "center" in locks else previous.center,
                projection=entered.projection if "projection" in locks else previous.projection,
                size=entered.size if "size" in locks or "crop" in locks else previous.size,
                scale_arcsec=entered.scale_arcsec if "scale" in locks else previous.scale_arcsec,
                crop=entered.crop if "crop" in locks else previous.crop,
                rotation_deg=entered.rotation_deg,
            )
            if (
                "crop" not in locks and spec.crop is not None
                and not Region(0, 0, *spec.size).contains(spec.crop)
            ):
                spec = replace(spec, crop=None)
        background = self.background.currentText().lower()
        radius = self.match.text().strip()
        refinement = (
            None
            if background == "disabled"
            else RefinementSpec(
                None if radius.lower() in ("", "auto") else self.decimal(self.match),
                cast(BackgroundMode, background),
            )
        )
        profile = self.photo_profile.settings()
        assert profile is not None
        project = replace(
            self.project,
            render=spec,
            auto_frame_preview=auto_frame,
            frame_locks=frozenset(locks),
            filter_name=self.filter.text().strip() or None,
            assume_surface_brightness=self.assume.isChecked(),
            refinement=refinement,
            photo_settings=PhotoSettings(
                profile,
                cast(ExposureMode, self.photo_exposure.currentData()),
                cast(BrightnessMode, self.photo_brightness.currentData()),
            ),
            composition=self.project.composition if spec == previous else None,
        )
        project.validate()
        return project


class PanelSettings(_SettingsDialog):
    def __init__(self, panel: ProjectPanel, parent: QWidget) -> None:
        super().__init__("Panel settings", parent, tab="Panel")
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
        photo = self.tab_form("Photo")
        self.photo_source_info = QLabel("Checking source metadata…")
        self.photo_source_info.setTextFormat(Qt.TextFormat.PlainText)
        photo.addRow("Source color", self.photo_source_info)
        self.photo_profile = _PhotoProfileFields(photo, self, panel.photo_profile, inherit=True)
        self.photo_ev = QDoubleSpinBox()
        self.photo_ev.setRange(-16, 16)
        self.photo_ev.setDecimals(6)
        self.photo_ev.setSingleStep(0.25)
        self.photo_ev.setValue(panel.photo_ev)
        self.photo_ev.setToolTip("Applies when Mosaic Settings uses Manual EV.")
        photo.addRow("Manual exposure (EV)", self.photo_ev)
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
            text = format_decimal(value, field.locale()) if value is not None else ""
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
        return self.decimal(field)

    def _attachment(self, label: str, reference: FileReference | None, names: str) -> QLineEdit:
        path = QLineEdit(str(reference.path) if reference else "")
        path.setReadOnly(True)
        path.setAccessibleName(label)
        browse = QPushButton("Browse…")
        browse.setAccessibleName(f"Browse for {label}")
        clear = QPushButton("Clear")
        clear.setAccessibleName(f"Clear {label}")

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
        weight = self.decimal(self.weight)
        if weight <= 0:
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
            photo_profile=self.photo_profile.settings(),
            photo_ev=self.panel.photo_ev if self.photo_ev.value() == round(self.panel.photo_ev, 6)
            else self.photo_ev.value(),
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
            (self.decimal(self.x_offset), self.decimal(self.y_offset)),
            self.decimal(self.rotation),
            self.decimal(self.scale),
        )
        seam = self.decimal(self.seam_y)
        spec = replace(
            self.initial,
            placement=placement,
            seam_y=seam,
            overlap_percent=self.decimal(self.overlap),
            sky_crop_bottom=int(self.crop.text()),
        )
        if placement != self.initial.placement or seam != self.initial.seam_y:
            spec = replace(spec, reference_panel=None, placement_rms_px=None)
        validate_composition(self.project, spec)
        return spec
