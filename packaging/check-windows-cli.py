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
    cli: Path, cwd: Path, source: Path, expected: NDArray[np.float32], target: WCS
) -> None:
    destination = cwd / f"{source.stem}-export{source.suffix}"
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
    assert result["backend"] == "cpu"
    if destination.suffix == ".fits":
        with fitsio.FITS(destination) as hdus:
            pixels = hdus[0].read()
            coverage = hdus["COVERAGE"].read()
        reopened = WCS(fits.getheader(destination))
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
        print(
            "Passed frozen worker spawning, FITS, and LZW, Deflate RGB, and PackBits TIFF exports."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Directory containing astromosaic-cli.exe.")
    check_bundle(parser.parse_args().bundle)
