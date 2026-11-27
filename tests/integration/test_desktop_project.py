import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path
from threading import Event, get_ident
from time import monotonic, sleep

import fitsio
import numpy as np
import pytest
import tifffile
from astropy.io import fits
from astropy.wcs import WCS
from packaging.version import Version

from astromosaic.astrometry.hints import PanelOptics
from astromosaic.astrometry.solve import SolveOptions, solve_panel, write_solution
from astromosaic.cli import main
from astromosaic.core import Region, Tile
from astromosaic.core.job import JobContext
from astromosaic.core.masks import FOREGROUND, MASK_EDGE, SKY, UNCLASSIFIED, SourceMask
from astromosaic.geometry import tan_output_wcs
from astromosaic.io import PanelSource, open_panel
from astromosaic.photometry.photo_settings import PhotoProfile, PhotoSettings
from astromosaic.pipeline.masking import read_thumbnail
from astromosaic.pipeline.mosaic import MosaicResult, PreviewFrame, RenderSpec, SkyCalibrationError
from astromosaic.pipeline.smoke import write_smoke_panel
from astromosaic.resampling import PreviewInterpolator
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    load_project,
    preview_project,
    render_project,
    save_project,
)


def test_settings_attachment_accessible_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    pytest.importorskip("PySide6")
    from PySide6.QtGui import QAccessible
    from PySide6.QtWidgets import QApplication, QPushButton, QWidget

    from astromosaic.ui.project_settings import PanelSettings, ProjectSettings

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
    parent = QWidget()
    source = tmp_path / "panel.fits"
    write_smoke_panel(source)
    panel = ProjectPanel(FileReference.capture(source))
    panel_dialog = PanelSettings(panel, parent)
    mosaic_dialog = ProjectSettings(MosaicProject((panel,)), parent)

    def accessible_name(widget: QWidget) -> str:
        interface = QAccessible.queryAccessibleInterface(widget)
        assert interface is not None and interface.isValid()
        return interface.text(QAccessible.Text.Name)

    for dialog in (panel_dialog, mosaic_dialog):
        if secondary is not None:
            dialog.move(secondary.availableGeometry().center() - dialog.rect().center())
        dialog.show()
        try:
            if dialog is panel_dialog:
                assert accessible_name(panel_dialog.wcs) == "WCS sidecar"
                assert accessible_name(panel_dialog.sky_mask) == "FITS sky mask"
                actions = [
                    accessible_name(button) for button in dialog.findChildren(QPushButton)
                    if button.isVisible() and button.text() in {"Browse…", "Clear"}
                ]
                assert sorted(actions) == sorted([
                    "Browse for WCS sidecar", "Clear WCS sidecar",
                    "Browse for FITS sky mask", "Clear FITS sky mask",
                ])

            assert dialog.tabs is not None
            assert dialog.tabs.tabText(1) == "Photo"
            dialog.tabs.setCurrentIndex(1)
            profile = dialog.photo_profile
            profile.mode.setCurrentIndex(profile.mode.findData("icc"))
            assert profile.path.isEnabled() and profile.path.isReadOnly()
            assert accessible_name(profile.path) == "ICC file"
            browse = next(
                button for button in dialog.findChildren(QPushButton)
                if button.isVisible() and button.text() == "Browse…"
            )
            assert browse.isEnabled() and accessible_name(browse) == "Browse for ICC file"
        finally:
            dialog.close()


@pytest.mark.parametrize("language, separator", [("en_US", "."), ("tr_TR", ",")])
def test_desktop_decimal_input_uses_its_locale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, language: str, separator: str,
) -> None:
    import os

    pytest.importorskip("PySide6")
    from PySide6.QtCore import QLocale, Qt
    from PySide6.QtWidgets import QApplication, QPushButton, QWidget

    from astromosaic.ui.panel_table import PanelTable, panel_row
    from astromosaic.ui.project_settings import PanelSettings, ProjectSettings

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    parent = QWidget()
    parent.setLocale(QLocale(language))
    source = tmp_path / "source.fits"
    write_smoke_panel(source)
    panel = ProjectPanel(FileReference.capture(source), weight=1.25)
    project = MosaicProject((panel,), RenderSpec((12.345678912345, -2.5), (64, 64), 2.5))
    mosaic = ProjectSettings(project, parent, suggested_rotation=2.25)
    panel_settings = PanelSettings(panel, parent)
    table = PanelTable()
    table.setLocale(parent.locale())

    try:
        assert mosaic.scale.text() == f"2{separator}5"
        assert mosaic.settings() == project
        assert panel_settings.weight.text() == f"1{separator}25"
        suggested = next(
            button for button in mosaic.findChildren(QPushButton)
            if button.text().startswith("Use suggested rotation")
        )
        suggested.click()
        mosaic.scale.setText(f"1{separator}5")
        mosaic.background.setCurrentText("Auto")
        mosaic.match.setText(f"2{separator}75")
        updated = mosaic.settings()
        assert updated.render.scale_arcsec == 1.5 and updated.render.rotation_deg == 2.25
        assert updated.refinement is not None and updated.refinement.max_shift_px == 2.75
        manifest = tmp_path / "localized.astromosaic"
        save_project(manifest, updated)
        assert load_project(manifest) == updated
        assert json.loads(manifest.read_text(encoding="utf-8"))["render"]["scale_arcsec"] == 1.5

        grouping = parent.locale().groupSeparator()
        mosaic.scale.setText(f"1{grouping}234")
        with pytest.raises(ValueError, match="Pixel scale.*without grouping separators"):
            mosaic.settings()
        mosaic.scale.setText("nan")
        with pytest.raises(ValueError, match="Pixel scale.*finite"):
            mosaic.settings()

        panel_settings.show_embedded_optics(PanelOptics(350, 3.75, 3.75))
        assert panel_settings.pixel_size_x.text() == f"3{separator}75"
        assert panel_settings.settings() == panel
        panel_settings.pixel_size_x.setText(f"4{separator}25")
        assert panel_settings.settings().optics.pixel_size_x_um == 4.25

        table.properties.refresh([panel_row(panel, None, None, None)])
        weight = table.cell(0, "Weight")
        assert weight.data(Qt.ItemDataRole.EditRole) == f"1{separator}25"
        edited: list[ProjectPanel] = []
        table.properties.panelEdited.connect(lambda _row, value: edited.append(value))
        assert table.properties.setData(weight, f"2{separator}5")
        assert edited[-1].weight == 2.5
        assert not table.properties.setData(weight, f"1{grouping}234")
        assert len(edited) == 1
    finally:
        table.close()
        panel_settings.close()
        mosaic.close()
        parent.close()


