"""Check a copied Windows CLI bundle against small, independently reopened rasters."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import fitsio
import numpy as np
import tifffile
from astropy.io import fits
from astropy.wcs import WCS
from numpy.typing import NDArray

from astromosaic.core import Region
from astromosaic.geometry import tan_output_wcs
from astromosaic.io import open_panel

SIZE = (64, 48)
CENTER = (359.999, 20.0)
SCALE = 7.2


def run_cli(executable: Path, cwd: Path, *args: str) -> dict[str, object]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("PYTHON", "QT_", "CONDA", "VIRTUAL_ENV"))
    }
    windows = Path(os.environ["SystemRoot"])
    env["PATH"] = f"{windows / 'System32'};{windows}"
    result = subprocess.run(
        [str(executable), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object from the packaged CLI.")
    return payload


def check_mosaic(
    cli: Path,
    cwd: Path,
    source: Path,
    expected: NDArray[np.float32],
    target: WCS,
    output_suffix: str | None = None,
) -> Path:
    destination = cwd / f"{source.stem}-export{output_suffix or source.suffix}"
    width, height = SIZE
    result = run_cli(
        cli,
        cwd,
        "mosaic",
        str(source),
        "-o",
        str(destination),
        "--center",
        *(str(value) for value in CENTER),
        "--size",
        str(width),
        str(height),
        "--scale",
        str(SCALE),
        "--tile-size",
        "13",
    )
    check_raster(destination, expected, target, result)
    return destination


def check_raster(
    destination: Path,
    expected: NDArray[np.float32],
    target: WCS,
    result: dict[str, object],
) -> None:
    assert result["backend"] == "cpu"
    width, height = SIZE
    if destination.suffix == ".fits":
        with fitsio.FITS(destination) as hdus:
            pixels = hdus[0].read()
            coverage = hdus["COVERAGE"].read()
        reopened = WCS(fits.getheader(destination))
    elif destination.suffix == ".xisf":
        with open_panel(destination) as source:
            tile = source.read_tile(Region(0, 0, width, height))
            pixels, coverage = tile.pixels, tile.valid
            assert source.descriptor.filter_name == "L" and source.descriptor.unit == "MJy/sr"
            reopened = WCS(source.header)
    else:
        with tifffile.TiffFile(destination) as tiff:
            page = tiff.pages[0]
            assert isinstance(page, tifffile.TiffPage) and page.pages is not None
            pixels, coverage = page.asarray(), page.pages[0].asarray()
            header = fits.Header.fromstring(page.description.split("\n", 1)[1], sep="\n")
        reopened = WCS(header)
    np.testing.assert_array_equal(pixels, expected)
    valid = np.isfinite(expected)
    if expected.ndim == 3:
        valid = valid.all(axis=-1)
    np.testing.assert_array_equal(coverage, valid)
    assert result["covered_pixels"] == int(valid.sum())
    x, y = [0, width - 1, width / 2], [0, height - 1, height / 2]
    np.testing.assert_allclose(
        reopened.pixel_to_world_values(x, y),
        target.pixel_to_world_values(x, y),
        atol=1e-9,
        rtol=0,
    )


def check_project(
    cli: Path,
    cwd: Path,
    source: Path,
    expected: NDArray[np.float32],
    target: WCS,
    *,
    projection: str = "TAN",
) -> None:
    project = source.with_suffix(".astromosaic")
    output = source.with_name(f"{source.stem} mosaic{source.suffix}")
    channels = expected.shape[-1] if expected.ndim == 3 else 1
    created = run_cli(
        cli,
        cwd,
        "project",
        "create",
        str(source),
        "-o",
        str(project),
        "--center",
        *map(str, CENTER),
        "--size",
        *map(str, SIZE),
        "--scale",
        str(SCALE),
        *(("--projection", projection) if projection != "TAN" else ()),
        "--json",
    )
    assert created["schema_version"] == 1 and created["status"] == "ok"
    assert project.is_file()
    saved = json.loads(project.read_text(encoding="utf-8"))
    assert saved["render"].get("projection", "TAN") == projection
    validated = run_cli(cli, cwd, "project", "validate", str(project), "-o", str(output), "--json")
    assert validated["schema_version"] == 1 and validated["status"] == "ok"
    assert (validated["width"], validated["height"], validated["channels"]) == (*SIZE, channels)
    assert not output.exists()
    exported = run_cli(cli, cwd, "project", "export", str(project), "-o", str(output), "--json")
    assert exported["schema_version"] == 1 and exported["status"] == "ok"
    assert exported["layer"] == "sky"
    check_raster(output, expected, target, exported)


def check_bands(
    cli: Path, cwd: Path, source: Path, expected: NDArray[np.float32], target: WCS
) -> None:
    second = cwd / "O III panel.fits"
    shifted = expected + np.float32(40)
    fits.writeto(second, shifted, fits.getheader(source))
    manifest = cwd / "Bands.astromosaic"
    created = run_cli(
        cli,
        cwd,
        "project",
        "create",
        str(source),
        str(second),
        "-o",
        str(manifest),
        "--panel-band",
        "2=O III",
        "--center",
        *map(str, CENTER),
        "--size",
        *map(str, SIZE),
        "--scale",
        str(SCALE),
        "--json",
    )
    assert created["panels"] == 2
    listed = run_cli(cli, cwd, "project", "bands", str(manifest), "--json")
    assert listed["bands"] == [{"band": "L", "panels": [1]}, {"band": "O III", "panels": [2]}]
    output = cwd / "O III sky.fits"
    selected = ("--band", "O III", "-o", str(output), "--json")
    validated = run_cli(cli, cwd, "project", "validate", str(manifest), *selected)
    assert validated["band"] == "O III" and validated["panels"] == 1
    result = run_cli(cli, cwd, "project", "export", str(manifest), *selected)
    check_raster(output, shifted, target, result)
    assert result["band"] == "O III" and fits.getheader(output)["FILTER"] == "O III"


def check_bundle(bundle: Path) -> None:
    with TemporaryDirectory(prefix="AstroMosaic package check ") as scratch:
        cwd = Path(scratch)
        runtime = cwd / "runtime"
        shutil.copytree(bundle, runtime)
        cli = runtime / "astromosaic-cli.exe"
        assert not list(runtime.rglob("Qt6Core.dll")), "The headless bundle contains Qt."
        assert run_cli(cli, cwd, "smoke", "--spawn")["spawned"] is True
        width, height = SIZE
        target = tan_output_wcs(CENTER, SIZE, SCALE, 0.0, Region(0, 0, width, height))
        header = target.to_header()
        header["FILTER"], header["BUNIT"] = "L", "MJy/sr"
        y, x = np.indices((height, width), dtype=np.int16)
        field = x - 3 * y
        path = cwd / "signed source.fits"
        fits.writeto(path, field, header)
        check_mosaic(cli, cwd, path, field.astype(np.float32), target)
        check_project(cli, cwd, path, field.astype(np.float32), target)
        check_bands(cli, cwd, path, field.astype(np.float32), target)

        zea_header = header.copy()
        zea_header["CTYPE1"], zea_header["CTYPE2"] = "RA---ZEA", "DEC--ZEA"
        zea = cwd / "equal area.fits"
        fits.writeto(zea, field, zea_header)
        check_project(cli, cwd, zea, field.astype(np.float32), WCS(zea_header), projection="ZEA")

        rgb = (np.stack((field, 2 * field, -field), axis=-1) / 4).astype(np.float32)
        rgb[12:17, 18:21] = np.nan
        fixtures: list[tuple[str, NDArray[np.float32] | NDArray[np.int16], int | None]] = [
            ("lzw", field.astype(np.int16), 2),
            ("deflate", rgb, 3),
            ("packbits", field.astype(np.int16), None),
        ]
        description = "AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False)
        for codec, samples, predictor in fixtures:
            path = cwd / f"{codec} source.tiff"
            tifffile.imwrite(
                path,
                samples,
                photometric="rgb" if samples.ndim == 3 else "minisblack",
                tile=(16, 16),
                compression=codec,
                predictor=predictor,
                description=description,
                metadata=None,
            )
            check_mosaic(cli, cwd, path, samples.astype(np.float32), target)
            if codec == "deflate":
                check_project(cli, cwd, path, rgb, target)
                xisf = check_mosaic(cli, cwd, path, rgb, target, output_suffix=".xisf")
                check_project(cli, cwd, xisf, rgb, target)
                report = run_cli(cli, cwd, "solve", str(xisf))
                assert report["stage"] == "existing-wcs"
        print(
            "Passed frozen worker spawning, FITS/TIFF/XISF exports, ZEA, and saved band selection."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Directory containing astromosaic-cli.exe.")
    check_bundle(parser.parse_args().bundle)
