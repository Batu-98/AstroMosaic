from pathlib import Path
from xml.etree import ElementTree

import numpy as np
import pytest
import tifffile
from astropy.io import fits

from astromosaic.astrometry.hints import PanelOptics
from astromosaic.core.job import JobContext
from astromosaic.io import open_panel
from astromosaic.storage.project import FileReference, ProjectPanel, inspect_project_panel


def _image(
    path: Path, fields: dict[str, str], header: fits.Header | None = None, *, padding: bytes = b""
) -> None:
    root = ElementTree.Element("metadata")
    for key, value in fields.items():
        namespace = "tiff" if key == "Model" else "exif"
        element = ElementTree.SubElement(root, f"{{http://ns.adobe.com/{namespace}/1.0/}}{key}")
        element.text = value
    xml = ElementTree.tostring(root, encoding="utf-8") + padding
    description = (
        "AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False)
        if header is not None
        else None
    )
    tifffile.imwrite(
        path,
        np.ones((12, 16), dtype=np.uint16),
        metadata=None,
        description=description,
        resolution=(300, 300),
        extratags=[(700, "B", len(xml), xml, False)],
    )


def test_panel_load_reads_standard_xmp_optics_with_units_and_preserves_manual_overrides(
    tmp_path: Path,
) -> None:
    image = tmp_path / "camera.tif"
    _image(
        image,
        {
            "FocalLength": "500/1",
            "FocalLengthIn35mmFilm": "750",
            "FocalPlaneXResolution": "2000/1",
            "FocalPlaneYResolution": "2000/1",
            "FocalPlaneResolutionUnit": "3",
            "Model": "Test camera",
        },
    )
    original = image.read_bytes()
    panel = ProjectPanel(FileReference.capture(image))
    info = inspect_project_panel(panel, JobContext())
    assert info.wcs_status == "Missing"
    assert info.camera_model == "Test camera"
    assert info.embedded_optics == PanelOptics(500, 5, 5)
    assert info.embedded_optics.with_overrides(PanelOptics(600)) == PanelOptics(600, 5, 5)
    with open_panel(image) as source:
        assert "XMP" in source.header.comments["XPIXSZ"]
        assert source.header["FOCALLEN"] == 500
    assert image.read_bytes() == original


@pytest.mark.parametrize("unit,expected", [("2", 12.7), ("3", 5.0), ("1", None), ("4", None)])
def test_only_standard_sensor_resolution_units_produce_pixel_pitch(
    tmp_path: Path,
    unit: str,
    expected: float | None,
) -> None:
    image = tmp_path / "units.tif"
    _image(image, {"FocalPlaneXResolution": "2000", "FocalPlaneResolutionUnit": unit})
    info = inspect_project_panel(ProjectPanel(FileReference.capture(image)), JobContext())
    assert info.embedded_optics.pixel_size_x_um == expected
    assert info.embedded_optics.pixel_size_y_um is None


@pytest.mark.parametrize(
    "change",
    [
        {"PixelXDimension": "32"},
        {"PixelXDimension": "unknown"},
        {"DigitalZoomRatio": "2"},
        {"DigitalZoomRatio": "invalid"},
        {"FocalPlaneXResolution": "1/0"},
    ],
)
def test_bad_or_ambiguous_pixel_grid_does_not_create_a_scale_hint(
    tmp_path: Path,
    change: dict[str, str],
) -> None:
    image = tmp_path / "resampled.tif"
    _image(
        image,
        {
            "FocalLength": "24",
            "FocalPlaneXResolution": "2000",
            "FocalPlaneResolutionUnit": "3",
            **change,
        },
    )
    info = inspect_project_panel(ProjectPanel(FileReference.capture(image)), JobContext())
    assert info.embedded_optics.focal_length_mm == 24
    assert info.embedded_optics.pixel_size_x_um is None


