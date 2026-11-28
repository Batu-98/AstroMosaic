import os
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep
from typing import TYPE_CHECKING

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.io import open_panel
from astromosaic.pipeline.smoke import write_smoke_panel
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    load_project,
    preview_project,
)

if TYPE_CHECKING:
    from astromosaic.ui.project_window import ProjectWindow

_ROOT = Path(__file__).resolve().parents[2] / "data/application-tests"


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    settings = QSettings(str(tmp_path / "phase10.ini"), QSettings.Format.IniFormat)
    settings.setValue("view/liveSkyPreview", False)
    window = ProjectWindow(use_gpu=False, preferences=settings)
    secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
    if secondary is not None:
        window.setScreen(secondary)
        window.move(secondary.availableGeometry().topLeft())
    window.show()
    yield app, window
    window._saved = window.project
    window.close()


def _settle(app, window: "ProjectWindow") -> None:
    limit = monotonic() + 25
    while (
        window.job is not None
        or window._inspection_job is not None
        or window._detail_job is not None
    ):
        app.processEvents()
        assert monotonic() < limit, window.status.text()
        sleep(0.005)
    app.processEvents()


def test_table_filter_preserves_source_identity_and_pins_the_panel(
    workspace,
    tmp_path: Path,
) -> None:
    from PySide6.QtCore import QPoint

    app, window = workspace
    paths = tuple(tmp_path / f"panel-{index}.fits" for index in range(3))
    for path in paths:
        write_smoke_panel(path)
    panels = tuple(ProjectPanel(FileReference.capture(path), band_override="R") for path in paths)
    window._set_project(MosaicProject(panels), None)
    _settle(app, window)
    window.panels.selectRow(0)
    window.filename_filter.setText("-2.fits")
    window.band_filter.setCurrentIndex(window.band_filter.findData("R"))
    window.wcs_filter.setCurrentIndex(window.wcs_filter.findData("Embedded"))
    assert window.panel_heading.text() == "Panels (1/3)"
    assert not window.panels.currentIndex().isValid() and not window.panel_button.isEnabled()
    assert window._selected_panel == paths[0]
    window.panels.selectRow(2)
    weight = window.panels.cell(2, "Weight")
    assert window.panels.properties.setData(weight, "2")
    window.clear_filters_button.click()
    assert [panel.weight for panel in window.project.panels] == [1, 1, 2]
    window.undo_action.trigger()
    assert window.project.panels[2].weight == 1
    window.redo_action.trigger()
    assert window.project.panels[2].weight == 2
    window.table_view.setCurrentText("All properties")
    bar = window.panels.horizontalScrollBar()
    bar.setValue(bar.maximum())
    app.processEvents()
    y = window.panels.rowViewportPosition(2) + 4
    assert window.panels.indexAt(QPoint(10, y)) == window.panels.cell(2, "Panel")
    assert window.panels.visualRect(window.panels.cell(2, "Panel")).left() == 0


def test_solve_summary_reports_required_mask_and_reused_wcs(workspace, tmp_path: Path) -> None:
    app, window = workspace
    paths = tuple(tmp_path / f"panel-{index}.fits" for index in range(2))
    write_smoke_panel(paths[0])
    fits.writeto(paths[1], np.ones((8, 12), dtype=np.float32))
    panels = (
        ProjectPanel(FileReference.capture(paths[0])),
        ProjectPanel(FileReference.capture(paths[1]), foreground_override="mixed"),
    )
    window._set_project(MosaicProject(panels), None)
    _settle(app, window)
    window.plate_solve_button.click()
    _settle(app, window)
    assert "1 reused · 0 solved · 1 failed · 0 unprocessed" in window.solve_summary.text()
    assert "Apply a sky mask" in window.status.text()
    assert window.panels.cell(0, "WCS").data() == "Embedded"
    window._set_project(MosaicProject(), None)
    assert not window.solve_summary.text()


