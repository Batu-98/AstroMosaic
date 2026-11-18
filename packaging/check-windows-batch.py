"""Run the batch acceptance cases in a Windows console."""

import argparse
import ctypes
import json
import os
import runpy
import shutil
import signal
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep

import fitsio
import numpy as np
import tifffile
from astropy.io import fits

from astromosaic.geometry import tan_output_wcs
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.storage.project import FileReference, MosaicProject, ProjectPanel, save_project

ROOT = Path(__file__).resolve().parents[1]


def write_batch(path: Path, *entries: tuple[str, str] | tuple[str, str, str]) -> None:
    path.write_text(
        json.dumps(
            [
                {"project": project, "output": output, **({"band": band[0]} if band else {})}
                for project, output, *band in entries
            ]
        ),
        encoding="utf-8",
    )


def read_records(lines: str) -> list[dict[str, object]]:
    records = [json.loads(line) for line in lines.splitlines()]
    assert all(record["schema_version"] == 1 for record in records)
    return records


def run_batch(
    command: list[str], batch: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*command, str(batch)],
        cwd=batch.parent.parent,
        env=env,
        check=False,
        capture_output=True,
        encoding="utf-8",
        timeout=50,
    )


def check_cancel_and_retry(
    command: list[str],
    directory: Path,
    env: dict[str, str],
    total_pixels: int,
) -> None:
    plan = directory / "interrupt.json"
    first = directory / "before interrupt.fits"
    interrupted = directory / "interrupted.fits"
    later = directory / "after interrupt.tiff"
    write_batch(
        plan,
        ("Bands.astromosaic", first.name, "L"),
        ("slow.astromosaic", interrupted.name, "L"),
        ("RGB project.astromosaic", later.name),
    )
    results, events = directory / "results.ndjson", directory / "progress.ndjson"
    with results.open("wb") as output_stream, events.open("wb") as progress_stream:
        child = subprocess.Popen(
            [*command, str(plan)],
            cwd=directory.parent,
            env=env,
            stdout=output_stream,
            stderr=progress_stream,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        try:
            deadline = monotonic() + 30
            while child.poll() is None and monotonic() < deadline:
                complete_lines = events.read_text(encoding="utf-8").rpartition("\n")[0]
                if any(
                    event.get("total_pixels") == total_pixels
                    for event in read_records(complete_lines)
                ):
                    break
                sleep(0.025)
            else:
                raise RuntimeError("The batch did not report progress for the cancellation job.")
            earlier_output = first.read_bytes()
            assert list(directory.glob(".astromosaic-*.part"))
            assert not interrupted.exists()
            child.send_signal(signal.CTRL_BREAK_EVENT)
            exit_code = child.wait(timeout=15)
        finally:
            if child.poll() is None:
                child.send_signal(signal.CTRL_BREAK_EVENT)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)
    reports = read_records(results.read_text(encoding="utf-8"))
    assert exit_code == 130, reports
    assert [report["status"] for report in reports] == ["ok", "cancelled"]
    assert [report["band"] for report in reports] == ["L", "L"]
    assert first.read_bytes() == earlier_output
    assert not interrupted.exists() and not later.exists()
    assert not list(directory.glob(".astromosaic-*.part"))

    retry = directory / "retry.json"
    write_batch(retry, ("slow.astromosaic", interrupted.name, "L"))
    retried = run_batch(command, retry, env)
    assert retried.returncode == 0, retried.stderr
    (report,) = read_records(retried.stdout)
    assert report["status"] == "ok" and report["band"] == "L"
    assert first.read_bytes() == earlier_output
    with fitsio.FITS(interrupted) as hdus:
        assert report["covered_pixels"] == int(hdus["COVERAGE"].read().sum()) > 0