def test_empty_workspace_guides_the_next_available_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication, QLabel

    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    preferences = QSettings(str(tmp_path / "workspace.ini"), QSettings.Format.IniFormat)
    preferences.setValue("view/liveSkyPreview", False)
    window = ProjectWindow(use_gpu=False, preferences=preferences)
    secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
    if secondary is not None:
        window.move(secondary.availableGeometry().center() - window.rect().center())
    window.show()
    hint = window.viewport.canvas.findChild(QLabel)
    assert hint is not None

    def idle() -> None:
        deadline = monotonic() + 20
        while window.job is not None or window._inspection_job is not None:
            assert monotonic() < deadline, window.status.text()
            app.processEvents()
            sleep(0.005)
        app.processEvents()

    try:
        assert hint.isVisible() and "Add Panels" in hint.text()
        assert window.add_button.property("primary") and not window.preview_button.isEnabled()
        source = tmp_path / "smoke.fits"
        write_smoke_panel(source)
        panel = ProjectPanel(FileReference.capture(source))
        window._set_project(MosaicProject((panel,), auto_frame_preview=True), None)
        assert "Checking panel metadata" in hint.text()
        idle()
        assert hint.isVisible() and "Build Preview" in hint.text()
        assert window.preview_button.property("primary") and not window.add_button.property("primary")
        window.preview_button.click()
        assert "Preparing the preview" in hint.text()
        idle()
        assert window.viewport.frame is not None and hint.isHidden()
        assert window.start_button.property("primary") and not window.preview_button.property("primary")
        window._new_project()
        assert hint.isVisible() and "Add Panels" in hint.text()
    finally:
        window.close()



