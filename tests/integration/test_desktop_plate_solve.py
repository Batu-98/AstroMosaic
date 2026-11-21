import os
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from threading import Event, get_ident

import numpy as np
import pytest
from astropy.io import fits

from astromosaic.astrometry import solve
from astromosaic.astrometry.astap_probe import AstapCandidate
from astromosaic.astrometry.gaia_solve import GaiaCandidate
from astromosaic.astrometry.hints import PanelOptics
from astromosaic.astrometry.solve import SolveOptions, SolverAttempt, SolveResult, write_solution
from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.core.masks import FOREGROUND, SKY, SourceMask
from astromosaic.geometry import read_panel_geometry, tan_output_wcs
from astromosaic.io import open_panel
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.storage.project import FileReference, MosaicProject, ProjectPanel, load_project


def test_desktop_plate_solve_skips_reusable_wcs_and_retries_unsolved_panels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stub_solve_evidence: None,
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEventLoop, QStandardPaths, Qt, QTimer
    from PySide6.QtWidgets import QApplication, QFileDialog

    from astromosaic.ui import project_window

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)

    size, center = (32, 24), (359.999, 20.0)
    header = tan_output_wcs(center, size, 2.0, 0, Region(0, 0, *size)).to_header()
    shape = (size[1], size[0])
    metadata = fits.Header({"FILTER": "L", "BUNIT": "MJy/sr", "RA": center[0], "DEC": center[1]})
    paths = [tmp_path / f"panel-{index}.fits" for index in range(6)]
    for index, path in enumerate(paths):
        image_header = header + metadata if index == 0 else metadata.copy()
        image_header["PANELID"] = index
        fits.writeto(path, np.full(shape, 5.0, dtype=np.float32), image_header)
    originals = [path.read_bytes() for path in paths]

    panels = [ProjectPanel(FileReference.capture(path)) for path in paths]
    previous = tmp_path / "reusable.wcs.json"
    with open_panel(paths[1]) as source:
        geometry = read_panel_geometry(header, *size)
        reuse = SolveResult(geometry, "gaia-dr3", (SolverAttempt("gaia-dr3", "solved", "fixture"),))
        write_solution(previous, source, reuse)
    panels[1] = replace(panels[1], wcs_sidecar=FileReference.capture(previous))
    old_sidecar = tmp_path / "stale.wcs.json"
    old_sidecar.write_text("{}", encoding="utf-8")
    panels[2] = replace(panels[2], include_sky=False)
    mask = SourceMask(size, bytes((SKY,)) * (32 * 12) + bytes((FOREGROUND,)) * (32 * 12))
    panels[3] = replace(panels[3], source_mask=mask, optics=PanelOptics(412, 4.0, 4.0))
    panels[4] = replace(panels[4], wcs_sidecar=FileReference.capture(old_sidecar))
    project = MosaicProject(tuple(panels), RenderSpec(center, size, 2.0))

    gaia_catalog = tmp_path / "gaia.bin"
    gaia_index = tmp_path / "gaia.idx"
    gaia_catalog.touch()
    gaia_index.touch()
    astap_executable = tmp_path / "astap_cli.exe"
    options = SolveOptions(
        gaia_catalog=gaia_catalog,
        gaia_index=gaia_index,
        astap=astap_executable,
        astap_catalog=tmp_path,
    )
    monkeypatch.setattr(project_window, "load_plate_solve_settings", lambda: options)

    main_thread = get_ident()
    waiting = Event()
    retry = Event()
    calls: list[tuple[int, str]] = []

    def coordinates(run: solve._PanelSolve) -> list[tuple[float, float, float]]:
        source = run.source
        index = int(source.header["PANELID"])
        if index == 3:
            assert run.options.optics == panels[3].optics
            assert source.sky_mask_fingerprint == mask.sky_fingerprint
            assert not source.read_tile(Region(0, 15, 1, 1)).valid[0, 0]
        return [(float(index), 0.0, 10.0)] * 20

    def gaia(
        catalog: Path,
        _index: Path | None,
        _size: tuple[int, int],
        measured: list[tuple[float, float, float]],
        position: tuple[float, float] | None,
        scale: float | None,
        _seconds: float,
        context: JobContext,
    ) -> GaiaCandidate:
        assert get_ident() != main_thread and catalog == gaia_catalog
        index = int(measured[0][0])
        calls.append((index, "gaia"))
        if index == 3:
            assert position == center and scale is not None
            return GaiaCandidate(
                header.tostring(sep="\n", padding=False), "test", "test", 20, 0.2, 0
            )
        if index == 5 and not retry.is_set():
            waiting.set()
            while not retry.wait(0.01):
                context.check_cancelled()
            context.check_cancelled()
        raise ValueError("Gaia found no match.")

    def astap(
        executable: Path,
        catalog: Path,
        stage: Callable[[Path], None],
        *,
        position: tuple[float, float] | None,
        **kwargs: object,
    ) -> AstapCandidate:
        assert executable == astap_executable and catalog == tmp_path
        assert callable(stage)
        calls.append((-1, "astap"))
        if not retry.is_set():
            raise ValueError("ASTAP found no match.")
        assert position == center
        return AstapCandidate(header, "CLI-test", "d05")

    monkeypatch.setattr(solve._PanelSolve, "coordinates", coordinates)
    monkeypatch.setattr(solve, "search_gaia", gaia)
    monkeypatch.setattr(solve, "solve_astap", astap)
    local_data = tmp_path / "local data"
    sidecars = local_data / "wcs"
    manifest = tmp_path / "projects" / "night.astromosaic"
    manifest.parent.mkdir()
    output = tmp_path / "result.fits"
    folder_requests: list[str] = []

    def record_folder_request(_parent: object, title: str, *args: object) -> str:
        folder_requests.append(title)
        return ""

    def writable_location(location: QStandardPaths.StandardLocation) -> str:
        assert location == QStandardPaths.StandardLocation.AppLocalDataLocation
        return str(local_data)

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", record_folder_request)
    monkeypatch.setattr(QStandardPaths, "writableLocation", writable_location)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda parent, title, *args, **kwargs: (
            str(manifest if title == "Save Project As" else output),
            "",
        ),
    )

    window = project_window.ProjectWindow(use_gpu=False)

    def wait_for(condition: Callable[[], bool]) -> None:
        if condition():
            return
        loop = QEventLoop()
        poll, timer = QTimer(), QTimer()
        poll.timeout.connect(lambda: loop.quit() if condition() else None)
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        poll.start(10)
        timer.start(15_000)
        loop.exec()
        assert condition(), window.status.text()

    try:
        window.show()
        window._set_project(project, None)
        window.command_panel_action.trigger()
        window.plate_solve_button.click()
        assert not folder_requests and window.job is not None
        wait_for(lambda: waiting.is_set() and " / 3 panels" in window.status.text())
        window.cancel_button.click()
        wait_for(lambda: window.job is None and window._inspection_job is None)
        assert window.progress.value() == 66
        assert window.status.text() == "Plate solve cancelled. 1 solved, 1 failed."
        window.command_panel_action.trigger()
        assert window.status.text() in window.command_panel.output.toPlainText().splitlines()
        assert window.panels.cell(3, "Solve result").data() == "Gaia DR3"
        assert "ASTAP found no match." in window.panels.cell(4, "Solve result").data(
            Qt.ItemDataRole.ToolTipRole
        )
        assert window.project.panels[4].wcs_sidecar == panels[4].wcs_sidecar
        assert window.project.panels[5].wcs_sidecar is None
        assert len(list(sidecars.glob("*.wcs.json"))) == 1
        first_solution = window.project.panels[3].wcs_sidecar
        assert first_solution is not None and first_solution.path.parent == sidecars

        window._file_actions[2].trigger()
        assert load_project(manifest) == window.project
        retry.set()
        window.plate_solve_button.click()
        wait_for(lambda: window.job is None and window._inspection_job is None)
        assert window.status.text() == "Plate solve finished. 2 solved, 0 failed."
        assert window.status.text() in window.command_panel.output.toPlainText().splitlines()
        assert window.project.panels[3].wcs_sidecar == load_project(manifest).panels[3].wcs_sidecar
        assert window.project.panels[1].wcs_sidecar == panels[1].wcs_sidecar
        assert window.panels.cell(5, "Solve result").data() == "ASTAP hinted"
        assert [index for index, backend in calls if backend == "gaia"] == [3, 4, 5]
        assert len(list(manifest.with_name("night.astromosaic.wcs").glob("*.wcs.json"))) == 2
        assert old_sidecar.read_text(encoding="utf-8") == "{}"

        assert window._save()
        window._set_project(load_project(manifest), manifest)
        window.plate_solve_button.click()
        wait_for(lambda: window.job is None and window._inspection_job is None)
        assert window.status.text() == "All sky panels already have a usable WCS."
        window.preview_button.click()
        wait_for(lambda: window.job is None)
        assert window.viewport.frame is not None
        window.start_button.click()
        wait_for(lambda: window.job is None)
        assert output.is_file(), window.status.text()
        assert not folder_requests
        assert [path.read_bytes() for path in paths] == originals
        assert not list(tmp_path.rglob("*.part"))
    finally:
        for job in (window.job, window._inspection_job):
            if job is not None:
                job.cancel()
                assert job.wait(15_000)
        window.deleteLater()
        app.processEvents()
