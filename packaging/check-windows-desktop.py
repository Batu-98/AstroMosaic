"""Exercise frozen desktop jobs with test data and no visible windows."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import tifffile
from astropy.io import fits
from astropy.wcs import WCS
from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QSettings, Qt, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog
from scipy.ndimage import gaussian_filter

from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.core.masks import FOREGROUND, SKY, UNCLASSIFIED, SourceMask
from astromosaic.display import normalize_tile
from astromosaic.geometry import tan_output_wcs
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
from astromosaic.ui.project_settings import CompositionSettings
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


def wait_for(window: ProjectWindow, condition: Callable[[], bool]) -> None:
    if condition():
        return
    loop = QEventLoop()
    poll, timeout = QTimer(), QTimer()
    poll.timeout.connect(lambda: loop.quit() if condition() else None)
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    poll.start(10)
    timeout.start(15_000)
    loop.exec()
    poll.stop()
    timeout.stop()
    if not condition():
        raise TimeoutError(f"Desktop check timed out. Last status: {window.status.text()}")


def export(window: ProjectWindow, destination: Path) -> None:
    with patch.object(QFileDialog, "getSaveFileName", return_value=(str(destination), "")):
        window.start_button.click()
    assert window.job is not None, window.status.text()


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
    assert "Source missing" in window.panels.item(1).text()
    assert "WCS Unavailable" in window.panels.item(1).text()
    window.panels.setCurrentRow(1)
    with patch.object(QFileDialog, "getOpenFileName", return_value=(str(moved), "")):
        window.relink_button.click()
    assert "Linked" in window.panels.item(1).text()
    assert window.project.panels[1].source.path == moved
    wait_for(window, lambda: window._inspection_job is None)
    assert "WCS Embedded" in window.panels.item(0).text()
    assert "WCS Missing" in window.panels.item(1).text()

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


def frozen_check(backend: str) -> None:
    runtime = Path(sys.executable).parent / "_internal"
    assert Path(sys._MEIPASS).resolve() == runtime.resolve()  # type: ignore[attr-defined]
    app = QApplication([sys.argv[0]])
    app.setQuitOnLastWindowClosed(False)
    platform = "offscreen" if backend == "CPU" else "windows"
    assert app.platformName() == platform
    window = ProjectWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    window.show()
    try:
        check_solver_settings(window, Path.cwd())
        covered = check_project(window, Path.cwd(), backend)
        print(
            json.dumps(
                {
                    "backend": backend,
                    "platform": platform,
                    "covered_pixels": covered,
                    "recovery": True,
                    "cancel_and_retry": True,
                    "solver_settings": True,
                }
            )
        )
    finally:
        for job in (window.job, window._inspection_job):
            if job is not None:
                job.cancel()
                assert job.wait(15_000)
        window.hide()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def check_bundle(bundle: Path, probe: Path, backend: str) -> None:
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
        result = subprocess.run(
            [str(check), "--backend", backend],
            cwd=working,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        report = json.loads(result.stdout)
        assert report["backend"] == backend
        assert report["recovery"] and report["cancel_and_retry"] and report["solver_settings"]
        print(result.stdout.strip())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    frozen = getattr(sys, "frozen", False)
    parser.add_argument("--backend", choices=("CPU", "OpenGL"), default="CPU")
    if not frozen:
        parser.add_argument("bundle", type=Path)
        parser.add_argument("probe", type=Path)
    args = parser.parse_args()
    if frozen:
        frozen_check(args.backend)
    else:
        check_bundle(args.bundle, args.probe, args.backend)