def test_photo_desktop_session_and_cli_share_the_fitted_grid_and_tone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    import os

    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEvent, QPointF, QSettings, Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFileDialog

    from astromosaic.ui.project_settings import ProjectSettings
    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    old_quit = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)
    spec = RenderSpec((32.0, 10.0), (24, 18), 7.2)
    header = spec.output_wcs().to_header()
    header["FILTER"] = "RGB"
    pixels = np.arange(24 * 18 * 3, dtype=np.uint16).reshape(18, 24, 3) * 33
    photo_source = tmp_path / "tagged.tiff"
    tifffile.imwrite(
        photo_source, pixels, photometric="rgb", metadata=None,
        iccprofile=files("astromosaic.io").joinpath("sRGB2014.icc").read_bytes(),
        description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n"),
    )
    linear_source = tmp_path / "linear.fits"
    header["FILTER"], header["BUNIT"] = "L", "MJy/sr"
    fits.writeto(linear_source, np.ones((18, 24), dtype=np.float32), header)
    extra_linear_source = tmp_path / "extra-linear.fits"
    fits.writeto(extra_linear_source, np.ones((18, 24), dtype=np.float32), header)
    project = MosaicProject(
        panels=tuple(
            ProjectPanel(FileReference.capture(p))
            for p in (photo_source, linear_source, extra_linear_source)
        ),
        auto_frame_preview=True,
    )
    manifest = tmp_path / "Saved.astromosaic"
    save_project(manifest, project)
    initial = manifest.read_bytes()
    desktop = tmp_path / "photo-desktop.tiff"
    session = tmp_path / "photo-session.tiff"
    cli = tmp_path / "photo-cli.tiff"
    cli_preview = tmp_path / "preview-cli.tiff"
    window = ProjectWindow(
        use_gpu=False,
        preferences=QSettings(str(tmp_path / "appearance.ini"), QSettings.Format.IniFormat),
    )

    def wait_idle() -> None:
        deadline = monotonic() + 15
        while window.job is not None or window._inspection_job is not None:
            assert monotonic() < deadline, window.status.text()
            app.processEvents()
            sleep(0.005)

    def wait_for_live_preview() -> None:
        deadline = monotonic() + 12
        while window.viewport.frame is None or window.job is not None:
            assert monotonic() < deadline, window.status.text()
            app.processEvents()
            sleep(0.005)

    try:
        secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
        if secondary is not None:
            window.move(secondary.availableGeometry().center() - window.rect().center())
        window.show()
        window._open_project(manifest)
        wait_idle()
        window.band_box.setCurrentIndex(window.band_box.findData("RGB"))
        window.preview_button.click()
        wait_idle()
        assert window.preview_title.text() == "Visual Preview"
        assert window.start_button.text() == "Export Photo Mosaic…"
        assert window.use_preview_grid_button.isEnabled() and window.project.render == project.render
        window.resize(630, 760)
        app.processEvents()
        assert window.band_box.isVisible()
        if app.platformName() == "windows":
            for button in (window.settings_button, window.preview_button, window.start_button):
                assert button.width() >= button.sizeHint().width()
        assert window.viewport.tone_box.currentText() == "Preserve Tone"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (str(desktop), ""))
        window.start_button.click()
        wait_idle()
        assert desktop.is_file(), window.status.text()

        assert main(
            ["project", "export-photo", str(manifest), "--band", "RGB", "-o", str(cli), "--json"]
        ) == 0
        result = json.loads(capsys.readouterr().out)
        assert (result["band"], result["tone"], result["grid"]) == ("RGB", "preserve", "auto")
        assert cli.read_bytes() == desktop.read_bytes()

        window.viewport.tone_box.setCurrentIndex(0)
        window.viewport.midtones.setValue(41)
        window.command_panel.entry.setText(f'session export-photo -o "{session}"')
        window.command_panel.run_button.click()
        wait_idle()
        with open_panel(session) as reader:
            assert reader.header["PHOTOTON"] == "preview"
            assert reader.header["PHOTOMID"] == 0.41
        assert main(
            ["project", "export-photo", str(manifest), "--band", "RGB", "--midtones", "41",
             "-o", str(cli_preview), "--json"]
        ) == 0
        assert json.loads(capsys.readouterr().out)["tone"] == "preview"
        assert cli_preview.read_bytes() == session.read_bytes()
        assert manifest.read_bytes() == initial
        assert window.project.render == project.render and window.project.auto_frame_preview

        window._update_panel(0, replace(window.project.panels[0], weight=1.25))
        assert window.viewport.frame is None
        wait_for_live_preview()
        assert window.start_button.text() == "Export Photo Mosaic…"

        window.panels.selectRow(2)
        window.remove_action.trigger()
        assert len(window.project.panels) == 2 and window.viewport.frame is None
        wait_for_live_preview()
        assert window.band_box.currentData() == "RGB"
        assert window.start_button.text() == "Export Photo Mosaic…"

        current = window.project
        frame_before_crop = window.viewport.frame
        window.edit_crop_button.click()
        wait_idle()
        assert window.viewport.crop is not None and window.crop_controls.isVisible()
        assert not window.check_foreground.isEnabled() and not window.revalidate_solve_action.isEnabled()
        crop_focus = app.focusWidget()
        assert crop_focus is not None and crop_focus.accessibleName() == "Mosaic preview"
        original_crop = window.viewport.crop
        QTest.keyClick(crop_focus, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
        assert window.viewport.crop == replace(original_crop, width=original_crop.width - 1)
        QTest.keyClick(crop_focus, Qt.Key.Key_Escape)
        assert window.project == current and not window.crop_controls.isVisible()
        assert window.viewport.frame is frame_before_crop
        assert app.focusWidget() is window.edit_crop_button
        assert window.start_button.text() == "Export Photo Mosaic…"
        window.edit_crop_button.click()
        wait_idle()
        assert window.auto_crop_button.isEnabled() and not window.start_button.isEnabled()
        window.auto_crop_button.click()
        crop = window.viewport.crop
        display = window.viewport.frame
        assert crop is not None and display is not None
        rect = window.viewport.image_rect()
        start = rect.topLeft()
        start.setX(start.x() + rect.width() * (crop.x + crop.width) / display.output_size[0])
        start.setY(start.y() + rect.height() * (crop.y + crop.height) / display.output_size[1])
        start -= QPointF(1, 1)
        end = start - QPointF(rect.width() * 0.13, rect.height() * 0.13)
        canvas = window.viewport.canvas
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start.toPoint())
        QTest.mouseMove(canvas, end.toPoint())
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end.toPoint())
        edited = window.viewport.crop
        assert edited is not None and edited.width < crop.width and edited.height < crop.height
        crop_focus = app.focusWidget()
        assert crop_focus is not None and crop_focus.accessibleName() == "Mosaic preview"
        QTest.keyClick(crop_focus, Qt.Key.Key_Right)
        moved = replace(edited, x=edited.x + 1)
        assert window.viewport.crop == moved
        QTest.keyClick(crop_focus, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
        edited = replace(moved, height=moved.height - 1)
        assert window.viewport.crop == edited
        before_pan = window.viewport.image_rect()
        QTest.keyClick(crop_focus, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)
        assert window.viewport.image_rect().x() < before_pan.x()
        assert window.viewport.crop == edited and window.project == current
        assert window.crop_bounds.text() == (
            f"Crop {edited.x}, {edited.y} · {edited.width} × {edited.height} / "
            f"{display.output_size[0]} × {display.output_size[1]} px"
        )
        QTest.keyClick(crop_focus, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
        assert app.focusWidget() is window.cancel_crop_button
        QTest.keyClick(window.cancel_crop_button, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
        assert app.focusWidget() is window.apply_crop_button
        QTest.keyClick(window.apply_crop_button, Qt.Key.Key_Space)
        wait_idle()
        assert window.project.render.crop == edited and "crop" in window.project.frame_locks
        frame = window.viewport.frame
        assert frame is not None and frame.output_size == (edited.width, edited.height)
        cropped = tmp_path / "cropped.astromosaic"
        save_project(cropped, window.project)
        assert load_project(cropped) == window.project
        assert json.loads(cropped.read_bytes())["version"] == 9
        cropped_project = window.project
        assert window.undo_action.text() == "&Undo Apply Crop"
        window.undo_action.trigger()
        assert window.project == current and window.viewport.crop is None
        assert not window.start_button.isEnabled()
        wait_for_live_preview()
        restored = window.viewport.frame
        assert restored is not None and frame_before_crop is not None
        assert restored.output_size == frame_before_crop.output_size
        assert window.start_button.text() == "Export Photo Mosaic…"
        window.redo_action.trigger()
        assert window.project == cropped_project and window.viewport.crop is None
        wait_for_live_preview()
        restored = window.viewport.frame
        assert restored is not None and restored.output_size == (edited.width, edited.height)
        assert not window.crop_controls.isVisible()

        def set_photo_options() -> None:
            dialog = app.activeModalWidget()
            assert isinstance(dialog, ProjectSettings)
            dialog.photo_profile.mode.setCurrentIndex(dialog.photo_profile.mode.findData("srgb"))
            dialog.photo_exposure.setCurrentIndex(dialog.photo_exposure.findData("manual"))
            dialog.photo_brightness.setCurrentIndex(dialog.photo_brightness.findData("standard"))
            dialog.accept()

        QTimer.singleShot(0, set_photo_options)
        window.settings_button.click()
        changed = window.project
        assert changed.photo_settings == PhotoSettings(PhotoProfile("srgb"), "manual", "standard")
        assert changed.render == cropped_project.render
        assert changed.frame_locks == cropped_project.frame_locks
        assert window.undo_action.text() == "&Undo Change Mosaic Settings"
        wait_for_live_preview()
        assert window.start_button.text() == "Export Photo Mosaic…"
        window.undo_action.trigger()
        assert window.project == cropped_project
        wait_for_live_preview()
        window.redo_action.trigger()
        assert window.project == changed
        wait_for_live_preview()
        assert window.band_box.currentData() == "RGB"
        assert window.start_button.text() == "Export Photo Mosaic…"

        window._update_panel(0, replace(window.project.panels[0], include_sky=False))
        wait_idle()
        assert window.band_box.findData("RGB") == -1
        window.undo_action.trigger()
        wait_idle()
        assert window.band_box.findData("RGB") >= 0 and window.band_box.findData("L") >= 0
        assert window.band_box.currentData() is None and not window.start_button.isEnabled()

        window.band_box.setCurrentIndex(window.band_box.findData("L"))
        assert window.start_button.text() == "Export Mosaic…" and window.viewport.frame is None
    finally:
        window._saved = window.project
        window.close()
        wait_idle()
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.setQuitOnLastWindowClosed(old_quit)


def test_desktop_project_roundtrip_progress_cancel_and_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    import os

    from PySide6.QtCore import QEventLoop, Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFileDialog

    from astromosaic.ui import mosaic_job
    from astromosaic.ui.project_settings import PanelSettings, ProjectSettings
    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)

    source = tmp_path / "light.fits"
    write_smoke_panel(source)
    with fits.open(source, mode="update", do_not_scale_image_data=True) as hdus:
        hdus[0].header.update({"FOCALLEN": 450.0, "XPIXSZ": 3.75, "YPIXSZ": 3.75})
    mask = tmp_path / "sky-mask.fits"
    sky = np.ones((12, 16), dtype=np.uint8)
    sky[0, 0] = 0
    fits.writeto(mask, sky)
    wcs = tmp_path / "light.wcs.json"
    with open_panel(source, sky_mask=mask) as panel:
        write_solution(wcs, panel, solve_panel(panel, SolveOptions()))
    tiff = tmp_path / "also linear.tiff"
    center = (359.999, 20.0)
    header = tan_output_wcs(center, (9, 7), 7.2, 0.0, Region(0, 0, 9, 7)).to_header()
    header["FILTER"], header["BUNIT"] = "L", "MJy/sr"
    tifffile.imwrite(
        tiff,
        np.ones((7, 9), dtype=np.uint16),
        photometric="minisblack",
        metadata=None,
        description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False),
    )
    manifest = tmp_path / "Session.astromosaic"
    output = tmp_path / "mosaic.tiff"
    save_target = manifest
    open_target = manifest
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (str(save_target), ""))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **kw: (str(open_target), ""))
    monkeypatch.setattr(
        QFileDialog, "getOpenFileNames", lambda *a, **kw: ([str(source), str(tiff)], "")
    )

    window = ProjectWindow()
    entered = Event()
    release = Event()
    main_thread = get_ident()

    def until(condition: Callable[[], bool]) -> None:
        if condition():
            return
        loop = QEventLoop()
        poll = QTimer()
        poll.timeout.connect(lambda: loop.quit() if condition() else None)
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(loop.quit)
        poll.start(10)
        timeout.start(8000)
        loop.exec()
        poll.stop()
        timeout.stop()
        assert condition(), (window.status.text(), window.progress.value(), entered.is_set())

    def click(button: object) -> None:
        from PySide6.QtWidgets import QPushButton

        assert isinstance(button, QPushButton)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)

    def pause_on_progress(context: JobContext) -> JobContext:
        assert get_ident() != main_thread
        report = context.on_progress
        assert report is not None

        def progress(done: int, total: int) -> None:
            report(done, total)
            if not entered.is_set():
                entered.set()
                if not release.wait(12):
                    raise RuntimeError("The test did not release the worker.")

        return JobContext(context.is_cancelled, progress)

    def pause_after_tile(project: MosaicProject, path: Path, context: JobContext) -> MosaicResult:
        return render_project(project, path, pause_on_progress(context))

    def pause_preview(
        project: MosaicProject,
        context: JobContext,
        on_proxy: Callable[[PreviewFrame], None],
        *,
        band: str | None,
        allow_visual: bool,
        adaptive_edge: int | None,
        resolution_scale: int,
        grid: RenderSpec | None,
        inspect_crop: bool,
        interpolate: PreviewInterpolator | None,
    ) -> PreviewFrame:
        return preview_project(
            project, pause_on_progress(context), on_proxy, band=band, allow_visual=allow_visual,
            adaptive_edge=adaptive_edge, resolution_scale=resolution_scale,
            grid=grid, inspect_crop=inspect_crop, interpolate=interpolate,
        )

    def set_geometry() -> None:
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, ProjectSettings)
        dialog.auto_frame.setChecked(False)
        dialog.ra.setText(str(center[0]))
        dialog.dec.setText(str(center[1]))
        dialog.scale.setText("7.2")
        dialog.output_width.setText("140")
        dialog.output_height.setText("140")
        dialog.accept()

    def set_panel_options() -> None:
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, PanelSettings)
        dialog.weight.setText("1.5")
        assert dialog.focal_length.placeholderText() == "450 (embedded)"
        assert dialog.pixel_size_x.placeholderText() == "3.75 (embedded)"
        assert dialog.pixel_size_y.placeholderText() == "3.75 (embedded)"
        assert dialog.focal_length.text() == "450"
        assert dialog.pixel_size_x.text() == dialog.pixel_size_y.text() == "3.75"
        dialog.focal_length.setText("500")
        dialog.wcs.setText(str(wcs))
        dialog.sky_mask.setText(str(mask))
        dialog.accept()

    try:
        window.show()
        app_version = Version(version("astromosaic"))
        beta_label = " (Beta)" if app_version.pre and app_version.pre[0] == "b" else ""
        app_title = f"AstroMosaic {app_version}{beta_label}"
        assert window.windowTitle() == f"Untitled — {app_title}"
        click(window.add_button)
        assert window.panels.properties.rowCount() == 2
        assert window.windowTitle() == f"Untitled* — {app_title}"
        until(lambda: window.job is None)
        until(lambda: window.panels.cell(0, "WCS").data() == "Embedded")
        window.panels.selectRow(0)
        QTimer.singleShot(0, set_panel_options)
        click(window.panel_button)
        assert window.project.panels[0].weight == 1.5
        assert window.project.panels[0].optics == PanelOptics(500)
        until(lambda: window.panels.cell(0, "WCS").data() == "Sidecar")
        QTimer.singleShot(0, set_geometry)
        click(window.settings_button)
        assert window.project.render.size == (140, 140)
        new, open_project, save, _save_as = window._file_actions
        save.trigger()
        assert load_project(manifest).render == window.project.render
        assert window.windowTitle() == f"{manifest.name} — {app_title}"
        new.trigger()
        assert window.panels.properties.rowCount() == 0
        original = source.read_bytes()
        moved = source.rename(tmp_path / "Taşınan panel.fits")
        open_project.trigger()
        assert "missing" in window.panels.cell(0, "Link").data()
        assert window.panels.cell(0, "WCS").data() == "Unavailable"
        open_target = moved
        window.relink_action.trigger()
        assert "Linked" in window.panels.cell(0, "Link").data()
        until(lambda: window.panels.cell(0, "WCS").data() == "Sidecar")
        save.trigger()
        assert load_project(manifest).panels[0].source.path == moved
        assert window.project.panels[0].optics == PanelOptics(500)

        def mixed_filters(*_args: object, **_kwargs: object) -> None:
            raise SkyCalibrationError("filter", "Expected a common FILTER.")

        with monkeypatch.context() as patch:
            patch.setattr(mosaic_job, "preview_project", mixed_filters)
            click(window.preview_button)
            until(lambda: window.job is None)
        assert "Select a Sky band" in window.status.text()
        assert window.status.text() in window.command_panel.output.toPlainText().splitlines()

        with monkeypatch.context() as patch:
            patch.setattr(mosaic_job, "preview_project", pause_preview)
            click(window.preview_button)
            until(lambda: entered.is_set() and 0 < window.progress.value() < 100)
            assert window.cancel_button.isEnabled() and not window.start_button.isEnabled()
            click(window.cancel_button)
            release.set()
            until(lambda: window.job is None)
        assert window.viewport.frame is None and window.status.text() == "Preview cancelled."
        click(window.preview_button)
        until(lambda: window.job is None)
        preview = window.viewport.frame
        assert preview is not None and preview.has_coverage
        assert preview.size == (70, 70) and preview.output_size == (140, 140)
        assert window.status.text().startswith("Sky preview")
        entered.clear()
        release.clear()

        save_target = output
        with monkeypatch.context() as patch:
            patch.setattr(mosaic_job, "render_project", pause_after_tile)
            click(window.start_button)
            until(lambda: entered.is_set() and 0 < window.progress.value() < 100)
            assert window.cancel_button.isEnabled() and not save.isEnabled()
            assert not output.exists() and len(list(tmp_path.glob("*.part"))) == 1
            ticks: list[int] = []
            QTimer.singleShot(10, lambda: ticks.append(window.progress.value()))
            until(lambda: bool(ticks))
            click(window.cancel_button)
            assert "Cancelling" in window.status.text()
            release.set()
            until(lambda: window.job is None)
        assert window.status.text() == "Mosaic cancelled."
        assert not output.exists() and not list(tmp_path.glob("*.part"))

        click(window.start_button)
        until(lambda: window.job is None)
        assert window.progress.value() == 100 and window.status.text().startswith(
            "Saved mosaic.tiff"
        )
        assert window.viewport.frame is preview
        with open_panel(output) as panel:
            assert panel.descriptor.width == panel.descriptor.height == 140
            assert panel.read_tile(Region(65, 66, 10, 10)).valid.any()
            assert any("existing-wcs WCS sidecar" in line for line in panel.header["HISTORY"])
            assert any("Input 1: sky mask" in line for line in panel.header["HISTORY"])
        assert moved.read_bytes() == original
        assert not list(tmp_path.glob("*.part"))

        click(window.start_button)
        until(lambda: window.job is None)
        assert "output file already exists" in window.status.text()
        log = window.command_panel.output.toPlainText()
        for summary in (
            "Added 2 panel(s).",
            "Checked 2 panel(s) for foreground.",
            "Updated settings for light.fits.",
            "Mosaic settings applied.",
            "Saved Session.astromosaic.",
            "Opened Session.astromosaic.",
            f"Relinked {moved.name}.",
            "Preview cancelled.",
            "Sky preview",
            "Mosaic cancelled.",
            "Saved mosaic.tiff",
        ):
            assert summary in log
        assert log.splitlines()[-1] == "Mosaic failed."
        assert str(tmp_path) not in log

        # Closing during a render waits asynchronously for cancellation and cleanup.
        save_target = tmp_path / "closing.tiff"
        entered.clear()
        release.clear()
        with monkeypatch.context() as patch:
            patch.setattr(mosaic_job, "render_project", pause_after_tile)
            click(window.start_button)
            until(entered.is_set)
            window.close()
            assert window.isVisible()
            release.set()
            until(lambda: not window.isVisible())
        assert not save_target.exists() and not list(tmp_path.glob("*.part"))
    finally:
        release.set()
        for job in (window.job, window._inspection_job):
            if job is not None:
                job.cancel()
                assert job.wait(15_000)
        window.deleteLater()
        app.processEvents()