@pytest.mark.parametrize("zoom", ["0/1", "1/1"])
def test_no_digital_zoom_retains_a_valid_pitch(tmp_path: Path, zoom: str) -> None:
    image = tmp_path / "native-grid.tif"
    _image(
        image,
        {
            "DigitalZoomRatio": zoom,
            "FocalPlaneXResolution": "2000",
            "FocalPlaneResolutionUnit": "3",
            "PixelXDimension": "16",
            "PixelYDimension": "12",
        },
    )
    info = inspect_project_panel(ProjectPanel(FileReference.capture(image)), JobContext())
    assert info.embedded_optics.pixel_size_x_um == 5


def test_fits_style_optics_keep_precedence_and_print_dpi_is_never_sensor_pitch(
    tmp_path: Path,
) -> None:
    image = tmp_path / "metadata.tif"
    _image(
        image,
        {"FocalLength": "24", "FocalLengthIn35mmFilm": "36"},
        fits.Header({"FOCALLEN": 100.0, "XPIXSZ": 6.0}),
    )
    info = inspect_project_panel(ProjectPanel(FileReference.capture(image)), JobContext())
    assert info.embedded_optics == PanelOptics(100, 6, None)
    _image(image, {"FocalLengthIn35mmFilm": "36"})
    info = inspect_project_panel(ProjectPanel(FileReference.capture(image)), JobContext())
    assert info.embedded_optics == PanelOptics()


def test_malformed_xmp_leaves_pixels_readable(tmp_path: Path) -> None:
    image = tmp_path / "broken.tif"
    xml = b"<!DOCTYPE metadata><metadata>bad"
    tifffile.imwrite(
        image,
        np.ones((12, 16), dtype=np.uint16),
        metadata=None,
        extratags=[(700, "B", len(xml), xml, False)],
    )
    info = inspect_project_panel(ProjectPanel(FileReference.capture(image)), JobContext())
    assert info.wcs_status == "Missing"
    assert info.embedded_optics == PanelOptics()


def test_invalid_fits_focal_length_uses_padded_xmp(tmp_path: Path) -> None:
    image = tmp_path / "padded-xmp.tif"
    _image(image, {"FocalLength": "24/1"}, fits.Header({"FOCALLEN": -1}), padding=b"\0\0")
    info = inspect_project_panel(ProjectPanel(FileReference.capture(image)), JobContext())
    assert info.embedded_optics == PanelOptics(24)


def test_invalid_optional_camera_text_does_not_invalidate_an_image(tmp_path: Path) -> None:
    image = tmp_path / "numeric-instrument.tif"
    _image(image, {}, fits.Header({"INSTRUME": 42, "FOCALLEN": 24}))
    info = inspect_project_panel(ProjectPanel(FileReference.capture(image)), JobContext())
    assert info.wcs_status == "Missing"
    assert info.camera_model is None
    assert info.embedded_optics.focal_length_mm == 24


def test_panel_settings_displays_imported_camera_and_optical_hints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("PySide6")
    import os

    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget

    from astromosaic.ui.project_settings import PanelSettings

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    image = tmp_path / "camera.tif"
    _image(image, {"FocalLength": "24", "Model": "Test camera"})
    panel = ProjectPanel(FileReference.capture(image))
    info = inspect_project_panel(panel, JobContext())
    parent = QWidget()
    dialog = PanelSettings(panel, parent)
    try:
        dialog.show()
        app.processEvents()
        QTest.keyClicks(dialog.pixel_size_x, "5.5")
        dialog.show_embedded_optics(info.embedded_optics, info.camera_model)
        assert dialog.camera_model.text() == "Test camera"
        assert dialog.focal_length.text() == "24"
        assert dialog.pixel_size_x.text() == "5.5"
        assert dialog.settings().optics == PanelOptics(pixel_size_x_um=5.5)
        dialog.focal_length.selectAll()
        QTest.keyClicks(dialog.focal_length, "50")
        dialog.show_embedded_optics(info.embedded_optics, info.camera_model)
        assert dialog.focal_length.text() == "50"
        assert dialog.settings().optics == PanelOptics(50, 5.5)
        dialog.focal_length.clear()
        dialog.pixel_size_x.clear()
        assert dialog.focal_length.placeholderText() == "24 (embedded)"
        assert dialog.settings().optics == PanelOptics()
    finally:
        dialog.close()
        parent.close()
