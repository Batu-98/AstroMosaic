import json
import subprocess
import sys
from dataclasses import replace
from math import cos, pi, radians, sin
from pathlib import Path

import fitsio
import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS
from mosaic_reference import (
    CENTER,
    SCALE_ARCSEC,
    SHAPE,
    WEIGHTS,
    reference_pixels,
    source_header,
    tan_world,
    write_reference_panels,
)
from reproject import reproject_interp

from astromosaic.core import Region, Tile
from astromosaic.io.fits import FitsTileSource, open_fits_panel
from astromosaic.pipeline.mosaic import RenderSpec, render_mosaic


def test_two_panel_cli_output_reopens_with_cfitsio(tmp_path: Path) -> None:
    inputs = write_reference_panels(tmp_path)
    original = [(path.read_bytes(), path.stat().st_mtime_ns) for path in inputs]
    destination = tmp_path / "output mosaic.fits"
    script = """
import sys

class BlockDesktop:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'PySide6', 'PyQt6', 'PySide2', 'PyQt5', 'fitsio'}:
            raise AssertionError(f'Unexpected import: {fullname}')
        if fullname.startswith('astromosaic.ui'):
            raise AssertionError(f'Unexpected UI import: {fullname}')

sys.meta_path.insert(0, BlockDesktop())
from astromosaic.cli import main
raise SystemExit(main(sys.argv[1:]))
"""
    job = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            "mosaic",
            *map(str, inputs),
            "-o",
            str(destination),
            "--center",
            *map(str, CENTER),
            "--size",
            "15",
            "9",
            "--scale",
            str(SCALE_ARCSEC),
            "--weights",
            *map(str, WEIGHTS),
            "--tile-size",
            "3",
            "--progress",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    summary = json.loads(job.stdout)
    assert (summary["width"], summary["height"], summary["covered_pixels"]) == (15, 9, 65)
    assert summary["backend"] == "cpu"
    assert summary["rejected_coordinates"] == 0
    assert "135/135 pixels (100%)" in job.stderr

    expected = reference_pixels()
    with fitsio.FITS(destination) as output:
        assert len(output) == 2
        science, coverage = output[0].read(), output["COVERAGE"].read()
        assert science.dtype == np.dtype(np.float32)
        assert coverage.dtype == np.dtype(np.uint8)
        np.testing.assert_array_equal(science, expected)
        np.testing.assert_array_equal(coverage, np.isfinite(expected))
        keywords = output[0].read_header()
        assert (keywords["BUNIT"], keywords["FILTER"]) == ("MJy/sr", "L")
        assert all(key not in keywords for key in ("BSCALE", "BZERO", "BLANK"))
        history = [record["value"] for record in keywords.records() if record["name"] == "HISTORY"]
        assert any("AstroMosaic" in line for line in history)

    with open_fits_panel(destination) as panel:
        assert panel.descriptor.mask_provenance == ("finite-raw-pixels", "coverage-extension")
        tile = panel.read_tile(Region(0, 0, SHAPE[1], SHAPE[0]))
        np.testing.assert_array_equal(tile.pixels, expected)
        np.testing.assert_array_equal(tile.valid, coverage)
        wcs = WCS(panel.header)
        for x, y in ((0, 0), (7, 4), (1, 6), (14, 8)):
            truth = tan_world(-0.002 * (x - 7), 0.002 * (y - 4))
            np.testing.assert_allclose(wcs.pixel_to_world_values(x, y), truth, rtol=0, atol=1e-9)
    assert [(path.read_bytes(), path.stat().st_mtime_ns) for path in inputs] == original


def test_source_window_budget_splits_an_output_tile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "wide-source.fits"
    header = source_header(0, 0)
    header["CRPIX1"] = header["CRPIX2"] = 33.0
    y, x = np.indices((65, 65), dtype=np.float32)
    fits.writeto(source, x + 2 * y, header=header)
    spec = RenderSpec(CENTER, (5, 3), 8 * SCALE_ARCSEC)
    untiled = tmp_path / "untiled.fits"
    assert render_mosaic([source], untiled, spec).tiles == 1

    regions = []
    original_read = FitsTileSource.read_tile

    def record_read(panel: FitsTileSource, region: Region, *, halo: int = 0) -> Tile:
        regions.append(region)
        return original_read(panel, region, halo=halo)

    monkeypatch.setattr(FitsTileSource, "read_tile", record_read)
    destination = tmp_path / "split.fits"
    budget = 96 * 1024
    summary = render_mosaic([source], destination, replace(spec, max_working_bytes=budget))
    assert summary.tiles > 1
    assert summary.peak_reserved_bytes <= budget
    assert all(region.width < 33 or region.height < 17 for region in regions)

    output_y, output_x = np.indices((3, 5))
    expected = (16 + 8 * output_x) + 2 * (24 + 8 * output_y)
    with fitsio.FITS(destination) as tiled, fitsio.FITS(untiled) as reference:
        np.testing.assert_array_equal(tiled[0].read(), expected)
        np.testing.assert_array_equal(tiled[0].read(), reference[0].read())
        np.testing.assert_array_equal(tiled["COVERAGE"].read(), reference["COVERAGE"].read())