def test_desktop_sky_mask_proposal_manual_edits_and_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    import os
    from time import monotonic

    from PySide6.QtCore import QPoint, Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFileDialog

    from astromosaic.ui import mosaic_job
    from astromosaic.ui.mask_editor import MaskEditor
    from astromosaic.ui.project_settings import PanelSettings
    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)

    width, height = 128, 96
    y, x = np.mgrid[:height, :width]
    sky = 2.0 + 0.002 * (x + y)
    horizon = 58 + 4 * np.sin(x / 19)
    fits_pixels = (sky + 250 * (y >= horizon)).astype(np.float32)
    tiff_pixels = (sky + 270 * ((y >= 67) & (x > 104))).astype(np.float32)
    source, tiff = tmp_path / "horizon.fits", tmp_path / "small-foreground.tiff"
    fits.writeto(source, fits_pixels)
    tifffile.imwrite(tiff, tiff_pixels, photometric="minisblack", metadata=None)
    originals = source.read_bytes(), tiff.read_bytes()
    manifest = tmp_path / "night.astromosaic"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (str(manifest), ""))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **kw: (str(manifest), ""))
    monkeypatch.setattr(
        QFileDialog, "getOpenFileNames", lambda *a, **kw: ([str(source), str(tiff)], "")
    )
    window = ProjectWindow(use_gpu=False)
    left = Qt.MouseButton.LeftButton
    entered, release = Event(), Event()

    def until(condition: Callable[[], bool]) -> None:
        deadline = monotonic() + 8
        while not condition() and monotonic() < deadline:
            QTest.qWait(12)
        assert condition(), window.status.text()

    def set_tag(index: int) -> None:
        def change() -> None:
            dialog = QApplication.activeModalWidget()
            assert isinstance(dialog, PanelSettings)
            dialog.foreground_override.setCurrentIndex(index)
            dialog.accept()

        QTimer.singleShot(0, change)
        QTest.mouseClick(window.panel_button, left)

    def with_mask_dialog(trigger: Callable[[], None], edit: Callable[[MaskEditor], None]) -> None:
        timer = QTimer()
        completed: list[Exception | None] = []

        def interact() -> None:
            dialog = QApplication.activeModalWidget()
            if isinstance(dialog, MaskEditor):
                timer.stop()
                try:
                    edit(dialog)
                except Exception as error:
                    completed.append(error)
                    dialog.reject()
                else:
                    completed.append(None)

        timer.timeout.connect(interact)
        timer.start(10)
        try:
            trigger()
            until(lambda: bool(completed) and window.job is None)
            if completed[0] is not None:
                raise completed[0]
        finally:
            timer.stop()

    def point(dialog: MaskEditor, x: int, y: int) -> QPoint:
        rect = dialog.canvas.image_rect()
        return QPoint(
            round(rect.x() + (x + 0.5) * rect.width() / width),
            round(rect.y() + (y + 0.5) * rect.height() / height),
        )

    def adjust_proposal(dialog: MaskEditor) -> None:
        assert dialog.canvas.grid[15, 30] == SKY and dialog.canvas.grid[86, 58] == FOREGROUND
        dialog.tool.setCurrentIndex(3)
        dialog.radius.setValue(2)
        QTest.mouseClick(dialog.canvas, left, pos=point(dialog, 30, 15))
        assert dialog.canvas.grid[15, 30] == UNCLASSIFIED
        QTest.mouseClick(dialog.apply_button, left)

    def trace_mask(dialog: MaskEditor) -> None:
        assert not dialog.apply_button.isEnabled() and dialog.tool.currentIndex() == 0
        QTest.mousePress(dialog.canvas, left, pos=point(dialog, 0, 65))
        QTest.mouseRelease(dialog.canvas, left, pos=point(dialog, width - 1, 65))
        assert np.all(dialog.canvas.grid[:65] == SKY)
        assert np.all(dialog.canvas.grid[65:] == FOREGROUND)
        dialog.undo_action.trigger()
        assert np.all(dialog.canvas.grid == UNCLASSIFIED) and not dialog.apply_button.isEnabled()
        dialog.redo_action.trigger()
        assert np.all(dialog.canvas.grid[:65] == SKY)
        assert np.all(dialog.canvas.grid[65:] == FOREGROUND)
        QTest.mouseClick(dialog.apply_button, left)

    def pause(source: PanelSource, edge: int, budget: int, context: JobContext) -> Tile:
        if edge == MASK_EDGE:
            entered.set()
            assert release.wait(8)
            context.check_cancelled()
        return read_thumbnail(source, edge, budget, context)

    try:
        window.show()
        QTest.mouseClick(window.add_button, left)
        until(lambda: window.job is None)
        assert window.project.panels[0].foreground_tag == "mixed"
        assert window.project.panels[1].foreground_tag == "sky-only"
        assert window.propose_mask.isEnabled()

        set_tag(2)
        window.check_foreground.trigger()
        until(lambda: window.job is None)
        rechecked = window.project.panels[0]
        assert rechecked.foreground_suggestion == "mixed"
        assert rechecked.foreground_tag == "sky-only"
        assert not window.propose_mask.isEnabled()
        set_tag(0)

        with monkeypatch.context() as patch:
            patch.setattr(mosaic_job, "read_thumbnail", pause)
            window.propose_mask.trigger()
            until(entered.is_set)
            QTest.mouseClick(window.cancel_button, left)
            release.set()
            until(lambda: window.job is None)
        assert window.status.text() == "Sky mask cancelled."
        assert window.project.panels[0].source_mask is None
        with_mask_dialog(window.propose_mask.trigger, adjust_proposal)
        first_mask = window.project.panels[0].source_mask
        assert first_mask is not None and first_mask.grid()[15, 30] == UNCLASSIFIED

        window.panels.selectRow(1)
        set_tag(1)
        with_mask_dialog(window.mask_action.trigger, trace_mask)
        second_mask = window.project.panels[1].source_mask
        assert second_mask is not None
        new, open_project, save, _ = window._file_actions
        save.trigger()
        new.trigger()
        assert window.panels.properties.rowCount() == 0
        open_project.trigger()
        assert window.panels.properties.rowCount() == 2
        assert window.project.panels[0].source_mask == first_mask
        assert window.project.panels[1].source_mask == second_mask
        assert window.project.panels[1].foreground_override == "mixed"

        def check_reopened(dialog: MaskEditor) -> None:
            assert dialog.canvas.grid[15, 30] == UNCLASSIFIED
            assert dialog.canvas.grid[20, 60] == SKY and dialog.canvas.grid[86, 58] == FOREGROUND
            dialog.reject()

        with_mask_dialog(window.mask_action.trigger, check_reopened)
        assert originals == (source.read_bytes(), tiff.read_bytes())
    finally:
        release.set()
        for job in (window.job, window._inspection_job):
            if job is not None:
                job.cancel()
                assert job.wait(10_000)
        window.deleteLater()
        app.processEvents()


