"""Replay Phase 9 history on real observations in source or a frozen Windows runtime."""

import argparse
import json
import os
from collections.abc import Callable
from dataclasses import replace
from hashlib import file_digest, sha256
from importlib.metadata import version
from pathlib import Path
from time import monotonic, sleep

import numpy as np
import tifffile
from astropy.io import fits
from astropy.wcs import WCS
from numpy.typing import NDArray
from PySide6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QDialog

from astromosaic.core import Region
from astromosaic.core.masks import FOREGROUND
from astromosaic.photometry.photo_settings import PhotoProfile, PhotoSettings
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.storage.project import load_project, save_project
from astromosaic.ui.mask_editor import MaskEditor
from astromosaic.ui.mosaic_job import PreviewJob
from astromosaic.ui.project_settings import CompositionSettings, ProjectSettings
from astromosaic.ui.project_window import ProjectWindow
from astromosaic.ui.terrain_editor import TerrainPointEditor


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def raster_digest(array: NDArray[np.generic]) -> str:
    return sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def inspect_product(path: Path) -> dict[str, object]:
    """Read samples and metadata independently of AstroMosaic's panel readers."""
    if path.suffix == ".fits":
        with fits.open(path) as hdus:
            hdus.verify("exception")
            header = hdus[0].header
            pixels = hdus[0].data
            coverage = hdus["COVERAGE"].data
            bands = {}
            icc = None
    else:
        with tifffile.TiffFile(path) as tiff:
            page = tiff.pages[0]
            assert isinstance(page, tifffile.TiffPage)
            pixels = page.asarray()
            header = fits.Header.fromstring(page.description.split("\n", 1)[1], sep="\n")
            tags = page.tags.get(34675)
            icc = sha256(tags.value).hexdigest() if tags is not None else None
            children = list(page.pages or ())
            bands = {str(index): raster_digest(child.asarray()) for index, child in enumerate(children)}
            coverage = pixels[..., 3] if icc is not None else children[0].asarray()
    valid = np.count_nonzero(coverage)
    assert valid > 0
    wcs = WCS(header).celestial if "CTYPE1" in header else None
    return {
        "shape": list(pixels.shape),
        "dtype": str(pixels.dtype),
        "samples": raster_digest(pixels),
        "coverage": raster_digest(coverage),
        "covered": int(valid),
        "planes": bands,
        "wcs": wcs.to_header(relax=True).tostring() if wcs is not None else None,
        "unit": header.get("BUNIT"),
        "icc": icc,
    }


class Replay:
    def __init__(self, app: QApplication, directory: Path, *, use_gpu: bool) -> None:
        self.app = app
        self.directory = directory
        self.window = ProjectWindow(
            use_gpu=use_gpu,
            preferences=QSettings(str(directory / "settings.ini"), QSettings.Format.IniFormat),
        )
        self.window.live_preview_action.setChecked(False)
        secondary = next((s for s in app.screens() if s != app.primaryScreen()), None)
        if secondary is not None:
            self.window.move(secondary.availableGeometry().center() - self.window.rect().center())
        self.window.show()
        self.window.activateWindow()
        self.backend = "OpenGL" if use_gpu else "CPU"

    def until(self, condition: Callable[[], bool]) -> None:
        deadline = monotonic() + 90
        while not condition():
            assert monotonic() < deadline, self.window.status.text()
            self.app.processEvents()
            sleep(0.005)
        self.app.processEvents()

    def idle(self) -> None:
        self.until(lambda: self.window.job is None and self.window._inspection_job is None)

    def dialog(self, invoke: Callable[[], None], edit: Callable[[QDialog], None]) -> None:
        timer = QTimer()
        results: list[Exception | None] = []

        def interact() -> None:
            dialog = self.app.activeModalWidget()
            if not isinstance(dialog, QDialog):
                return
            timer.stop()
            try:
                assert dialog.screen() == self.window.screen()
                edit(dialog)
            except Exception as error:
                results.append(error)
                dialog.reject()
            else:
                results.append(None)

        timer.timeout.connect(interact)
        timer.start(5)
        try:
            invoke()
            self.until(lambda: bool(results))
        finally:
            timer.stop()
        if results[0] is not None:
            raise results[0]
        self.idle()

    def open(self, path: Path) -> None:
        self.window._open_project(path)
        self.idle()
        assert not self.window.undo_action.isEnabled() and not self.window.redo_action.isEnabled()

    def preview(self) -> None:
        self.idle()
        assert self.window.preview_button.isEnabled(), self.window.grid_summary.text()
        self.window.preview_button.click()
        job = self.window.job
        assert isinstance(job, PreviewJob)
        self.idle()
        frame = self.window.viewport.frame
        assert frame is not None and frame.has_coverage, self.window.status.text()
        assert self.window.viewport.backend == self.backend
        if self.window._layer() == "sky" and self.backend == "OpenGL":
            assert "OpenGL GPU sampling" in self.window.status.text(), self.window.status.text()

    def export(self, command: str, name: str) -> dict[str, object]:
        path = self.directory / name
        terminal = self.window.command_panel
        terminal.entry.setText(f'session {command} -o "{path}"')
        terminal.run_button.click()
        self.idle()
        assert path.is_file(), self.window.status.text()
        return inspect_product(path)

    def save(self, name: str) -> Path:
        path = self.directory / f"{name}.astromosaic"
        self.window._save_project(path, replace_existing=False)
        assert load_project(path) == self.window.project
        return path

    def close(self) -> None:
        self.window._saved = self.window.project
        self.window.close()
        self.until(lambda: not self.window.isVisible())
        self.window.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def apply_crop(replay: Replay, crop: Region) -> None:
    window = replay.window
    window.edit_crop_button.click()
    replay.idle()
    assert window.crop_controls.isVisible()
    window.viewport.set_crop(crop, editing=True)
    window._show_crop_bounds(crop)
    window.apply_crop_button.click()
    replay.idle()
    assert window.project.render.crop == crop and "crop" in window.project.frame_locks