def test_rotated_cropped_tan_export_from_sip_inputs(tmp_path: Path) -> None:
    size = (13, 11)
    crop = Region(2, 3, 8, 6)
    rotation = 23.0
    coefficient = 0.003
    header = source_header(0, 0)
    header.update(
        {
            "CRPIX1": 21.0,
            "CRPIX2": 21.0,
            "CTYPE1": "RA---TAN-SIP",
            "CTYPE2": "DEC--TAN-SIP",
            "A_ORDER": 2,
            "B_ORDER": 2,
            "A_2_0": coefficient,
        }
    )
    y, x = np.indices((41, 41), dtype=np.float32) - 20.0
    field = -3 + 0.25 * x + 1.75 * y
    source = tmp_path / "distorted.fits"
    fits.writeto(source, field, header=header)
    destination = tmp_path / "cropped.fits"
    summary = render_mosaic(
        [source], destination, RenderSpec(CENTER, size, 3.6, rotation, crop, tile_size=3)
    )
    assert summary.rejected_coordinates == 0

    y, x = np.indices((crop.height, crop.width), dtype=np.float64)
    dx, dy = x + crop.x - 6, y + crop.y - 5
    angle = radians(rotation)
    plane_x = (cos(angle) * dx - sin(angle) * dy) / 2
    plane_y = (sin(angle) * dx + cos(angle) * dy) / 2
    # Invert p + A_2_0 * p**2 analytically and evaluate the linear source field.
    source_x = 2 * plane_x / (1 + np.sqrt(1 + 4 * coefficient * plane_x))
    expected = -3 + 0.25 * source_x + 1.75 * plane_y
    with fitsio.FITS(destination) as output:
        values = output[0].read()
        np.testing.assert_allclose(values, expected, rtol=0, atol=2e-6)
        np.testing.assert_array_equal(output["COVERAGE"].read(), 1)
        exported = output[0].read_header()
        assert (exported["CTYPE1"], exported["CTYPE2"]) == ("RA---TAN", "DEC--TAN")
        assert all(key not in exported for key in ("A_2_0", "A_ORDER", "B_ORDER"))

    target = WCS(fits.getheader(destination))
    for column, row in ((0, 0), (4, 2), (7, 5)):
        truth = tan_world(-0.002 * plane_x[row, column], 0.002 * plane_y[row, column])
        np.testing.assert_allclose(
            target.pixel_to_world_values(column, row), truth, rtol=0, atol=1e-9
        )
    # The first-preference reference uses the complete small source for this comparison.
    baseline, _ = reproject_interp((field, WCS(header)), target, expected.shape)
    np.testing.assert_allclose(values, baseline, rtol=0, atol=2e-6)


def test_masked_bilinear_support_and_true_zero(tmp_path: Path) -> None:
    source = tmp_path / "masked.fits"
    header = source_header(0, 0)
    header["CRPIX1"] = header["CRPIX2"] = 2.0
    pixels = np.tile(np.array([-2, 0, 42], dtype=np.float32), (3, 1))
    valid = np.tile(np.array([1, 1, 0], dtype=np.uint8), (3, 1))
    fits.HDUList([fits.PrimaryHDU(pixels, header), fits.ImageHDU(valid, name="COVERAGE")]).writeto(
        source
    )
    destination = tmp_path / "half-scale.fits"
    render_mosaic([source], destination, RenderSpec(CENTER, (7, 3), 3.6, tile_size=2))
    expected = np.tile([-2, -2, -1, 0, np.nan, np.nan, np.nan], (3, 1))
    with fitsio.FITS(destination) as output:
        np.testing.assert_array_equal(output[0].read(), expected)
        np.testing.assert_array_equal(output["COVERAGE"].read(), np.isfinite(expected))


