import json
import signal
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import tifffile
from astropy.io import fits

from astromosaic.cli import main
from astromosaic.cli import project as project_cli
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