def check_wcs(product: dict[str, object], spec: RenderSpec) -> None:
    header = product["wcs"]
    assert isinstance(header, str)
    actual = WCS(fits.Header.fromstring(header)).celestial
    region = spec.output_region()
    samples = np.array([(0, 0), (region.width - 1, region.height - 1), (region.width // 2, region.height // 2)])
    np.testing.assert_allclose(actual.all_pix2world(samples, 0),
                               spec.output_wcs().all_pix2world(samples, 0), atol=1e-9, rtol=0)


def check_science(replay: Replay, reference: Path) -> dict[str, object]:
    window = replay.window
    replay.open(reference)
    original = window.project

    def output(name: str) -> dict[str, object]:
        replay.save(f"science-{name}")
        result = replay.export("export", f"science-{name}.fits")
        check_wcs(result, window.project.render)
        assert result["unit"] == "DN"
        return result

    replay.preview()
    initial = output("baseline")
    apply_crop(replay, Region(160, 200, 650, 750))
    edited = window.project
    changed = output("edited")
    assert changed != initial
    window.undo_action.trigger()
    assert window.project == original
    assert output("undo") == initial
    window.redo_action.trigger()
    assert window.project == edited
    assert output("redo") == changed
    return {"baseline": initial, "edited": changed}


def check_photo(replay: Replay, reference: Path) -> dict[str, object]:
    window = replay.window
    observed = load_project(reference)
    original = replace(observed, photo_settings=PhotoSettings(PhotoProfile("srgb")))
    seed = replay.directory / "sky-input.astromosaic"
    save_project(seed, original)
    replay.open(seed)

    def outputs(name: str) -> dict[str, object]:
        manifest = replay.save(f"sky-{name}")
        assert json.loads(manifest.read_bytes())["version"] == 10
        replay.preview()
        result = replay.export("export-photo", f"sky-{name}.tiff")
        check_wcs(result, window.project.render)
        assert result["icc"] == "384b832de3412066743b52a75ee906b6fb9fb8d9e09e936fc2c43223815c6e0a"
        return result

    initial = outputs("baseline")
    apply_crop(replay, Region(190, 250, 1000, 1000))
    cropped = window.project

    def photo_options(dialog: QDialog) -> None:
        assert isinstance(dialog, ProjectSettings)
        assert dialog.tabs is not None
        dialog.tabs.setCurrentIndex(dialog.tabs.count() - 1)
        dialog.photo_exposure.setCurrentIndex(dialog.photo_exposure.findData("manual"))
        dialog.photo_brightness.setCurrentIndex(dialog.photo_brightness.findData("standard"))
        dialog.accept()

    replay.dialog(window.settings_button.click, photo_options)
    edited = window.project
    assert edited.photo_settings == PhotoSettings(PhotoProfile("srgb"), "manual", "standard")
    changed = outputs("edited")
    assert changed != initial
    window.undo_action.trigger()
    assert window.project == cropped
    window.undo_action.trigger()
    assert window.project == original
    assert outputs("undo") == initial
    window.redo_action.trigger()
    assert window.project == cropped
    window.redo_action.trigger()
    assert window.project == edited
    assert outputs("redo") == changed
    return {"baseline": initial, "edited": changed}


def check_mixed(replay: Replay, reference: Path) -> dict[str, object]:
    window = replay.window
    replay.open(reference)
    original = window.project
    placement = original.composition
    original_mask = original.panels[0].source_mask
    assert placement is not None and original_mask is not None

    def output(name: str) -> dict[str, object]:
        replay.save(f"mixed-{name}")
        window.layer_box.setCurrentText("Composition")
        assert window.start_button.isEnabled()
        return replay.export("export --layer composition", f"mixed-{name}.tiff")

    initial = output("baseline")
    window.panels.selectRow(0)

    def paint(dialog: QDialog) -> None:
        assert isinstance(dialog, MaskEditor)
        dialog.tool.setCurrentIndex(3)
        dialog.radius.setValue(3)
        rows, columns = np.nonzero(original_mask.grid() == FOREGROUND)
        x, y = int(columns[-1]), int(rows[-1])
        rect = dialog.canvas.image_rect()
        cols, height = original_mask.size
        point = QPoint(
            round(rect.x() + (x + 0.5) * rect.width() / cols),
            round(rect.y() + (y + 0.5) * rect.height() / height),
        )
        button = Qt.MouseButton.LeftButton
        for kind, pressed in (
            (QEvent.Type.MouseButtonPress, button),
            (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton),
        ):
            event = QMouseEvent(
                kind, QPointF(point), QPointF(dialog.canvas.mapToGlobal(point)),
                button, pressed, Qt.KeyboardModifier.NoModifier,
            )
            QApplication.sendEvent(dialog.canvas, event)
        assert dialog.undo_action.isEnabled()
        dialog.apply_button.click()

    replay.dialog(window.mask_action.trigger, paint)
    masked = window.project
    assert masked.panels[0].source_mask != original_mask and masked.current_foreground() is None

    def fit(dialog: QDialog) -> None:
        assert isinstance(dialog, TerrainPointEditor)
        replay.until(lambda: dialog._job is None)
        for x, y in ((610, 848), (690, 878), (780, 894), (970, 875), (1010, 892)):
            dialog.add_pair.click()
            dialog.views[0].picked.emit((float(x), float(y)))
            dialog.views[1].picked.emit((float(x - 510), float(y)))
        dialog.anchor.setCurrentIndex(1)
        dialog.fit_button.click()
        replay.until(lambda: dialog._job is None)
        assert dialog.apply_button.isEnabled(), dialog.status.text()
        dialog.apply_button.click()

    replay.dialog(window.review_points_action.trigger, fit)
    fitted = window.project
    assert fitted.reviewable_terrain() is not None and fitted.current_foreground() is not None

    def place(dialog: QDialog) -> None:
        assert isinstance(dialog, CompositionSettings)
        dialog.x_offset.setText(str(placement.placement.offset[0]))
        dialog.y_offset.setText(str(placement.placement.offset[1]))
        dialog.seam_y.setText(str(placement.seam_y + 8))
        dialog.overlap.setText(str(placement.overlap_percent))
        dialog.accept()

    replay.dialog(window.composition_action.trigger, place)
    edited = window.project
    changed = output("edited")
    assert changed != initial
    for expected in (fitted, masked, original):
        window.undo_action.trigger()
        assert window.project == expected
    assert output("undo") == initial
    for expected in (masked, fitted, edited):
        window.redo_action.trigger()
        assert window.project == expected
    assert output("redo") == changed
    return {"baseline": initial, "edited": changed}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--backend", choices=("CPU", "OpenGL"), required=True)
    args = parser.parse_args()
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    data = args.data.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    photo = data / "owner01-pa4/pair-20-21.astromosaic"
    mixed = data / "mix02-paranal/project.astromosaic"
    m17 = data / "sky01-m17-atlas/project.astromosaic"
    sources = {
        reference.path
        for manifest in (photo, mixed, m17)
        for panel in load_project(manifest).panels
        for _, reference in panel.references()
    }
    originals = {path: digest(path) for path in sources | {photo, mixed, m17}}
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    replay = Replay(app, output, use_gpu=args.backend == "OpenGL")
    try:
        replay.open(m17)
        source_schema = json.loads(m17.read_bytes())["version"]
        earliest = json.loads(m17.read_bytes())
        earliest["version"] = 1
        for record in earliest["panels"]:
            record["source"]["path"] = str(m17.parent / record["source"]["path"])
        old_manifest = output / "m17-v1.astromosaic"
        old_manifest.write_text(json.dumps(earliest), encoding="utf-8")
        replay.open(old_manifest)
        assert replay.window.project.render == load_project(m17).render
        results = {
            "version": version("astromosaic"),
            "backend": replay.backend,
            "schemas": [1, source_schema, 10],
            "science": check_science(replay, m17),
            "photo": check_photo(replay, photo),
            "mixed": check_mixed(replay, mixed),
        }
        replay.open(output / "sky-edited.astromosaic")
    finally:
        replay.close()
    assert {path: digest(path) for path in originals} == originals
    assert not list(output.glob("*.part"))
    (output / "report.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