@pytest.mark.parametrize("uniform", [True, False])
def test_surface_brightness_at_half_pixel_scale(tmp_path: Path, uniform: bool) -> None:
    header = source_header(0, 0)
    header["CRPIX1"] = header["CRPIX2"] = 17.0
    header["CDELT1"], header["CDELT2"] = -2 / 3600, 2 / 3600
    y, x = np.indices((33, 33), dtype=np.float32) - 16
    values = np.full_like(x, 7.0) if uniform else 5 * np.exp(-(x**2 + y**2) / (2 * 3**2))
    path = tmp_path / "surface.fits"
    fits.writeto(path, values, header=header)
    destination = tmp_path / "reprojected.fits"
    render_mosaic([path], destination, RenderSpec(CENTER, (65, 65), 1.0, tile_size=11))
    with fitsio.FITS(destination) as output:
        np.testing.assert_array_equal(output["COVERAGE"].read(), 1)
        result = output[0].read()
    if uniform:
        np.testing.assert_array_equal(result, 7.0)
    else:
        step = radians(1 / 3600)
        y, x = (np.indices((65, 65), dtype=np.float64) - 32) * step
        solid_angle = step**2 / (1 + x**2 + y**2) ** 1.5
        flux = np.sum(result * solid_angle)
        np.testing.assert_allclose(flux, 5 * 2 * pi * (6 * step) ** 2, rtol=0.01, atol=0)


def test_swapped_world_axes_and_projection_singularity(tmp_path: Path) -> None:
    values = np.arange(9 * 15, dtype=np.float32).reshape(SHAPE)
    header = source_header(0, 0)
    header.update(
        {
            "CTYPE1": "DEC--TAN",
            "CTYPE2": "RA---TAN",
            "CRVAL1": CENTER[1],
            "CRVAL2": CENTER[0],
            "CD1_2": 0.002,
            "CD2_1": -0.002,
        }
    )
    del header["CDELT1"], header["CDELT2"]
    swapped = tmp_path / "swapped.fits"
    fits.writeto(swapped, values, header=header)

    opposite_header = source_header(0, 0)
    opposite_header["CRVAL1"] = (CENTER[0] + 180) % 360
    opposite = tmp_path / "opposite.fits"
    fits.writeto(opposite, -values, header=opposite_header)
    destination = tmp_path / "one-visible.fits"
    result = render_mosaic(
        [swapped, opposite], destination, RenderSpec(CENTER, SHAPE[::-1], SCALE_ARCSEC)
    )
    assert result.rejected_coordinates == values.size
    with fitsio.FITS(destination) as output:
        np.testing.assert_array_equal(output[0].read(), values)
        np.testing.assert_array_equal(output["COVERAGE"].read(), 1)


def test_uninvertible_sip_samples_are_uncovered_across_tiles(tmp_path: Path) -> None:
    header = source_header(0, 0)
    header.update(
        {
            "CRPIX1": 13.0,
            "CRPIX2": 13.0,
            "CTYPE1": "RA---TAN-SIP",
            "CTYPE2": "DEC--TAN-SIP",
            "A_ORDER": 2,
            "B_ORDER": 2,
            "A_2_0": 0.05,
        }
    )
    source = tmp_path / "folded-geometry.fits"
    fits.writeto(source, np.full((25, 25), 7.0, dtype=np.float32), header=header)
    spec = RenderSpec(CENTER, (17, 3), SCALE_ARCSEC)
    tile, whole = tmp_path / "tile.fits", tmp_path / "whole.fits"
    result = render_mosaic([source], whole, spec)
    assert result.rejected_coordinates >= 9
    render_mosaic([source], tile, replace(spec, tile_size=3))
    with fitsio.FITS(tile) as tiled, fitsio.FITS(whole) as untiled:
        mask = tiled["COVERAGE"].read()
        pixels = tiled[0].read()
        # p + 0.05p**2 cannot reach the first three columns, where dx is below -5.
        np.testing.assert_array_equal(mask[:, :3], 0)
        assert mask[1, 8] == 1
        np.testing.assert_array_equal(pixels[mask == 1], 7.0)
        np.testing.assert_array_equal(mask, untiled["COVERAGE"].read())
        np.testing.assert_array_equal(pixels, untiled[0].read())