def test_desktop_composition_propose_edit_and_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    import os

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication, QFileDialog

    from astromosaic.ui.project_settings import CompositionSettings, ProjectSettings
    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    source = tmp_path / "combined.fits"
    size = (80, 60)
    spec = RenderSpec((30.0, 20.0), size, 2.0, tile_size=24)
    header = tan_output_wcs(
        spec.center, size, spec.scale_arcsec, 0.0, spec.output_region()
    ).to_header()
    header["FILTER"], header["BUNIT"] = "L", "MJy/sr"
    y, x = np.indices((size[1], size[0]), dtype=np.float32)
    fits.writeto(source, 0.1 * x + y, header)
    labels = np.broadcast_to(np.where(y < 30, SKY, FOREGROUND), y.shape).astype(np.uint8)
    panel = ProjectPanel(
        FileReference.capture(source), source_mask=SourceMask(size, labels.tobytes())
    )
    manifest = tmp_path / "layers.astromosaic"
    save_project(manifest, MosaicProject((panel,), render=spec))
    destination = tmp_path / "composition.fits"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **kw: (str(manifest), ""))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (str(destination), ""))
    window = ProjectWindow(use_gpu=False)

    def wait_for_job() -> None:
        job = window.job
        if job is None:
            return
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        job.finished.connect(loop.quit)
        timer.start(8_000)
        loop.exec()
        assert window.job is None, window.status.text()

    def edit() -> None:
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, CompositionSettings)
        dialog.x_offset.setText("2.5")
        dialog.y_offset.setText("23.0")
        dialog.rotation.setText("-2.0")
        dialog.scale.setText("1.05")
        dialog.seam_y.setText("27.0")
        dialog.overlap.setText("20.0")
        dialog.crop.setText("12")
        dialog.accept()

    try:
        window.show()
        _new, open_action, save, _save_as = window._file_actions
        open_action.trigger()
        window.align_action.trigger()
        wait_for_job()
        assert window.layer_box.currentText() == "Foreground", window.status.text()
        window.placement_action.trigger()
        wait_for_job()
        assert window.layer_box.currentText() == "Composition", window.status.text()
        QTimer.singleShot(0, edit)
        window.composition_action.trigger()
        save.trigger()
        open_action.trigger()
        composition = window.project.composition
        assert composition is not None
        assert (
            composition.placement.offset,
            composition.placement.rotation_deg,
            composition.placement.scale,
        ) == ((2.5, 23.0), -2.0, 1.05)
        assert (composition.seam_y, composition.overlap_percent, composition.sky_crop_bottom) == (
            27.0,
            20.0,
            12,
        )
        assert "Seam width" in window.grid_summary.text()
        window.preview_button.click()
        wait_for_job()
        preview = window.viewport.frame
        assert preview is not None and preview.common_coverage is not None
        assert preview.common_coverage.any()
        window.overlap_check.setChecked(True)
        highlighted = window.viewport.frame
        assert highlighted is not None and not np.array_equal(highlighted.rgba, preview.rgba)
        window.overlap_check.setChecked(False)
        assert window.viewport.frame is preview
        window.start_button.click()
        wait_for_job()
        assert destination.exists(), window.status.text()
        with fits.open(destination) as result:
            assert np.any(result["LAYERS"].data == 3)

        for layer in ("composition", "sky", "foreground"):
            if layer != "composition":
                window.layer_box.setCurrentText(layer.capitalize())
                destination = tmp_path / f"desktop-{layer}.fits"
                window.start_button.click()
                wait_for_job()
                assert destination.exists(), window.status.text()
            cli_output = tmp_path / f"cli-{layer}.fits"
            exported = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "astromosaic",
                    "project",
                    "export",
                    str(manifest),
                    "--layer",
                    layer,
                    "-o",
                    str(cli_output),
                    "--json",
                ],
                check=True,
                capture_output=True,
                encoding="utf-8",
                timeout=60,
            )
            assert json.loads(exported.stdout)["layer"] == layer
            with fitsio.FITS(destination) as desktop, fitsio.FITS(cli_output) as cli:
                np.testing.assert_array_equal(cli[0].read(), desktop[0].read())
                np.testing.assert_array_equal(cli["COVERAGE"].read(), desktop["COVERAGE"].read())
                if layer == "composition":
                    np.testing.assert_array_equal(cli["LAYERS"].read(), desktop["LAYERS"].read())
            desktop_wcs, cli_wcs = (WCS(fits.getheader(path)) for path in (destination, cli_output))
            assert cli_wcs.has_celestial == desktop_wcs.has_celestial == (layer == "sky")
            if layer == "sky":
                points = ([0, 40, 79], [0, 30, 59])
                np.testing.assert_allclose(
                    cli_wcs.pixel_to_world_values(*points),
                    desktop_wcs.pixel_to_world_values(*points),
                    atol=1e-9,
                    rtol=0,
                )

        def select_zea() -> None:
            dialog = QApplication.activeModalWidget()
            assert isinstance(dialog, ProjectSettings)
            assert dialog.projection.currentData() == "TAN"
            dialog.projection.setCurrentIndex(dialog.projection.findData("ZEA"))
            dialog.accept()

        ground = window.project.foreground
        window.layer_box.setCurrentText("Sky")
        QTimer.singleShot(0, select_zea)
        window.settings_button.click()
        assert window.project.render.projection == "ZEA"
        assert window.project.composition is None and window.project.foreground == ground
        assert "ICRS ZEA" in window.grid_summary.text()
        save.trigger()
        open_action.trigger()
        assert window.project.render.projection == "ZEA"
        assert window.project.composition is None
    finally:
        for job in (window.job, window._inspection_job):
            if job is not None:
                job.cancel()
                assert job.wait(10_000)
        window.deleteLater()
        app.processEvents()
