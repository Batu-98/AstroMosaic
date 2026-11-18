"""Generate and measure the Phase 4B full-size Windows CLI fixtures."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import signal
import subprocess
import sys
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep
from typing import Literal, TypedDict

import fitsio
import numpy as np
import tifffile
from astropy.io import fits
from astropy.wcs import WCS
from numpy.typing import NDArray

from astromosaic.core import Region
from astromosaic.core.masks import FOREGROUND, SKY, SourceMask, bounded_grid
from astromosaic.geometry import tan_output_wcs
from astromosaic.geometry.image import CompositionSpec, LayerPlacement
from astromosaic.pipeline.foreground import ForegroundAlignment, GroundPanel
from astromosaic.pipeline.mosaic import MIB, RenderSpec
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    SavedForeground,
    load_project,
    save_project,
)

type Case = Literal["fits", "rgb-tiff", "mixed"]

CASES = ("fits", "rgb-tiff", "mixed")
PANEL_SIZE = (6000, 4000)
STEP = (4096, 2560)
COLUMNS, ROWS = 4, 3
SIZE = (PANEL_SIZE[0] + (COLUMNS - 1) * STEP[0], PANEL_SIZE[1] + (ROWS - 1) * STEP[1])
CENTER = (359.999, 20.0)
SCALE = 2.0
GROUND_HEIGHT = 2000
OVERLAP = 256
HOLES = (Region(8190, 3500, 48, 32), Region(10047, 6972, 13, 7))


def offsets() -> list[tuple[int, int]]:
    return [(column * STEP[0], row * STEP[1]) for row in range(ROWS) for column in range(COLUMNS)]


def field(
    x: NDArray[np.float32] | NDArray[np.float64], y: NDArray[np.float32] | NDArray[np.float64]
) -> NDArray[np.float32]:
    return np.asarray((x - 8192) / 512 + (y - 4096) / 1024, dtype=np.float32)


def channels(mono: NDArray[np.float32]) -> NDArray[np.float32]:
    rgb = np.empty((*mono.shape, 3), dtype=np.float32)
    rgb[..., 0] = mono
    np.multiply(mono, -0.5, out=rgb[..., 1])
    rgb[..., 1] += 3
    np.multiply(mono, 2.0, out=rgb[..., 2])
    rgb[..., 2] -= 1
    return rgb


def output_name(case: Case) -> str:
    return "mosaic.fits" if case == "fits" else "mosaic.tiff"


def prepare(case: Case, directory: Path) -> None:
    directory.mkdir(parents=True)
    output_limit = 3072 if case == "rgb-tiff" else 2048
    spec = RenderSpec(CENTER, SIZE, SCALE, max_output_bytes=output_limit * MIB)
    header = tan_output_wcs(CENTER, SIZE, SCALE, 0, spec.output_region()).to_header()
    header["FILTER"], header["BUNIT"] = "L", "MJy/sr"
    width, height = PANEL_SIZE
    grid_width, grid_height = bounded_grid(PANEL_SIZE, 384)
    labels = np.full((grid_height, grid_width), SKY, dtype=np.uint8)
    labels[grid_height // 2 :] = FOREGROUND
    mixed_mask = SourceMask(PANEL_SIZE, labels.tobytes())
    layout = offsets()
    panels = []
    for index, (left, top) in enumerate(layout):
        x = np.arange(left, left + width, dtype=np.float32)
        y = np.arange(top, top + height, dtype=np.float32)[:, None]
        mono = field(x, y)
        for hole in HOLES:
            mono[
                (y >= hole.y)
                & (y < hole.y + hole.height)
                & (x >= hole.x)
                & (x < hole.x + hole.width)
            ] = np.nan
        rgb = case == "rgb-tiff"
        fractional = 0.25 if rgb else 0.0
        panel_header = header.copy()
        panel_header["CRPIX1"] = header["CRPIX1"] - left + fractional
        panel_header["CRPIX2"] = header["CRPIX2"] - top + fractional
        is_tiff = rgb or (case == "mixed" and index % 2 == 1)
        path = directory / f"panel-{index + 1:02d}{'.tiff' if is_tiff else '.fits'}"
        if is_tiff:
            tifffile.imwrite(
                path,
                channels(mono) if rgb else mono,
                photometric="rgb" if rgb else "minisblack",
                tile=(128, 128),
                compression="deflate",
                compressionargs={"level": 1},
                predictor=3,
                maxworkers=1,
                metadata=None,
                description="AstroMosaic TIFF 1\n" + panel_header.tostring(sep="\n", padding=False),
            )
        else:
            fits.writeto(path, mono, panel_header)
        mask = mixed_mask if case == "mixed" and index >= COLUMNS * (ROWS - 1) else None
        panels.append(ProjectPanel(FileReference.capture(path), 1.0 + index % 3, source_mask=mask))

    project = MosaicProject(tuple(panels), spec)
    if case == "mixed":
        ground_inputs = project.foreground_inputs()
        ground = ForegroundAlignment(
            PANEL_SIZE,
            Region(0, height - GROUND_HEIGHT, SIZE[0], GROUND_HEIGHT),
            tuple(GroundPanel(index, (float(layout[index][0]), 0.0)) for index, _ in ground_inputs),
            (),
        )
        sky_height = SIZE[1] - GROUND_HEIGHT
        project = replace(
            project,
            foreground=SavedForeground(project.foreground_key(ground_inputs), ground),
            composition=CompositionSpec(
                LayerPlacement((0.0, sky_height - OVERLAP)),
                seam_y=sky_height - OVERLAP / 2 - 0.5,
                overlap_percent=100 * OVERLAP / GROUND_HEIGHT,
                sky_crop_bottom=GROUND_HEIGHT,
            ),
        )
    save_project(directory / "reference.astromosaic", project)
    print(f"Prepared {case} with {len(panels)} inputs of {width} x {height} pixels.", flush=True)


class _MemoryCounters(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
        (name, ctypes.c_size_t)
        for name in (
            "peak_working",
            "working",
            "peak_paged",
            "paged",
            "peak_nonpaged",
            "nonpaged",
            "commit",
            "peak_commit",
        )
    ]


class _ProgressEvent(TypedDict):
    completed_pixels: int
    total_pixels: int


def _progress(path: Path) -> list[_ProgressEvent]:
    complete = path.read_text(encoding="utf-8").rpartition("\n")[0]
    events = [json.loads(line) for line in complete.splitlines()]
    return [event for event in events if event["event"] == "progress"]


def run_export(
    cli: Path, manifest: Path, destination: Path, layer: str, *, cancel: bool = False
) -> dict[str, object]:
    """Measure the onedir console process and keep its raw result and progress."""
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    prefix = destination.with_name(destination.stem + ("-cancel" if cancel else ""))
    result_path, events_path = (
        prefix.with_suffix(".result.json"),
        prefix.with_suffix(".events.ndjson"),
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("PYTHON", "QT_", "CONDA", "VIRTUAL_ENV", "_PYI_"))
    }
    windows = Path(os.environ["SystemRoot"])
    env.update(
        PATH=f"{windows / 'System32'};{windows}", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1"
    )
    command = [
        str(cli.resolve()),
        "project",
        "export",
        str(manifest),
        "-o",
        str(destination),
        "--layer",
        layer,
        "--json",
        "--progress",
    ]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.K32GetProcessMemoryInfo.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_MemoryCounters),
        wintypes.DWORD,
    )
    kernel.K32GetProcessMemoryInfo.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    peak_working = peak_commit = 0
    incremental = False
    interrupted_at = None
    completed_at_interrupt = None
    started = monotonic()
    with result_path.open("xb") as stdout, events_path.open("xb") as stderr:
        child = subprocess.Popen(
            command,
            env=env,
            stdout=stdout,
            stderr=stderr,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        handle = kernel.OpenProcess(0x0410, False, child.pid)  # Query information and VM read.
        try:
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            counters = _MemoryCounters(size=ctypes.sizeof(_MemoryCounters))
            while child.poll() is None:
                if kernel.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.size):
                    peak_working = max(peak_working, counters.peak_working)
                    peak_commit = max(peak_commit, counters.peak_commit)
                if not incremental:
                    events = _progress(events_path)
                    if (
                        events
                        and not destination.exists()
                        and any(destination.parent.glob(".astromosaic-*.part"))
                    ):
                        incremental = True
                        if cancel:
                            interrupted_at = monotonic()
                            completed_at_interrupt = events[-1]["completed_pixels"]
                            child.send_signal(signal.CTRL_BREAK_EVENT)
                sleep(0.15)
        finally:
            if handle:
                kernel.CloseHandle(handle)
            if child.poll() is None:
                try:
                    child.send_signal(signal.CTRL_BREAK_EVENT)
                    child.wait(timeout=15)
                except (OSError, subprocess.TimeoutExpired):
                    child.kill()
                    child.wait(timeout=10)
    elapsed = monotonic() - started
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if child.returncode != (130 if cancel else 0):
        raise RuntimeError(f"The CLI exited with {child.returncode}. {result}")
    events = _progress(events_path)
    completed = [event["completed_pixels"] for event in events]
    assert incremental and completed == sorted(set(completed)) and 1 <= len(events) <= 21
    assert not list(destination.parent.glob(".astromosaic-*.part"))
    assert peak_working > 0 and peak_commit > 0
    report = {
        "elapsed_seconds": elapsed,
        "peak_working_set_bytes": peak_working,
        "peak_commit_bytes": peak_commit,
        "progress_events": len(events),
        "temporary_output_during_progress": incremental,
        "result": result,
    }
    if cancel:
        assert interrupted_at is not None and result["status"] == "cancelled"
        assert not destination.exists()
        report.update(
            cancelled_after_pixels=completed_at_interrupt,
            cancellation_seconds=monotonic() - interrupted_at,
        )
    else:
        project = load_project(manifest)
        assert 0 < result["peak_reserved_bytes"] <= project.render.max_working_bytes
        assert completed[-1] == result["width"] * result["height"]
        report["output_bytes"] = destination.stat().st_size
    with prefix.with_suffix(".metrics.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    return report


def _valid_taps(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    last_x: NDArray[np.float64],
    last_y: NDArray[np.float64],
) -> NDArray[np.bool_]:
    valid = np.ones((len(y), len(x)), dtype=np.bool_)
    for hole in HOLES:
        valid &= ~(
            (x < hole.x + hole.width)
            & (last_x >= hole.x)
            & (y < hole.y + hole.height)
            & (last_y >= hole.y)
        )
    return valid


def _rgb_truth(region: Region) -> tuple[NDArray[np.float32], NDArray[np.bool_]]:
    """Apply an independent bilinear reference using the known global 0.25 px offset."""
    shape = region.height, region.width
    summed = np.zeros(shape, dtype=np.float64)
    total_weight = np.zeros(shape, dtype=np.float64)
    for index, (left, top) in enumerate(offsets()):
        right, bottom = left + PANEL_SIZE[0], top + PANEL_SIZE[1]
        x0, x1 = max(region.x, left), min(region.x + region.width, right)
        y0, y1 = max(region.y, top), min(region.y + region.height, bottom)
        if x0 >= x1 or y0 >= y1:
            continue
        x = np.arange(x0, x1, dtype=np.float64)
        y = np.arange(y0, y1, dtype=np.float64)[:, None]
        # The known gradient is linear between taps. Clamp to the outer sample at the edge.
        samples = field(np.minimum(x + 0.25, right - 1), np.minimum(y + 0.25, bottom - 1))
        valid = _valid_taps(x, y, np.minimum(x + 1, right - 1), np.minimum(y + 1, bottom - 1))
        weight = (1 + index % 3) * valid
        section = np.s_[y0 - region.y : y1 - region.y, x0 - region.x : x1 - region.x]
        summed[section] += samples * weight
        total_weight[section] += weight
    valid = total_weight > 0
    mono = np.full(shape, np.nan, dtype=np.float32)
    np.divide(summed, total_weight, out=mono, where=valid)
    return channels(mono), valid


def _expected_rows(
    case: Case, region: Region
) -> tuple[NDArray[np.float32], NDArray[np.bool_], NDArray[np.uint8] | None, int]:
    if case == "rgb-tiff":
        rgb, valid = _rgb_truth(region)
        return rgb, valid, None, 0
    x = np.arange(region.x, region.x + region.width, dtype=np.float64)
    y = np.arange(region.y, region.y + region.height, dtype=np.float64)[:, None]
    sky = field(x, y)
    sky_valid = _valid_taps(x, y, x, y)
    if case == "fits":
        sky[~sky_valid] = np.nan
        return sky, sky_valid, None, 0

    sky_height = SIZE[1] - GROUND_HEIGHT
    sky_valid &= y < sky_height
    ground_y = y + OVERLAP
    ground_valid = _valid_taps(x, ground_y, x, ground_y) & (ground_y >= sky_height)
    common = sky_valid & ground_valid
    # The saved feather runs over the 256 rows where the two layers overlap.
    sky_weight = np.clip((sky_height - 0.5 - y) / OVERLAP, 0, 1)
    sky_weight = sky_weight**2 * (3 - 2 * sky_weight)
    ground = field(x, ground_y)
    pixels = np.where(sky_valid, sky, ground)
    blend = sky * sky_weight + ground * (1 - sky_weight)
    pixels[common] = blend[common]
    valid = sky_valid | ground_valid
    pixels[~valid] = np.nan
    layers = sky_valid.astype(np.uint8) + 2 * ground_valid.astype(np.uint8)
    return pixels, valid, layers, int(common.sum())


def _check_wcs(header: fits.Header, region: Region, case: Case) -> float | None:
    wcs = WCS(header)
    if case == "mixed":
        assert not wcs.has_celestial
        return None
    assert wcs.has_celestial and not wcs.has_distortion
    x = np.array([0, region.width - 1, (region.width - 1) / 2], dtype=np.float64)
    y = np.array([0, region.height - 1, (region.height - 1) / 2], dtype=np.float64)
    # Invert an undistorted north-up TAN projection independently of the input headers.
    xi = np.deg2rad(-(x + region.x - (SIZE[0] - 1) / 2) * SCALE / 3600)
    eta = np.deg2rad((y + region.y - (SIZE[1] - 1) / 2) * SCALE / 3600)
    ra0, dec0 = np.deg2rad(CENTER)
    radius = np.cos(dec0) - eta * np.sin(dec0)
    ra = np.rad2deg(ra0 + np.arctan2(xi, radius)) % 360
    dec = np.rad2deg(np.arctan2(np.sin(dec0) + eta * np.cos(dec0), np.hypot(radius, xi)))
    deltas = np.asarray(wcs.pixel_to_world_values(x, y)) - np.stack((ra, dec))
    deltas[0] = (deltas[0] + 180) % 360 - 180
    error = float(np.max(np.abs(deltas)))
    assert error <= 1e-9
    return error


def _verify_rows(
    case: Case,
    region: Region,
    pixels: Callable[[slice], NDArray[np.float32]],
    coverage: Callable[[slice], NDArray[np.uint8]],
    layers: Callable[[slice], NDArray[np.uint8]] | None = None,
) -> dict[str, object]:
    covered = common = 0
    contribution_counts = np.zeros(4, dtype=np.int64)
    max_error = 0.0
    for start in range(0, region.height, 64):
        stop = min(start + 64, region.height)
        rows = slice(start, stop)
        strip = Region(region.x, region.y + start, region.width, stop - start)
        expected, valid, contributions, shared = _expected_rows(case, strip)
        samples = pixels(rows)
        actual_coverage = coverage(rows)
        assert samples.dtype.kind == "f" and samples.dtype.itemsize == 4
        assert actual_coverage.dtype == np.uint8
        np.testing.assert_array_equal(
            actual_coverage, valid, err_msg=f"Coverage rows {start}:{stop}"
        )
        np.testing.assert_allclose(
            samples, expected, atol=8e-6, rtol=0, err_msg=f"Samples rows {start}:{stop}"
        )
        if valid.any():
            max_error = max(max_error, float(np.max(np.abs(samples[valid] - expected[valid]))))
        if layers is not None:
            assert contributions is not None
            actual_layers = layers(rows)
            np.testing.assert_array_equal(actual_layers, contributions)
            contribution_counts += np.bincount(actual_layers.ravel(), minlength=4)
        covered += int(valid.sum())
        common += shared
    return {
        "pixels_checked": region.width * region.height,
        "covered_pixels": covered,
        "common_pixels": common if layers is not None else None,
        "max_sample_error": max_error,
        "contribution_counts": contribution_counts.tolist() if layers is not None else None,
    }


def verify_export(case: Case, destination: Path, region: Region) -> dict[str, object]:
    """Reopen science and mask rasters in strips using independent FITS and TIFF readers."""
    if case == "fits":
        with fitsio.FITS(destination) as hdus:
            assert tuple(hdus[0].get_dims()) == (region.height, region.width)
            wcs_error = _check_wcs(fits.getheader(destination), region, case)
            report = _verify_rows(
                case, region, lambda rows: hdus[0][rows, :], lambda rows: hdus["COVERAGE"][rows, :]
            )
    else:
        with tifffile.TiffFile(destination) as opened:
            page = opened.pages[0]
            assert isinstance(page, tifffile.TiffPage) and page.pages is not None
            assert (page.imagelength, page.imagewidth) == (region.height, region.width)
            header = fits.Header.fromstring(page.description.split("\n", 1)[1], sep="\n")
            wcs_error = _check_wcs(header, region, case)
            pages = [page, *page.pages]
            assert len(pages) == (3 if case == "mixed" else 2)
            for raster in pages:
                assert isinstance(raster, tifffile.TiffPage) and raster.is_memmappable
            arrays = [raster.asarray(out="memmap") for raster in pages]
            report = _verify_rows(
                case,
                region,
                arrays[0].__getitem__,
                arrays[1].__getitem__,
                arrays[2].__getitem__ if case == "mixed" else None,
            )
    report["max_wcs_error_deg"] = wcs_error
    return report


def check_halo(cli: Path, directory: Path) -> dict[str, object]:
    """Check mismatched output tile edges and forced subdivisions on the RGB inputs."""
    project = load_project(directory / "reference.astromosaic")
    crop = Region(8017, 3341, 513, 385)
    spec = replace(project.render, crop=crop, tile_size=193, max_working_bytes=6 * MIB)
    scratch = directory / "halo"
    scratch.mkdir()
    manifest = scratch / "halo.astromosaic"
    destination = scratch / "halo.tiff"
    save_project(manifest, replace(project, render=spec))
    measured = run_export(cli, manifest, destination, "sky")
    result = measured["result"]
    assert isinstance(result, dict) and result["tiles"] > 6
    return {"measurement": measured, "verification": verify_export("rgb-tiff", destination, crop)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generator = commands.add_parser("prepare", help="Write a new synthetic workload directory.")
    runner = commands.add_parser("run", help="Measure the full saved project export.")
    verifier = commands.add_parser("verify", help="Reopen and verify the full exported raster.")
    halo = commands.add_parser("halo", help="Check split output tiles on the prepared RGB case.")
    for command in (generator, runner, verifier):
        command.add_argument("case", choices=CASES)
    for command in (generator, runner, verifier, halo):
        command.add_argument("directory", type=Path)
    for command in (runner, halo):
        command.add_argument(
            "--cli", required=True, type=Path, help="Portable astromosaic-cli.exe."
        )
    runner.add_argument(
        "--cancel", action="store_true", help="Cancel the export after live progress."
    )
    generator.add_argument(
        "--reuse", type=Path, help="Reuse the saved inputs and settings of the same reference case."
    )
    verifier.add_argument(
        "--baseline", type=Path, help="Case directory for an exact prior-export comparison."
    )
    args = parser.parse_args()
    directory = args.directory.resolve()
    if args.command == "prepare":
        if args.reuse is None:
            prepare(args.case, directory)
        else:
            project = load_project(args.reuse.resolve() / "reference.astromosaic")
            directory.mkdir(parents=True)
            save_project(directory / "reference.astromosaic", project)
            print(f"Reused the saved {args.case} reference in {directory}.", flush=True)
        return
    if args.command == "verify":
        project = load_project(directory / "reference.astromosaic")
        assert len(project.panels) == 12
        assert all(panel.source.status() == "Ready" for panel in project.panels)
        height = SIZE[1] - OVERLAP if args.case == "mixed" else SIZE[1]
        destination = directory / output_name(args.case)
        verified = verify_export(args.case, destination, Region(0, 0, SIZE[0], height))
        measured = json.loads((directory / "mosaic.metrics.json").read_text(encoding="utf-8"))
        for key in ("covered_pixels", "common_pixels"):
            assert verified[key] == measured["result"][key]
        if args.baseline is not None:
            baseline: Path = args.baseline.resolve()
            assert load_project(baseline / "reference.astromosaic") == project
            with (
                (baseline / output_name(args.case)).open("rb") as reference,
                destination.open("rb") as output,
            ):
                digest = hashlib.file_digest(output, "sha256").hexdigest()
                assert digest == hashlib.file_digest(reference, "sha256").hexdigest()
            verified["matching_export_sha256"] = digest
        print(json.dumps(verified, indent=2), flush=True)
        return
    if sys.platform != "win32":
        parser.error("The benchmark's process memory counters require Windows.")
    if args.command == "run" and args.cancel and ctypes.windll.kernel32.GetConsoleCP() == 0:
        parser.error("Start the cancellation check from a Windows console.")
    if args.command == "halo":
        print(json.dumps(check_halo(args.cli, directory), indent=2), flush=True)
        return
    measured = run_export(
        args.cli,
        directory / "reference.astromosaic",
        directory / output_name(args.case),
        "composition" if args.case == "mixed" else "sky",
        cancel=args.cancel,
    )
    print(json.dumps(measured, indent=2), flush=True)


if __name__ == "__main__":
    main()