@pytest.mark.parametrize("fixture", ["sky01-m17-atlas", "extended/sky07-wide-sip"])
def test_detector_outlines_follow_sampled_wcs_and_crop(fixture: str) -> None:
    manifest = _ROOT / fixture / "project.astromosaic"
    if not manifest.is_file():
        pytest.skip("Prepare the Phase 10 sky references.")
    project = load_project(manifest)
    spec = replace(project.render, crop=Region(17, 21, 480, 520), rotation_deg=13)
    result = preview_project(
        replace(project, auto_frame_preview=False, render=spec),
        JobContext(),
        adaptive_edge=256,
        allow_visual=True,
    )
    assert len(result.outlines) == 2 and result.output_wcs is not None
    for panel, outline in zip(project.panels, result.outlines, strict=True):
        assert outline.vertices is not None and outline.source == panel.source.path
        with open_panel(panel.source.path) as source:
            width, height = source.descriptor.width, source.descriptor.height
            original = WCS(source.header).celestial
        steps = len(outline.vertices) // 4
        starts = outline.vertices.reshape(4, steps, 2)
        ends = np.roll(outline.vertices, -1, axis=0).reshape(4, steps, 2)
        fractions = np.linspace(0, 1, 1025)
        x = np.array(
            (fractions * width, np.full(1025, width), (1 - fractions) * width, np.zeros(1025))
        )
        y = np.array(
            (np.zeros(1025), fractions * height, np.full(1025, height), (1 - fractions) * height)
        )
        dense = (
            np.stack(
                result.output_wcs.world_to_pixel(original.pixel_to_world(x - 0.5, y - 0.5)), axis=-1
            )
            + 0.5
        )
        section = np.minimum((fractions * steps).astype(int), steps - 1)
        chord = ends[:, section] - starts[:, section]
        distance = dense - starts[:, section]
        projection = np.clip(
            np.sum(distance * chord, axis=-1) / np.sum(chord * chord, axis=-1), 0, 1
        )
        assert np.linalg.norm(distance - projection[..., None] * chord, axis=-1).max() < 0.25


def test_review_keeps_output_and_history_untouched_until_confirmed(
    workspace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtWidgets import QFileDialog

    from astromosaic.ui.export_review import FITS

    app, window = workspace
    manifest = _ROOT / "sky01-m17-atlas/project.astromosaic"
    if not manifest.is_file():
        pytest.skip("Prepare the real M17 reference.")
    project = load_project(manifest)
    crop = Region(7, 9, 68, 56)
    window._set_project(replace(project, render=replace(project.render, crop=crop)), None)
    _settle(app, window)
    revision = window._revision
    capture = []
    destination = tmp_path / "M17"
    attempts = []
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (attempts.pop() if attempts else "", ""),
    )
    monkeypatch.setattr(
        window, "_confirm_export_review", lambda description: capture.append(description)
    )
    window.scientific_export.trigger()
    _settle(app, window)
    assert window.status.text() == "Export review cancelled."
    assert dict(capture[0].fields)["Dimensions"] == "68 × 56 px"
    assert dict(capture[0].fields)["Crop"] == "7, 9 · 68 × 56 px"
    monkeypatch.setattr(window, "_confirm_export_review", lambda _description: FITS)
    window.scientific_export.trigger()
    _settle(app, window)
    assert "destination selection cancelled" in window.status.text()
    assert window._revision == revision and not list(tmp_path.glob("*.fits"))
    attempts.append(str(destination))
    window.scientific_export.trigger()
    _settle(app, window)
    with fits.open(destination.with_suffix(".fits")) as result:
        assert result[0].data.shape == (56, 68) and result["COVERAGE"].data.shape == (56, 68)
        pixels = np.array(((0, 0), (33, 27), (67, 55)))
        np.testing.assert_allclose(WCS(result[0].header).all_pix2world(pixels, 0),
                                   window.project.render.output_wcs().all_pix2world(pixels, 0),
                                   rtol=0, atol=1e-9)
    assert window._revision == revision


def test_actual_size_and_detector_selection_share_the_preview_geometry(workspace) -> None:
    from PySide6.QtCore import QPointF

    app, window = workspace
    manifest = _ROOT / "sky01-m17-atlas/project.astromosaic"
    if not manifest.is_file():
        pytest.skip("Prepare the real M17 reference.")
    window._open_project(manifest)
    _settle(app, window)
    window.preview_button.click()
    _settle(app, window)
    viewport = window.viewport
    assert viewport.frame is not None
    window.panel_outlines.setChecked(True)
    assert len(viewport._outline_paths) == 2
    viewport.actual_size_button.click()
    assert viewport.image_rect().width() * viewport.canvas.devicePixelRatioF() == pytest.approx(
        viewport.frame.output_size[0]
    )
    assert viewport._zoom_readout.text().startswith("100")
    viewport.fit_button.click()
    second = window.project.panels[1].source.path
    center = viewport._outline_paths[second].boundingRect().center()
    size = viewport.frame.output_size
    rect = viewport.image_rect()
    viewport.select_outline(None)
    viewport._pick_outline(QPointF(rect.x() + center.x() * rect.width() / size[0],
                                   rect.y() + center.y() * rect.height() / size[1]))
    assert window._selected_panel == second
    window.filename_filter.setText(window.project.panels[0].source.path.name)
    assert window._selected_panel == second and not window.panels.currentIndex().isValid()
    window.show_panels_button.click()
    assert window.navigation.currentRow() == 0 and "Clear Filters" in window.status.text()
    window.clear_filters_button.click()
    assert window.panels.currentIndex().row() == 1