def check_batches(
    command: list[str], directory: Path, env: dict[str, str], raster_check: dict[str, object]
) -> None:
    directory.mkdir()
    spec = RenderSpec((359.999, 20.0), (64, 48), 7.2, tile_size=8)
    target = tan_output_wcs(spec.center, spec.size, spec.scale_arcsec, 0, spec.output_region())
    header = target.to_header()
    header["FILTER"], header["BUNIT"] = "L", "MJy/sr"
    width, height = spec.size
    y, x = np.indices((height, width), dtype=np.float32)
    mono = x - 3 * y
    rgb = np.stack((mono, -mono, 0.5 * mono), axis=-1)
    mono[4, 6] = np.nan
    rgb[12:16, 18:21] = np.nan
    source = directory / "signed FITS panel.fits"
    tiff = directory / "RGB panel.tiff"
    missing = directory / "missing panel.fits"
    fits.writeto(source, mono, header)
    fits.writeto(missing, mono, header)
    tifffile.imwrite(
        tiff,
        rgb,
        photometric="rgb",
        tile=(16, 16),
        compression="deflate",
        predictor=3,
        metadata=None,
        description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False),
    )
    slow = replace(spec, size=(256, 192), tile_size=4)
    for name, image, settings in (
        ("Gökyüzü", source, spec),
        ("RGB project", tiff, spec),
        ("missing", missing, spec),
        ("slow", source, slow),
    ):
        project = MosaicProject((ProjectPanel(FileReference.capture(image)),), settings)
        save_project(directory / f"{name}.astromosaic", project)
    bands = MosaicProject(
        (
            ProjectPanel(FileReference.capture(source)),
            ProjectPanel(FileReference.capture(tiff), band_override="O III"),
        ),
        spec,
    )
    save_project(directory / "Bands.astromosaic", bands)
    missing.rename(directory / "moved panel.fits")
    original_sources = (source.read_bytes(), tiff.read_bytes())

    occupied = directory / "occupied.fits"
    occupied.write_bytes(b"Previous output")
    plan = directory / "batch.json"
    write_batch(
        plan,
        ("Bands.astromosaic", "sky output.fits", "L"),
        ("missing.astromosaic", "missing output.fits"),
        ("Gökyüzü.astromosaic", occupied.name),
        ("Bands.astromosaic", "RGB output.tiff", "O III"),
    )
    outcome = run_batch(command, plan, env)
    assert outcome.returncode == 1, outcome.stderr
    reports = read_records(outcome.stdout)
    assert [report["status"] for report in reports] == ["ok", "error", "error", "ok"]
    assert reports[0]["band"] == "L" and reports[3]["band"] == "O III"
    assert "Source file is missing" in str(reports[1]["message"])
    assert "already exists" in str(reports[2]["message"])
    assert occupied.read_bytes() == b"Previous output"
    assert not (directory / "missing output.fits").exists()
    events = read_records(outcome.stderr)
    progress = [event for event in events if event["event"] == "progress"]
    assert len(progress) > 2
    assert sum(event["completed_pixels"] == width * height for event in progress) == 2
    check_raster = raster_check["check_raster"]
    assert callable(check_raster)
    check_raster(directory / "sky output.fits", mono, target, reports[0])
    check_raster(directory / "RGB output.tiff", rgb, target, reports[3])

    check_cancel_and_retry(command, directory, env, slow.size[0] * slow.size[1])
    assert (source.read_bytes(), tiff.read_bytes()) == original_sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Directory containing astromosaic-cli.exe.")
    parser.add_argument("--pwsh", default="pwsh", help="PowerShell 7 executable.")
    args = parser.parse_args()
    pwsh = shutil.which(args.pwsh)
    if pwsh is None:
        parser.error("PowerShell 7 is required to run the PowerShell batch checks.")
    if sys.platform != "win32" or ctypes.windll.kernel32.GetConsoleCP() == 0:
        parser.error("Start this acceptance check from a Windows console to test Ctrl+Break.")
    windows = Path(os.environ["SystemRoot"])
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("PYTHON", "QT_", "CONDA", "VIRTUAL_ENV", "_PYI_"))
    }
    env["PATH"] = f"{windows / 'System32'};{windows}"
    raster_check = runpy.run_path(str(ROOT / "packaging" / "check-windows-cli.py"))

    with TemporaryDirectory(prefix="AstroMosaic batch check ") as scratch:
        directory = Path(scratch)
        runtime = directory / "portable"
        shutil.copytree(args.bundle.resolve(), runtime)
        assert not list(runtime.rglob("Qt6Core.dll")), "The headless bundle contains Qt."
        cli = runtime / "astromosaic-cli.exe"
        powershell = [
            pwsh,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(ROOT / "examples/export-batch.ps1"),
        ]
        python = [sys.executable, str(ROOT / "examples/export_batch.py")]
        for label, command in (
            ("Python installed CLI", python),
            ("Python portable CLI", [*python, "--cli", str(cli)]),
            ("PowerShell installed CLI", [*powershell, "-Python", sys.executable, "-Batch"]),
            ("PowerShell portable CLI", [*powershell, "-Cli", str(cli), "-Batch"]),
        ):
            check_batches(command, directory / label, env, raster_check)
            print(
                f"{label} passed band exports, progress, failure, cancellation and retry.",
                flush=True,
            )


if __name__ == "__main__":
    main()
