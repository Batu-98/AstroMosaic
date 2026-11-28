"""Exercise frozen desktop jobs with test data and no visible windows."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from hashlib import file_digest
from multiprocessing import freeze_support
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import patch

import numpy as np
import tifffile
from astropy.io import fits
from astropy.wcs import WCS
from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QPalette
from PySide6.QtWidgets import QApplication, QFileDialog
from scipy.ndimage import gaussian_filter

from astromosaic.astrometry import astap_probe
from astromosaic.astrometry.solve import SolveOptions, SolverAttempt, SolveResult, write_solution
from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.core.masks import FOREGROUND, SKY, UNCLASSIFIED, SourceMask
from astromosaic.display import normalize_tile
from astromosaic.geometry import read_panel_geometry, tan_output_wcs
from astromosaic.io import open_panel
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.storage.project import (
    FileReference,
    Layer,
    MosaicProject,
    ProjectPanel,
    load_project,
    preview_project_layer,
    save_project,
)
from astromosaic.ui import plate_solve_settings
from astromosaic.ui.plate_solve_settings import PlateSolveSettings
from astromosaic.ui.preview_gl import OpenGLPreview
from astromosaic.ui.project_settings import CompositionSettings, ProjectSettings
from astromosaic.ui.project_window import ProjectWindow


def make_project(directory: Path) -> tuple[Path, Path]:
    size, shift = (96, 72), (35, 5)
    width, height = size
    rng = np.random.default_rng(271)
    field = gaussian_filter(rng.normal(size=(height + shift[1], width + shift[0])), 1.45)
    spec = RenderSpec((359.999, 25.0), size, 2.0, tile_size=24)
    panels = []
    source = directory / "ground.tiff"
    for index, (x, y) in enumerate(((0, 0), shift)):
        columns = x + np.arange(width)
        rows = (y + np.arange(height))[:, None]
        horizon = height // 2 + (columns // 9) % 5 - 2
        labels = np.where(
            rows < horizon - 1, SKY, np.where(rows >= horizon + 1, FOREGROUND, UNCLASSIFIED)
        )
        mask = SourceMask(size, labels.astype(np.uint8).tobytes())
        samples = field[y : y + height, x : x + width].astype(np.float32)
        sky = labels == SKY
        samples[sky] = 4 + rng.normal(size=int(sky.sum())).astype(np.float32)
        samples[2, 3] = np.nan
        if index == 0:
            header = tan_output_wcs(
                spec.center, size, spec.scale_arcsec, 0, spec.output_region()
            ).to_header()
            header["FILTER"], header["BUNIT"] = "L", "MJy/sr"
            path = directory / "mixed.fits"
            fits.writeto(path, samples, header)
        else:
            header = fits.Header({"FILTER": "L", "BUNIT": "MJy/sr"})
            path = source
            tifffile.imwrite(
                path,
                samples,
                photometric="minisblack",
                tile=(16, 16),
                compression="deflate",
                predictor=3,
                metadata=None,
                description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False),
            )
        panels.append(
            ProjectPanel(FileReference.capture(path), source_mask=mask, include_sky=index == 0)
        )
    manifest = directory / "Mixed.astromosaic"
    save_project(manifest, MosaicProject(tuple(panels), render=spec))
    return manifest, source.rename(directory / "Moved ground.tiff")


def wait_for(
    window: ProjectWindow, condition: Callable[[], bool], timeout_ms: int = 15_000
) -> None:
    if condition():
        return
    loop = QEventLoop()
    poll, timeout = QTimer(), QTimer()
    poll.timeout.connect(lambda: loop.quit() if condition() else None)
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    poll.start(10)
    timeout.start(timeout_ms)
    loop.exec()
    poll.stop()
    timeout.stop()
    if not condition():
        raise TimeoutError(f"Desktop check timed out. Last status: {window.status.text()}")


def export(window: ProjectWindow, destination: Path) -> None:
    from astromosaic.ui.export_review import FITS, TIFF, XISF

    output = next(item for item in (FITS, TIFF, XISF) if destination.suffix.lower() in item.suffixes)
    with (
        patch.object(QFileDialog, "getSaveFileName", return_value=(str(destination), "")),
        patch.object(window, "_confirm_export_review", return_value=output),
    ):
        window.start_button.click()
        wait_for(window, lambda: window.job is None)


def check_layer(window: ProjectWindow, directory: Path, layer: Layer, backend: str) -> int:
    window.layer_box.setCurrentText(layer.capitalize())
    window.preview_button.click()
    wait_for(window, lambda: window.job is None)
    frame = window.viewport.frame
    assert frame is not None and frame.has_coverage, window.status.text()
    assert window.viewport.backend == backend
    canvas = window.viewport.canvas
    if isinstance(canvas, OpenGLPreview):
        assert canvas.isValid() and not canvas.grabFramebuffer().isNull()
    else:
        assert not canvas.grab().isNull()
    if layer == "composition":
        assert frame.common_coverage is not None and np.any(frame.common_coverage)
        window.overlap_check.setChecked(True)
        shown = window.viewport.frame
        assert shown is not None and not np.array_equal(shown.rgba, frame.rgba)
        window.overlap_check.setChecked(False)

    path = directory / (layer + (".fits" if layer == "sky" else ".tiff"))
    export(window, path)
    wait_for(window, lambda: window.job is None)
    assert window.status.text().startswith(f"Saved {path.name}"), window.status.text()
    reference = preview_project_layer(window.project, layer, JobContext())
    assert reference.output_size == frame.size  # This fixture fits at full preview resolution.
    with open_panel(path) as reopened:
        tile = reopened.read_tile(Region(0, 0, *reference.output_size))
        np.testing.assert_array_equal(tile.pixels, reference.tile.pixels)
        np.testing.assert_array_equal(tile.valid, reference.tile.valid)
        np.testing.assert_array_equal(normalize_tile(tile, frame.size).rgba, frame.rgba)
        assert (reopened.descriptor.wcs_provenance is not None) == (layer == "sky")
        if reference.output_wcs is not None:
            np.testing.assert_allclose(
                WCS(reopened.header).pixel_to_world_values([0, 48, 95], [0, 36, 71]),
                reference.output_wcs.pixel_to_world_values([0, 48, 95], [0, 36, 71]),
                rtol=0,
                atol=1e-9,
            )
    if layer == "composition":
        with tifffile.TiffFile(path) as tiff:
            page = tiff.pages[0]
            assert isinstance(page, tifffile.TiffPage) and page.pages is not None
            mask = page.pages[1].asarray()
            assert set(np.unique(mask)) == {0, 1, 2, 3}
            np.testing.assert_array_equal(mask > 0, tile.valid)
    return int(tile.valid.sum())


def check_project(window: ProjectWindow, directory: Path, backend: str) -> dict[Layer, int]:
    manifest, moved = make_project(directory)
    _, open_action, save_action, _ = window._file_actions

    def open_project(path: Path) -> None:
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(path), "")):
            open_action.trigger()
        assert window.status.text() == f"Opened {path.name}.", window.status.text()

    open_project(manifest)
    assert "Source missing" in window.panels.cell(1, "Link").data()
    assert window.panels.cell(1, "WCS").data() == "Unavailable"
    window.panels.selectRow(1)
    with patch.object(QFileDialog, "getOpenFileName", return_value=(str(moved), "")):
        window.relink_action.trigger()
    assert "Linked" in window.panels.cell(1, "Link").data()
    assert window.project.panels[1].source.path == moved
    wait_for(window, lambda: window._inspection_job is None)
    assert window.panels.cell(0, "WCS").data() == "Embedded"
    assert window.panels.cell(1, "WCS").data() == "Missing"

    snapshot = manifest.read_bytes()
    with (
        patch.object(Path, "replace", side_effect=PermissionError("Test publication failure")),
        patch.object(window, "_error") as error,
    ):
        save_action.trigger()
        error.assert_called_once()
    assert manifest.read_bytes() == snapshot and not list(directory.glob("*.part"))

    window.align_action.trigger()
    wait_for(window, lambda: window.job is None)
    alignment = window.project.current_foreground()
    assert alignment is not None and alignment.panels[1].shift == (35.0, 5.0)
    window.placement_action.trigger()
    wait_for(window, lambda: window.job is None)
    proposal = window.project.composition
    assert proposal is not None and proposal.reference_panel == 0

    def accept_settings(dialog: CompositionSettings) -> int:
        dialog.x_offset.setText("2")
        dialog.y_offset.setText("24")
        dialog.seam_y.setText("32")
        dialog.overlap.setText("26")
        dialog.crop.setText("20")
        return 1

    with patch.object(CompositionSettings, "exec", accept_settings):
        window.composition_action.trigger()
    composition = window.project.composition
    assert composition is not None and composition.sky_crop_bottom == 20
    assert composition.overlap_percent == 26 and composition.placement.offset == (2.0, 24.0)
    save_action.trigger()
    assert load_project(manifest) == window.project
    open_project(manifest)
    assert window.project.composition == composition

    layers: tuple[Layer, ...] = ("sky", "foreground", "composition")
    covered = {layer: check_layer(window, directory, layer, backend) for layer in layers}

    slow = directory / "Cancel.astromosaic"
    large = replace(window.project.render, size=(1536, 1024), tile_size=16)
    save_project(slow, replace(window.project, render=large))
    window.layer_box.setCurrentText("Sky")
    open_project(slow)
    destination = directory / "cancelled.fits"
    export(window, destination)
    wait_for(window, lambda: window.status.text().startswith("Rendering "))
    assert list(directory.glob("*.part")) and not destination.exists()
    assert window.cancel_button.isEnabled() and window.job is not None
    window.cancel_button.click()
    wait_for(window, lambda: window.job is None)
    assert window.status.text() == "Mosaic cancelled.", window.status.text()
    assert not destination.exists() and not list(directory.glob("*.part"))
    open_project(manifest)
    export(window, destination)
    wait_for(window, lambda: window.job is None)
    assert destination.is_file() and window.progress.value() == 100
    assert window.project.composition == composition
    return covered


def check_zea(window: ProjectWindow, directory: Path, backend: str) -> int:
    previous = window.project
    assert previous.composition is not None

    def select_projection(dialog: ProjectSettings) -> int:
        assert dialog.projection.currentData() == "TAN"
        dialog.projection.setCurrentIndex(dialog.projection.findData("ZEA"))
        return 1

    window.layer_box.setCurrentText("Sky")
    with patch.object(ProjectSettings, "exec", select_projection):
        window.settings_button.click()
    assert window.project.render.projection == "ZEA"
    assert window.project.composition is None and window.project.foreground == previous.foreground
    assert "ICRS ZEA" in window.grid_summary.text()
    manifest = directory / "Saved equal area grid.astromosaic"
    _, open_action, _, save_as = window._file_actions
    with patch.object(QFileDialog, "getSaveFileName", return_value=(str(manifest), "")):
        save_as.trigger()
    with patch.object(QFileDialog, "getOpenFileName", return_value=(str(manifest), "")):
        open_action.trigger()
    assert window.status.text() == f"Opened {manifest.name}.", window.status.text()
    assert window.project.render.projection == "ZEA"

    window.preview_button.click()
    wait_for(window, lambda: window.job is None)
    frame = window.viewport.frame
    assert frame is not None and frame.has_coverage, window.status.text()
    assert window.viewport.backend == backend
    destination = directory / "Equal area sky.fits"
    export(window, destination)
    wait_for(window, lambda: window.job is None)
    reference = preview_project_layer(window.project, "sky", JobContext())
    with open_panel(destination) as reopened:
        assert reopened.header["CTYPE1"] == "RA---ZEA"
        tile = reopened.read_tile(reference.tile.region)
        np.testing.assert_array_equal(tile.pixels, reference.tile.pixels)
        np.testing.assert_array_equal(tile.valid, reference.tile.valid)
        np.testing.assert_array_equal(normalize_tile(tile, frame.size).rgba, frame.rgba)
    return int(reference.tile.valid.sum())


def check_xisf(window: ProjectWindow, directory: Path, backend: str) -> int:
    from astromosaic.ui.export_review import XISF

    project = window.project
    window.layer_box.setCurrentText("Sky")
    reference = preview_project_layer(project, "sky", JobContext())
    destination = directory / "Interchange sky.xisf"
    with (
        patch.object(QFileDialog, "getSaveFileName",
                     return_value=(str(destination.with_suffix("")), "")) as dialog,
        patch.object(window, "_confirm_export_review", return_value=XISF),
    ):
        window.start_button.click()
        wait_for(window, lambda: window.job is None)
        assert "*.xisf" in dialog.call_args.args[-1]
    wait_for(window, lambda: window.job is None)
    assert destination.is_file(), window.status.text()

    window._set_project(MosaicProject(render=project.render), None)
    with patch.object(
        QFileDialog, "getOpenFileNames", return_value=([str(destination)], "")
    ) as dialog:
        window.add_button.click()
        assert "*.xisf" in dialog.call_args.args[-1]
    wait_for(window, lambda: window.job is None and window._inspection_job is None)
    assert window.panels.cell(0, "WCS").data() == "Embedded"
    panel = replace(window.project.panels[0], foreground_override="sky-only")
    window._set_project(replace(window.project, panels=(panel,)), None)
    window.preview_button.click()
    wait_for(window, lambda: window.job is None)
    frame = window.viewport.frame
    assert frame is not None and frame.has_coverage, window.status.text()
    assert window.viewport.backend == backend
    np.testing.assert_array_equal(frame.rgba, normalize_tile(reference.tile, frame.size).rgba)
    return int(reference.tile.valid.sum())


def check_bands(window: ProjectWindow, directory: Path, backend: str) -> int:
    spec = RenderSpec((359.999, 20.0), (16, 12), 7.2, projection="ZEA")
    header = spec.output_wcs().to_header()
    first, second = directory / "H-alpha panel.fits", directory / "O III panel.fits"
    expected = np.arange(192, dtype=np.float32).reshape(12, 16) - 30
    expected[5, 3] = np.nan
    header["FILTER"], header["BUNIT"] = "H-alpha", "MJy/sr"
    fits.writeto(first, -2 * expected, header)
    del header["FILTER"]
    header["BUNIT"] = "Jy/sr"
    fits.writeto(second, expected, header)
    project = MosaicProject(
        tuple(ProjectPanel(FileReference.capture(p)) for p in (first, second)), spec
    )
    window._set_project(project, None)
    wait_for(window, lambda: window._inspection_job is None)
    window.panels.selectRow(1)

    window.table_view.setCurrentText("All properties")
    assert window.panels.cell(1, "Size (px)").data() == "16 × 12"
    assert window.panels.properties.setData(window.panels.cell(1, "Band"), "O III")
    assert window.project.panels[1].band_override == "O III"
    manifest = directory / "Saved band selection.astromosaic"
    _, open_action, _, save_as = window._file_actions
    with patch.object(QFileDialog, "getSaveFileName", return_value=(str(manifest), "")):
        save_as.trigger()
    with patch.object(QFileDialog, "getOpenFileName", return_value=(str(manifest), "")):
        open_action.trigger()
    wait_for(window, lambda: window._inspection_job is None)
    assert window.project.panels[1].band_override == "O III"
    window.layer_box.setCurrentText("Sky")
    assert not window.start_button.isEnabled()
    window.band_box.setCurrentIndex(window.band_box.findData("O III"))
    assert window.start_button.isEnabled() and "O III" in window.grid_summary.text()
    window.preview_button.click()
    wait_for(window, lambda: window.job is None)
    frame = window.viewport.frame
    assert frame is not None and frame.has_coverage, window.status.text()
    assert window.viewport.backend == backend
    destination = directory / "O III from desktop.fits"
    export(window, destination)
    wait_for(window, lambda: window.job is None)
    with open_panel(destination) as reopened:
        tile = reopened.read_tile(Region(0, 0, *spec.size))
        assert reopened.descriptor.filter_name == "O III" and reopened.descriptor.unit == "Jy/sr"
        assert reopened.header["CTYPE1"] == "RA---ZEA"
        np.testing.assert_array_equal(tile.pixels, expected)
        np.testing.assert_array_equal(tile.valid, np.isfinite(expected))
        np.testing.assert_array_equal(normalize_tile(tile, frame.size).rgba, frame.rgba)
    return int(tile.valid.sum())


def check_commands(window: ProjectWindow, directory: Path) -> dict[str, object]:
    manifest = directory / "Mixed.astromosaic"
    window._set_project(load_project(manifest), manifest)
    panel = window.command_panel
    if not panel.isVisible():
        if window.command_toggle.isVisible():
            window.command_toggle.click()
        else:
            window.command_panel_action.setChecked(True)
    assert panel.isVisible() and window.command_panel_action.isChecked()
    assert panel.directory_field.text() == str(directory)

    def start(command: str) -> None:
        panel.entry.setText(command)
        panel.run_button.click()
        assert panel.is_running and not window.start_button.isEnabled()

    def result() -> dict[str, object]:
        wait_for(window, lambda: not panel.is_running)
        lines = panel.output.toPlainText().splitlines()
        return dict(json.loads(next(line for line in reversed(lines) if line.startswith("{"))))

    start("smoke --spawn")
    assert result()["spawned"] is True

    start('project validate "Mixed.astromosaic" --json')
    checked = result()
    assert checked["schema_version"] == 1 and checked["status"] == "ok"
    assert checked["panels"] == 1 and checked["width"] == 96

    cancelled = directory / "command interrupted.fits"
    slow = 'project export "Cancel.astromosaic" -o "command interrupted.fits" --json --progress'
    start(slow)
    wait_for(window, lambda: panel.status.text().startswith("Rendering "))
    assert list(directory.glob("*.part")) and not cancelled.exists()
    window.cancel_button.click()
    assert result()["status"] == "cancelled" and "130" in panel.status.text()
    assert not cancelled.exists() and not list(directory.glob("*.part"))

    for layer, output in (("sky", "sky.fits"), ("composition", "composition.tiff")):
        destination = f"command {output}"
        start(f'project export "{manifest.name}" -o "{destination}" --layer {layer} --json')
        exported = result()
        assert exported["status"] == "ok" and exported["layer"] == layer
        assert (directory / destination).read_bytes() == (directory / output).read_bytes()
    assert panel.progress.value() == 100 and window.start_button.isEnabled()
    return {"validation": True, "cancelled": True, "matching_layers": ["sky", "composition"]}


def check_solver_settings(window: ProjectWindow, directory: Path) -> None:
    settings_file = directory / "settings.ini"
    missing_catalog = directory / "moved-stars.bin"

    def edit(dialog: PlateSolveSettings) -> int:
        dialog.gaia_catalog.setText(str(missing_catalog))
        dialog.astap.setText(str(directory / "moved-astap.exe"))
        dialog.astap_catalog.setText(str(directory))
        dialog.astap_database.setCurrentText("D50")
        dialog.check_button.click()
        try:
            wait_for(window, dialog.save_button.isEnabled)
            assert "catalog is missing" in dialog.message.text(), dialog.message.text()
            assert "ASTAP executable is missing" in dialog.message.text()
            dialog.save_button.click()
            return dialog.result()
        finally:
            if dialog._job is not None:
                dialog._job.cancel()
                assert dialog._job.wait(15_000)

    with (
        patch.object(
            plate_solve_settings,
            "_settings",
            side_effect=lambda: QSettings(str(settings_file), QSettings.Format.IniFormat),
        ),
        patch.object(PlateSolveSettings, "exec", edit),
    ):
        window.plate_solve_settings_action.trigger()
        assert window.status.text() == "Saved local plate solve settings."
        options = plate_solve_settings.load_plate_solve_settings()
        assert options.gaia_catalog == missing_catalog and options.astap_database == "d50"


def check_plate_solve(window: ProjectWindow, directory: Path, fixtures: Path) -> dict[str, str]:
    directory.mkdir()
    center, size, scale = (250.42, 36.46), (32, 24), 1.0069
    spec = RenderSpec(center, size, scale)
    metadata = fits.Header({"FILTER": "L", "BUNIT": "ADU"})
    embedded = tan_output_wcs(center, size, scale, 0, spec.output_region()).to_header()
    sky_ready, reuse, ground = (
        directory / name for name in ("sky.fits", "reuse.fits", "ground.fits")
    )
    for path, header in ((sky_ready, embedded + metadata), (reuse, metadata), (ground, metadata)):
        fits.writeto(path, np.full((size[1], size[0]), 10.0, dtype=np.float32), header)

    reuse_path = directory / "reusable.wcs.json"
    with open_panel(reuse) as opened:
        solution = SolveResult(
            read_panel_geometry(embedded, *size),
            "existing-wcs",
            (SolverAttempt("existing-wcs", "solved", "Reference WCS"),),
        )
        write_solution(reuse_path, opened, solution)

    gaia_input, astap_input, retry_input = (
        directory / name for name in ("gaia-m13.fits", "astap-m13.fits", "retry-m13.fits")
    )
    fixture = fixtures / "phase2-solve-evidence/m13-primary.fits"
    with fits.open(fixture, memmap=False) as hdus:
        pixels = hdus[0].data
    for path in (gaia_input, astap_input, retry_input):
        header = metadata.copy()
        header["RA"], header["DEC"] = (60.0, 0.0) if path == retry_input else center
        header["PIXSCALE"] = scale * 2 if path == retry_input else scale
        fits.writeto(path, pixels, header)

    def digest(path: Path) -> bytes:
        with path.open("rb") as stream:
            return file_digest(stream, "sha256").digest()

    originals = {
        path: digest(path)
        for path in (sky_ready, reuse, ground, gaia_input, astap_input, retry_input, reuse_path)
    }
    options = SolveOptions(
        gaia_catalog=fixtures / "phase2-gaia/stars-gaia.bin",
        astap=fixtures / "astap/cli/astap_cli.exe",
        astap_catalog=fixtures / "astap/catalog",
    )
    reused = FileReference.capture(reuse_path)
    initial = MosaicProject(
        (
            ProjectPanel(FileReference.capture(sky_ready)),
            ProjectPanel(FileReference.capture(reuse), wcs_sidecar=reused),
            ProjectPanel(FileReference.capture(ground), include_sky=False),
            ProjectPanel(FileReference.capture(gaia_input)),
        ),
        render=spec,
        assume_surface_brightness=True,
    )
    manifest = directory / "Solve.astromosaic"
    save_project(manifest, initial)
    window._set_project(load_project(manifest), manifest)
    window.layer_box.setCurrentText("Sky")

    def result(index: int) -> dict[str, object]:
        reference = window.project.panels[index].wcs_sidecar
        assert reference is not None, window.panels.cell(index, "Solve result").data(
            Qt.ItemDataRole.ToolTipRole
        )
        return json.loads(reference.path.read_text(encoding="utf-8"))

    def solve_and_wait() -> None:
        window.plate_solve_button.click()
        assert window.job is not None
        wait_for(window, lambda: window.job is None, 65_000)

    settings_file = directory / "solver-settings.ini"
    with patch.object(
        plate_solve_settings,
        "_settings",
        side_effect=lambda: QSettings(str(settings_file), QSettings.Format.IniFormat),
    ):
        plate_solve_settings._save_plate_solve_settings(
            replace(options, astap=None, astap_catalog=None)
        )
        solve_and_wait()
        assert result(3)["stage"] == "gaia-dr3"
        assert result(3)["version"] == 2
        assert window.project.panels[0].wcs_sidecar is None
        assert window.project.panels[1].wcs_sidecar == reused
        assert window.project.panels[2].wcs_sidecar is None
        assert window.status.text() == "Plate solve finished. 1 solved, 0 failed."

        window.project = replace(
            window.project,
            panels=window.project.panels
            + tuple(
                ProjectPanel(FileReference.capture(path)) for path in (astap_input, retry_input)
            ),
        )
        window._refresh()
        plate_solve_settings._save_plate_solve_settings(replace(options, gaia_catalog=None))
        paused, release = Event(), Event()
        processes: list[subprocess.Popen[str]] = []
        original_wait = astap_probe._wait_for_astap

        def pause_second(
            process: subprocess.Popen[str], timeout: float, context: JobContext
        ) -> str:
            if "-f" not in process.args:
                return original_wait(process, timeout, context)
            processes.append(process)
            if len(processes) == 2:
                paused.set()
                while not release.wait(0.01):
                    context.check_cancelled()
                context.check_cancelled()
            return original_wait(process, timeout, context)

        with (
            patch.object(astap_probe, "_wait_for_astap", pause_second),
            patch.object(
                astap_probe,
                "TemporaryDirectory",
                side_effect=lambda **kwargs: TemporaryDirectory(dir=directory, **kwargs),
            ),
        ):
            try:
                window.plate_solve_button.click()
                wait_for(window, paused.is_set, 40_000)
                window.cancel_button.click()
                wait_for(window, lambda: window.job is None)
            finally:
                release.set()
        assert window.status.text() == "Plate solve cancelled. 1 solved, 0 failed."
        first_astap = window.project.panels[4].wcs_sidecar
        assert result(4)["stage"] == "astap-hinted"
        assert window.project.panels[5].wcs_sidecar is None
        assert len(processes) == 2 and all(process.poll() is not None for process in processes)
        assert not list(directory.glob("astromosaic-astap-*"))

        plate_solve_settings._save_plate_solve_settings(
            replace(
                options,
                astap_catalog=directory / "missing-catalog",
                gaia_catalog=fixtures / "phase2-gaia/stars-deep-gaia17.bin",
                gaia_index=fixtures / "phase2-gaia/blind-gaia16.idx",
            )
        )
        solve_and_wait()
        fallback = result(5)
        assert fallback["stage"] == "gaia-dr3", window.panels.cell(5, "Solve result").data(
            Qt.ItemDataRole.ToolTipRole
        )
        attempts = fallback["attempts"]
        assert isinstance(attempts, list)
        assert (attempts[1]["stage"], attempts[1]["outcome"]) == ("astap-hinted", "skipped")
        assert attempts[-1]["method"] == "blind" and attempts[-1]["effective_position_deg"] is None
        assert window.project.panels[4].wcs_sidecar == first_astap
        assert len(list(directory.rglob("panel-*.wcs.json"))) == 3

    assert window._save()
    reopened = load_project(manifest)
    assert reopened == window.project
    window._set_project(reopened, manifest)
    window.preview_button.click()
    wait_for(window, lambda: window.job is None)
    assert window.viewport.frame is not None, window.status.text()
    exported = directory / "solved-mosaic.fits"
    export(window, exported)
    wait_for(window, lambda: window.job is None)
    with fits.open(exported) as hdus:
        assert np.any(hdus[1].data > 0)
        assert any("astap-hinted WCS sidecar" in entry for entry in hdus[0].header["HISTORY"])
    assert all(digest(path) == expected for path, expected in originals.items())
    assert not list(directory.rglob("*.part"))
    return {"gaia": "gaia-dr3", "astap": "astap-hinted", "fallback": "gaia-dr3"}


def frozen_check(backend: str, solve_fixtures: Path | None) -> None:
    runtime = Path(sys.executable).parent / "_internal"
    assert Path(sys._MEIPASS).resolve() == runtime.resolve()  # type: ignore[attr-defined]
    app = QApplication([sys.argv[0]])
    app.setQuitOnLastWindowClosed(False)
    platform = "offscreen" if backend == "CPU" else "windows"
    assert app.platformName() == platform
    preferences = QSettings(str(Path.cwd() / "appearance.ini"), QSettings.Format.IniFormat)
    window = ProjectWindow(preferences=preferences)
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    window.show()
    try:
        for name in ("Dark", "Light", "Dark"):
            next(a for a in window.findChildren(QAction) if a.text() == name).trigger()
            base = window.panels.viewport().palette().color(QPalette.ColorRole.Base)
            assert (base.lightness() < 128) == (name == "Dark")
        check_solver_settings(window, Path.cwd())
        covered = check_project(window, Path.cwd(), backend)
        plate_solve = (
            check_plate_solve(window, Path.cwd() / "solver", solve_fixtures)
            if solve_fixtures is not None
            else None
        )
        commands = check_commands(window, Path.cwd())
        zea = check_zea(window, Path.cwd(), backend)
        mixed = Path.cwd() / "Mixed.astromosaic"
        window._set_project(load_project(mixed), mixed)
        xisf = check_xisf(window, Path.cwd(), backend)
        band = check_bands(window, Path.cwd(), backend)
        print(
            json.dumps(
                {
                    "backend": backend,
                    "platform": platform,
                    "covered_pixels": covered,
                    "recovery": True,
                    "cancel_and_retry": True,
                    "solver_settings": True,
                    "plate_solve": plate_solve,
                    "command_panel": commands,
                    "xisf_covered_pixels": xisf,
                    "zea_covered_pixels": zea,
                    "band_covered_pixels": band,
                }
            )
        )
    finally:
        panel = window.command_panel
        panel.cancel()
        wait_for(window, lambda: not panel.is_running)
        for job in (window.job, window._inspection_job):
            if job is not None:
                job.cancel()
                assert job.wait(15_000)
        window.hide()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def check_bundle(bundle: Path, probe: Path, backend: str, solve_fixtures: Path | None) -> None:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("PYTHON", "QT_", "CONDA", "VIRTUAL_ENV", "_PYI_"))
    }
    windows = Path(os.environ["SystemRoot"])
    env["PATH"] = f"{windows / 'System32'};{windows}"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["QT_QPA_PLATFORM"] = "offscreen" if backend == "CPU" else "windows"
    with TemporaryDirectory(prefix="AstroMosaic desktop check ") as folder:
        working = Path(folder)
        copied = working / "runtime"
        shutil.copytree(bundle, copied)
        check = copied / "astromosaic-desktop-check.exe"
        shutil.copy2(probe, check)
        command = [str(check), "--backend", backend]
        if solve_fixtures is not None:
            command.extend(("--solve-fixtures", str(solve_fixtures.resolve())))
        result = subprocess.run(
            command,
            cwd=working,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=150 if solve_fixtures is not None else 90,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        report = json.loads(result.stdout)
        assert report["backend"] == backend
        assert report["recovery"] and report["cancel_and_retry"] and report["solver_settings"]
        assert report["command_panel"]["matching_layers"] == ["sky", "composition"]
        assert report["xisf_covered_pixels"] == report["covered_pixels"]["sky"]
        assert report["zea_covered_pixels"] > 0
        assert report["band_covered_pixels"] == 191
        if solve_fixtures is not None:
            assert report["plate_solve"]["fallback"] == "gaia-dr3"
        print(result.stdout.strip())


if __name__ == "__main__":
    freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    frozen = getattr(sys, "frozen", False)
    parser.add_argument("--backend", choices=("CPU", "OpenGL"), default="CPU")
    parser.add_argument("--solve-fixtures", type=Path, help="Local Phase 2 fixture directory.")
    if not frozen:
        parser.add_argument("bundle", type=Path)
        parser.add_argument("probe", type=Path)
    args = parser.parse_args()
    if frozen:
        frozen_check(args.backend, args.solve_fixtures)
    else:
        check_bundle(args.bundle, args.probe, args.backend, args.solve_fixtures)
