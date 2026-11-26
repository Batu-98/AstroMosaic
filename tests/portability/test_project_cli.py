import json
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import tifffile
from astropy.io import fits

from astromosaic.cli import main
from astromosaic.cli import project as project_cli
from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.pipeline.smoke import write_smoke_panel
from astromosaic.storage.project import load_project


def _create_args(manifest: Path, *panels: Path) -> list[str]:
    return [
        "project",
        "create",
        *map(str, panels),
        "-o",
        str(manifest),
        "--center",
        "359.999",
        "20",
        "--scale",
        "7.2",
        "--size",
        "12",
        "10",
        "--json",
    ]


def test_create_and_preflight_share_project_io_without_qt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "Gökyüzü panel.fits"
    write_smoke_panel(source)
    mask = tmp_path / "sky mask.fits"
    fits.writeto(mask, np.ones((12, 16), dtype=np.uint8))
    sidecar = tmp_path / "solution.wcs.json"
    assert main(["solve", str(source), "--sky-mask", str(mask), "-o", str(sidecar)]) == 0
    capsys.readouterr()
    tiff = tmp_path / "linear.tiff"
    header = fits.getheader(source)
    for key in ("BSCALE", "BZERO", "BLANK"):
        del header[key]
    tifffile.imwrite(
        tiff,
        np.ones((12, 16), dtype=np.float32),
        photometric="minisblack",
        metadata=None,
        description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False),
    )
    original = [path.read_bytes() for path in (source, mask, sidecar, tiff)]
    manifest = tmp_path / "Night.astromosaic"
    assert (
        main(
            [
                *_create_args(manifest, source, tiff),
                "--sky-mask",
                f"1={mask}",
                "--wcs",
                f"1={sidecar}",
                "--weights",
                "1",
                "2",
                "--crop",
                "1",
                "2",
                "8",
                "6",
                "--refine",
            ]
        )
        == 0
    )
    create = capsys.readouterr()
    assert create.err == ""
    assert json.loads(create.out) == {
        "schema_version": 1,
        "command": "project create",
        "status": "ok",
        "project": str(manifest),
        "panels": 2,
    }
    saved = load_project(manifest)
    assert saved.panels[0].source.path == source
    assert saved.panels[0].sky_mask is not None and saved.panels[0].sky_mask.path == mask
    assert saved.panels[0].wcs_sidecar is not None and saved.panels[0].wcs_sidecar.path == sidecar
    assert saved.panels[1].weight == 2
    assert saved.refinement is not None
    assert (
        json.loads(manifest.read_text(encoding="utf-8"))["panels"][0]["source"]["path"]
        == source.name
    )

    script = """
import sys

class BlockQt:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'PySide6', 'PyQt6', 'PySide2', 'PyQt5'}:
            raise AssertionError(f'Unexpected Qt import: {fullname}')

sys.meta_path.insert(0, BlockQt())
from astromosaic.cli import main
raise SystemExit(main(sys.argv[1:]))
"""
    output = tmp_path / "mosaic.fits"
    validated = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            "project",
            "validate",
            str(manifest),
            "-o",
            str(output),
            "--json",
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
        timeout=60,
    )
    assert validated.stderr == ""
    assert json.loads(validated.stdout) == {
        "schema_version": 1,
        "command": "project validate",
        "status": "ok",
        "project": str(manifest),
        "layer": "sky",
        "panels": 2,
        "width": 8,
        "height": 6,
        "channels": 1,
    }
    assert not output.exists()
    assert [path.read_bytes() for path in (source, mask, sidecar, tiff)] == original


def test_cli_uses_the_saved_zea_grid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "panel.fits"
    write_smoke_panel(source)
    path = tmp_path / "wide.astromosaic"
    output = tmp_path / "saved-zea.fits"
    options = ["--projection", "zea", "--rotation", "16", "--crop", "2", "1", "8", "7"]
    assert main([*_create_args(path, source), *options]) == 0
    assert load_project(path).render.projection == "ZEA"
    capsys.readouterr()

    assert main(["project", "validate", str(path), "-o", str(output), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "ok" and (report["width"], report["height"]) == (8, 7)
    assert main(["project", "export", str(path), "-o", str(output), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["covered_pixels"] > 0
    assert fits.getheader(output)["CTYPE1"] == "RA---ZEA"

    direct = tmp_path / "direct-zea.fits"
    assert (
        main(
            [
                "mosaic",
                str(source),
                "-o",
                str(direct),
                "--center",
                "359.999",
                "20",
                "--scale",
                "7.2",
                "--size",
                "12",
                "10",
                *options,
            ]
        )
        == 0
    )
    assert direct.read_bytes() == output.read_bytes()


def test_saved_band_reports_select_only_the_requested_panel(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first, second, path = (
        tmp_path / name for name in ("L.fits", "O III.fits", "bands.astromosaic")
    )
    write_smoke_panel(first)
    with fits.open(first, do_not_scale_image_data=True) as original:
        header = original[0].header.copy()
        del header["FILTER"]
        fits.writeto(second, original[0].data, header)
    assert main([*_create_args(path, first, second), "--panel-band", "2=O III"]) == 0
    capsys.readouterr()
    assert main(["project", "bands", str(path), "--json"]) == 0
    listing = json.loads(capsys.readouterr().out)
    assert listing["schema_version"] == 1
    assert listing["bands"] == [{"band": "L", "panels": [1]}, {"band": "O III", "panels": [2]}]
    output = tmp_path / "only O III.fits"
    selected = [str(path), "--band", "O III", "-o", str(output), "--json"]
    assert main(["project", "validate", *selected]) == 0
    checked = json.loads(capsys.readouterr().out)
    assert checked["band"] == "O III" and checked["panels"] == 1
    assert main(["project", "export", *selected, "--progress"]) == 0
    exported = capsys.readouterr()
    assert json.loads(exported.out)["band"] == "O III"
    assert json.loads(exported.err.splitlines()[-1])["completed_pixels"] == 120
    assert fits.getheader(output)["FILTER"] == "O III"


def test_project_command_failures_report_json_and_preserve_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "panel.fits"
    write_smoke_panel(source)
    manifest = tmp_path / "project.astromosaic"
    create = _create_args(manifest, source)
    assert main(create) == 0
    capsys.readouterr()
    original_project, original_source = manifest.read_bytes(), source.read_bytes()

    validate = ["project", "validate", str(manifest), "--json"]
    assert main([*validate, "-o", str(source)]) == 1
    occupied = capsys.readouterr()
    outcome = json.loads(occupied.out)
    assert outcome["status"] == "error"
    assert "already exists" in outcome["message"]
    assert json.loads(occupied.err) == {
        "schema_version": 1,
        "event": "diagnostic",
        "level": "error",
        "message": outcome["message"],
    }
    assert source.read_bytes() == original_source
    assert main(create) == 1
    assert "already exists" in json.loads(capsys.readouterr().out)["message"]
    assert manifest.read_bytes() == original_project
    assert not list(tmp_path.glob("*.part"))

    export = ["project", "export", str(manifest), "--json"]
    assert main([*export, "-o", str(source)]) == 1
    occupied = json.loads(capsys.readouterr().out)
    assert occupied["output"] == str(source)
    assert "already exists" in occupied["message"]
    assert source.read_bytes() == original_source

    source.rename(tmp_path / "moved.fits")
    assert main(validate) == 1
    missing = json.loads(capsys.readouterr().out)
    assert missing["status"] == "error"
    assert "Source file is missing" in missing["message"]
    destination = tmp_path / "missing-input.fits"
    assert main([*export, "-o", str(destination)]) == 1
    assert "Source file is missing" in json.loads(capsys.readouterr().out)["message"]
    assert not destination.exists()


def test_export_reports_saved_dimensions_and_versioned_tile_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "panel.fits"
    write_smoke_panel(source)
    manifest = tmp_path / "project.astromosaic"
    assert main([*_create_args(manifest, source), "--tile-size", "3"]) == 0
    capsys.readouterr()
    original_project, original_source = manifest.read_bytes(), source.read_bytes()

    destination = tmp_path / "mosaic.fits"
    assert (
        main(["project", "export", str(manifest), "-o", str(destination), "--json", "--progress"])
        == 0
    )
    report = capsys.readouterr()
    result = json.loads(report.out)
    assert (result["schema_version"], result["status"], result["layer"]) == (1, "ok", "sky")
    assert result["output"] == str(destination) and result["backend"] == "cpu"
    assert (result["width"], result["height"], result["panels"]) == (12, 10, 1)
    events = [json.loads(line) for line in report.err.splitlines()]
    assert 1 < len(events) <= 21
    done = [event["completed_pixels"] for event in events]
    assert done == sorted(set(done)) and 0 < done[0] < done[-1] == 120
    assert all(
        event["schema_version"] == 1
        and event["event"] == "progress"
        and event["stage"] == "render"
        and event["total_pixels"] == 120
        for event in events
    )
    with fits.open(destination) as reopened:
        assert result["covered_pixels"] == int(reopened["COVERAGE"].data.sum())
    assert manifest.read_bytes() == original_project and source.read_bytes() == original_source


def test_console_interrupt_cleans_export_and_allows_retry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "panel.fits"
    write_smoke_panel(source)
    manifest = tmp_path / "project.astromosaic"
    assert main([*_create_args(manifest, source), "--tile-size", "3"]) == 0
    capsys.readouterr()
    destination = tmp_path / "interrupted.tiff"
    command = ["project", "export", str(manifest), "-o", str(destination), "--json", "--progress"]
    previous_handler = signal.getsignal(signal.SIGINT)
    emit = project_cli._render_progress_event

    def interrupt(done: int, total: int) -> None:
        emit(done, total)
        assert 0 < done < total
        assert signal.getsignal(signal.SIGINT) != previous_handler
        assert list(tmp_path.glob(".astromosaic-*.part")) and not destination.exists()
        signal.raise_signal(signal.SIGINT)

    with monkeypatch.context() as patch:
        patch.setattr(project_cli, "_render_progress_event", interrupt)
        assert main(command) == 130
    result = capsys.readouterr()
    assert json.loads(result.out)["status"] == "cancelled"
    assert [json.loads(line)["event"] for line in result.err.splitlines()] == [
        "progress",
        "diagnostic",
    ]
    assert signal.getsignal(signal.SIGINT) == previous_handler
    assert not destination.exists() and not list(tmp_path.glob("*.part"))

    assert main(command) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok" and destination.is_file()


def test_unsolved_tiff_can_be_saved_for_later_solving(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "unsolved.tif"
    tifffile.imwrite(
        source, np.ones((12, 16, 3), dtype=np.uint16), photometric="rgb", metadata=None
    )
    manifest = tmp_path / "unsolved.astromosaic"
    assert main(_create_args(manifest, source)) == 0
    capsys.readouterr()
    assert main(["project", "validate", str(manifest), "--json"]) == 1
    assert "existing celestial WCS" in json.loads(capsys.readouterr().out)["message"]


def test_project_json_keeps_wcs_diagnostics_off_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "sip.fits"
    write_smoke_panel(source)
    with fits.open(source, mode="update", do_not_scale_image_data=True) as hdus:
        hdus[0].header.update({"A_ORDER": 2, "B_ORDER": 2, "A_2_0": 1e-6, "B_0_2": 1e-6})
    manifest = tmp_path / "project.astromosaic"
    assert main(_create_args(manifest, source)) == 0
    capsys.readouterr()
    assert main(["project", "validate", str(manifest), "--json"]) == 0
    result = capsys.readouterr()
    assert json.loads(result.out)["status"] == "ok"
    events = [json.loads(line) for line in result.err.splitlines()]
    assert any(
        event["event"] == "diagnostic" and "Inconsistent SIP distortion" in event["message"]
        for event in events
    )


def test_cli_relinks_a_saved_project_and_reuses_its_wcs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "Panel source.fits"
    write_smoke_panel(source)
    manifest = tmp_path / "Night.astromosaic"
    assert main(_create_args(manifest, source)) == 0
    before = manifest.read_bytes()
    moved = source.with_name("Panel moved.fits")
    source.rename(moved)
    relinked = tmp_path / "Relinked.astromosaic"
    capsys.readouterr()
    assert (
        main(
            [
                "project",
                "relink",
                str(manifest),
                "--panel",
                f"1={moved}",
                "-o",
                str(relinked),
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["relinked"] == [1]
    assert load_project(relinked).panels[0].source.path == moved

    ready = tmp_path / "Ready.astromosaic"
    assert main(["project", "solve", str(relinked), "-o", str(ready), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["reused"] == [1] and not report["outcomes"]
    assert load_project(ready) == load_project(relinked)
    assert not list(tmp_path.glob("astromosaic-wcs-*")) and manifest.read_bytes() == before


def test_project_solve_checks_reuse_only_for_selected_panels(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from astromosaic.astrometry.solve_budget import SolveBudgetExceeded
    from astromosaic.storage import project as storage

    sources = tuple(tmp_path / f"Panel {number}.fits" for number in (1, 2, 3))
    for source in sources:
        write_smoke_panel(source)
    manifest = tmp_path / "Night.astromosaic"
    assert main(_create_args(manifest, *sources)) == 0
    capsys.readouterr()

    inspect = storage.inspect_project_panel
    inspected = []

    def inspect_panel(panel: storage.ProjectPanel, context: JobContext) -> storage.PanelInspection:
        inspected.append(panel.source.path)
        if panel.source.path == sources[0]:
            raise SolveBudgetExceeded("The job solve budget elapsed.")
        return inspect(panel, context)

    monkeypatch.setattr(storage, "inspect_project_panel", inspect_panel)
    destination = tmp_path / "Selected panels.astromosaic"
    result = main(
        [
            "project", "solve", str(manifest), "-o", str(destination),
            "--panel", "3", "--panel", "2", "--job-budget", "60", "--json",
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert result == 0, report
    assert sorted(inspected) == list(sources[1:])
    assert report["reused"] == [3, 2] and report["outcomes"] == []
    assert load_project(destination) == load_project(manifest)
    assert not list(tmp_path.glob("astromosaic-wcs-*"))


@pytest.mark.parametrize(
    "ending", ["solved", "failed", "cancelled", "cancelled-at-publish", "job-budget-exhausted"]
)
def test_project_solve_publishes_only_complete_results(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    ending: str,
) -> None:
    from astromosaic.astrometry.solve import SolveOptions, SolveResult, SolveStep, write_solution
    from astromosaic.astrometry.solve_budget import SolveBudget
    from astromosaic.geometry import read_panel_geometry
    from astromosaic.io import open_panel
    from astromosaic.storage import project as storage

    sources = tuple(tmp_path / f"Panel {number}.fits" for number in (1, 2))
    for source in sources:
        write_smoke_panel(source)
    manifest = tmp_path / "Night.astromosaic"
    assert main(_create_args(manifest, *sources)) == 0
    capsys.readouterr()
    destination = tmp_path / "Solved night.astromosaic"
    original = [path.read_bytes() for path in (manifest, *sources)]
    paths = []

    def solve(
        index: int,
        panel: storage.ProjectPanel,
        options: SolveOptions,
        directory: Path,
        context: JobContext,
        *,
        job_budget: SolveBudget | None,
        on_step: Callable[[SolveStep], None] | None = None,
    ) -> storage.PanelSolveOutcome:
        assert options.revalidate and job_budget is not None and on_step is None
        if index == 1 and ending == "failed":
            return storage.PanelSolveOutcome(index, error="No match.")
        if index == 1 and ending == "cancelled":
            raise MosaicCancelled("Cancelled between panels.")
        if index == 1 and ending == "job-budget-exhausted":
            return storage.PanelSolveOutcome(
                index,
                error="The job solve budget has no search time after the validation reserve.",
                status="budget-exhausted",
                budget={"limiting_scope": "job"},
            )
        path = directory / f"panel-{index + 1}.wcs.json"
        with open_panel(panel.source.path) as source:
            geometry = read_panel_geometry(source.header, 16, 12)
            write_solution(path, source, SolveResult(geometry, "existing-wcs", ()), context)
        paths.append(path)
        return storage.PanelSolveOutcome(
            index, "existing-wcs", storage.FileReference.capture(path), status="solved"
        )

    monkeypatch.setattr(storage, "solve_project_panel", solve)
    arguments = [
        "project",
        "solve",
        str(manifest),
        "-o",
        str(destination),
        "--job-budget",
        "60",
        "--revalidate",
        "--progress",
        "--json",
    ]
    context = JobContext(
        is_cancelled=lambda: ending == "cancelled-at-publish" and destination.exists()
    )
    code = main(arguments, context=context)
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["outcomes"][0]["panel"] == 1 and report["outcomes"][0]["status"] == "solved"
    assert json.loads(captured.err.splitlines()[1])["completed_panels"] == 1
    assert [path.read_bytes() for path in (manifest, *sources)] == original
    assert not list(tmp_path.rglob("*.part"))
    if ending == "solved":
        assert code == 0 and report["status"] == "ok"
        assert [panel.wcs_sidecar for panel in load_project(destination).panels] == [
            storage.FileReference.capture(path) for path in paths
        ]
        output = tmp_path / "Sky.fits"
        assert main(["project", "export", str(destination), "-o", str(output)]) == 0
        assert np.any(fits.getdata(output, 1) > 0)
    else:
        expected = (130, "cancelled") if ending.startswith("cancelled") else (1, "error")
        assert (code, report["status"]) == expected
        if ending == "job-budget-exhausted":
            assert report["outcomes"][1]["status"] == "budget-exhausted"
            assert "validation reserve" in report["message"]
        assert not destination.exists() and not list(tmp_path.glob("astromosaic-wcs-*"))


def test_cli_prepares_and_exports_a_mixed_project_from_explicit_masks_and_placement(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "mixed.fits"
    write_smoke_panel(source)
    labels = np.ones((12, 16), dtype=np.uint8)
    labels[8:] = 2
    mask_path = tmp_path / "source labels.fits"
    fits.writeto(mask_path, labels)
    project = tmp_path / "masked.astromosaic"
    assert main([*_create_args(project, source), "--label-mask", f"1={mask_path}"]) == 0
    saved = load_project(project)
    assert saved.sky_indices() == (0,) and len(saved.foreground_inputs()) == 1
    assert saved.panels[0].source_mask is not None
    np.testing.assert_array_equal(saved.panels[0].source_mask.grid(), labels)
    before = (project.read_bytes(), source.read_bytes(), mask_path.read_bytes())
    capsys.readouterr()

    ground = tmp_path / "aligned.astromosaic"
    assert main(["project", "align-foreground", str(project), "-o", str(ground), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["panels"] == 1
    placed = tmp_path / "placed.astromosaic"
    assert (
        main(
            [
                "project",
                "set-placement",
                str(ground),
                "-o",
                str(placed),
                "--offset",
                "0",
                "7",
                "--seam",
                "8",
                "--crop-bottom",
                "1",
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["placement"]["sky_crop_bottom"] == 1
    output = tmp_path / "composition.fits"
    assert (
        main(
            [
                "project",
                "export",
                str(placed),
                "--layer",
                "composition",
                "-o",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["covered_pixels"] > 0
    assert np.any(fits.getdata(output, 1) > 0)
    assert before == (project.read_bytes(), source.read_bytes(), mask_path.read_bytes())

    invalid = tmp_path / "wrong-size.fits"
    fits.writeto(invalid, labels[:, :-1])
    undo = tmp_path / "invalid.astromosaic"
    assert main([*_create_args(undo, source), "--label-mask", f"1={invalid}"]) == 1
    assert "mono label mask with 16 x 12" in json.loads(capsys.readouterr().out)["message"]
    assert not undo.exists()
