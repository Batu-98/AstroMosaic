import json
from dataclasses import replace
from math import cos, radians, sin
from pathlib import Path
from threading import Event
from typing import Literal

import fitsio
import imagecodecs
import numpy as np
import pytest
import tifffile
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
from numpy.typing import NDArray

from astromosaic.cli import main
from astromosaic.core import Region
from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.io import open_panel
from astromosaic.io.tiff import open_tiff_panel
from astromosaic.pipeline.mosaic import RenderSpec, render_mosaic
from astromosaic.pipeline.refinement import RefinementSpec

SPEC = RenderSpec(CENTER, (SHAPE[1], SHAPE[0]), SCALE_ARCSEC, tile_size=3)


@pytest.mark.parametrize(
    ("dtype", "layout", "byteorder", "compression", "predictor", "tiled", "big"),
    [
        ("uint16", "mono", ">", "lzw", 2, False, False),
        ("int16", "mono", "<", None, None, True, False),
        ("float32", "separate", ">", "deflate", 3, True, False),
        ("uint16", "contig", "<", "packbits", None, False, False),
        ("float32", "separate", ">", None, None, False, False),
        ("int16", "contig", "<", None, None, True, True),
    ],
)
def test_tiff_windows_cross_segment_and_channel_boundaries(
    tmp_path: Path,
    dtype: str,
    layout: str,
    byteorder: Literal["<", ">"],
    compression: str | None,
    predictor: int | None,
    tiled: bool,
    big: bool,
) -> None:
    y, x = np.indices((35, 39))
    rgb = layout != "mono"
    base = (3 * x + 11 * y).astype(dtype)
    values = np.stack((base, base * 2, base * 3), axis=-1) if rgb else base
    if dtype == "uint16":
        values[17, 16] = 65535
    elif dtype == "int16":
        values[17, 16] = -32768
    else:
        values[17, 16] = (-2.5, 0.0, 1.25)
        values[19, 18, 2] = np.inf
    path = tmp_path / "science.tiff"
    tifffile.imwrite(
        path,
        np.moveaxis(values, -1, 0) if layout == "separate" else values,
        photometric="rgb" if rgb else "minisblack",
        planarconfig=layout if rgb else None,
        byteorder=byteorder,
        compression=compression,
        predictor=predictor,
        rowsperstrip=None if tiled else 8,
        tile=(16, 16) if tiled else None,
        bigtiff=big,
        metadata=None,
    )

    with open_tiff_panel(path) as panel:
        assert panel.descriptor.channel_layout == ("rgb" if rgb else "mono")
        assert (panel.descriptor.bscale, panel.descriptor.bzero) == (1, 0)
        tile = panel.read_tile(Region(16, 16, 23, 19), halo=3)
        assert tile.region == Region(13, 13, 26, 22)
        expected = values[tile.region.slices].astype(np.float32)
        valid = np.isfinite(expected).all(axis=-1) if rgb else np.isfinite(expected)
        expected[~valid] = np.nan
        assert tile.pixels.dtype == np.float32
        np.testing.assert_array_equal(tile.pixels, expected)
        np.testing.assert_array_equal(tile.valid, valid)


def _write_panels(directory: Path, rgb: bool) -> tuple[Path, Path]:
    a = directory / "Panel α.TIF"
    b = directory / "Panel B.tiff"
    left_y, left_x = np.indices((6, 8))
    left = (left_x + 1 + 2 * (left_y + 1) - 8).astype(np.int16)
    mask = np.ones_like(left, dtype=np.uint8)
    mask[2, 2] = mask[2, 6] = mask[4, 7] = 0
    right_y, right_x = np.indices((5, 7))
    right = (right_x + 6 + 2 * (right_y + 2) - 4.5).astype(np.float32)
    photo = "rgb" if rgb else "minisblack"
    first = _color(left) if rgb else left
    second = _color(right) if rgb else right
    if rgb:
        second[2, 0, 0] = second[3, 2, 2] = np.nan
        second[4, 5, 1] = np.inf
    else:
        second[2, 0] = second[3, 2] = np.nan
        second[4, 5] = np.inf
    with tifffile.TiffWriter(a) as tiff:
        tiff.write(
            first,
            photometric=photo,
            compression="lzw",
            rowsperstrip=2,
            description=_description(source_header(1, 1)),
            metadata=None,
            subifds=1,
        )
        tiff.write(mask, photometric="minisblack", metadata=None)
    tifffile.imwrite(
        b, second, photometric=photo, description=_description(source_header(6, 2)), metadata=None
    )
    return a, b


def _description(header: fits.Header) -> str:
    cards: str = header.tostring(sep="\n", padding=False)
    return "AstroMosaic TIFF 1\n" + cards


def _color[Sample: (np.int16, np.float32)](values: NDArray[Sample]) -> NDArray[Sample]:
    return np.stack((-2 * values, values, values + 64), axis=-1).astype(values.dtype, copy=False)


@pytest.mark.parametrize("rgb", [False, True])
def test_tiff_cli_round_trip_preserves_samples_coverage_and_wcs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], rgb: bool
) -> None:
    sources = _write_panels(tmp_path, rgb)
    original = [(path.read_bytes(), path.stat().st_mtime_ns) for path in sources]
    output = tmp_path / "two-panel mosaic.tiff"
    assert main(["inspect", str(sources[0])]) == 0
    descriptor = json.loads(capsys.readouterr().out)
    assert descriptor["channel_layout"] == ("rgb" if rgb else "mono")
    assert descriptor["wcs_provenance"] == "tiff-description"
    sidecar = tmp_path / "saved.wcs.json"
    assert main(["solve", str(sources[0]), "-o", str(sidecar)]) == 0
    assert json.loads(capsys.readouterr().out)["stage"] == "existing-wcs"
    assert (
        main(
            [
                "mosaic",
                *map(str, sources),
                "-o",
                str(output),
                "--wcs",
                f"1={sidecar}",
                "--center",
                *map(str, CENTER),
                "--scale",
                str(SCALE_ARCSEC),
                "--size",
                "15",
                "9",
                "--weights",
                "1",
                "3",
                "--tile-size",
                "3",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["covered_pixels"] == 65

    mono = reference_pixels()
    expected = _color(mono) if rgb else mono
    valid = np.isfinite(mono)
    science = imagecodecs.tiff_decode(output.read_bytes())
    assert science.dtype == np.float32
    np.testing.assert_array_equal(science, expected)
    with tifffile.TiffFile(output) as tiff:
        page = tiff.pages[0]
        assert len(tiff.pages) == 1
        subimages = page.pages
        assert subimages is not None
        coverage = subimages[0].asarray()
        assert coverage.dtype == np.uint8
        np.testing.assert_array_equal(coverage, valid)
    with open_panel(output) as source:
        tile = source.read_tile(Region(0, 0, *SPEC.size))
        np.testing.assert_array_equal(tile.pixels, expected)
        np.testing.assert_array_equal(tile.valid, valid)
        assert source.descriptor.unit == "MJy/sr"
        assert source.descriptor.filter_name == "L"
        wcs = WCS(source.header)
        for x, y in ((0, 0), (7, 4), (1, 6), (14, 8)):
            truth = tan_world(-0.002 * (x - 7), 0.002 * (y - 4))
            np.testing.assert_allclose(wcs.pixel_to_world_values(x, y), truth, rtol=0, atol=1e-9)
    assert [(path.read_bytes(), path.stat().st_mtime_ns) for path in sources] == original


def test_mixed_mono_fits_and_tiff_keep_the_reference_values(tmp_path: Path) -> None:
    fits_source, _ = write_reference_panels(tmp_path)
    _, tiff_source = _write_panels(tmp_path, rgb=False)
    output = tmp_path / "mixed.fits"
    result = render_mosaic([fits_source, tiff_source], output, SPEC, weights=WEIGHTS)
    assert result.covered_pixels == 65
    with fitsio.FITS(output) as reopened:
        np.testing.assert_array_equal(reopened[0].read(), reference_pixels())
        np.testing.assert_array_equal(reopened["COVERAGE"].read(), np.isfinite(reference_pixels()))


def test_rgb_bilinear_resampling_and_rotated_crop(tmp_path: Path) -> None:
    header = source_header(0, 0)
    header["CRPIX1"] = header["CRPIX2"] = 21.0
    sy, sx = np.indices((41, 41), dtype=np.float32) - 20
    field = np.stack(
        (-3 + 0.25 * sx + 1.75 * sy, 12 - 2.5 * sx + 0.25 * sy, 4 + sx - 0.5 * sy), axis=-1
    )
    source = tmp_path / "grid.tif"
    tifffile.imwrite(
        source, field, photometric="rgb", description=_description(header), metadata=None
    )
    crop = Region(2, 3, 8, 6)
    rotation = 23.0
    spec = RenderSpec(CENTER, (13, 11), 3.6, rotation, crop, tile_size=3)
    output = tmp_path / "cropped.tif"
    result = render_mosaic([source], output, spec)
    assert result.covered_pixels == crop.width * crop.height
    y, x = np.indices((crop.height, crop.width), dtype=np.float64)
    dx, dy = x + crop.x - 6, y + crop.y - 5
    angle = radians(rotation)
    u = (cos(angle) * dx - sin(angle) * dy) / 2
    v = (sin(angle) * dx + cos(angle) * dy) / 2
    truth = np.stack((-3 + 0.25 * u + 1.75 * v, 12 - 2.5 * u + 0.25 * v, 4 + u - 0.5 * v), axis=-1)
    with open_tiff_panel(output) as reopened:
        tile = reopened.read_tile(Region(0, 0, crop.width, crop.height))
        assert tile.valid.all()
        np.testing.assert_allclose(tile.pixels, truth, rtol=0, atol=2e-6)
        wcs = WCS(reopened.header)
        for ix, iy in ((0, 0), (4, 2), (7, 5)):
            expected = tan_world(-0.002 * u[iy, ix], 0.002 * v[iy, ix])
            np.testing.assert_allclose(
                wcs.pixel_to_world_values(ix, iy), expected, rtol=0, atol=1e-9
            )


def test_raw_single_strip_is_windowed_and_compressed_segments_are_budgeted(tmp_path: Path) -> None:
    pixels = np.arange(128 * 128, dtype=np.uint16).reshape(128, 128)
    raw = tmp_path / "raw.tif"
    compressed = tmp_path / "compressed.tif"
    for path, codec in ((raw, None), (compressed, "lzw")):
        tifffile.imwrite(
            path,
            pixels,
            compression=codec,
            rowsperstrip=128,
            description=_description(source_header(0, 0)),
            metadata=None,
        )
    with open_tiff_panel(raw, max_tile_bytes=128) as source:
        assert source.read_tile(Region(126, 127, 1, 1)).pixels.item() == pixels[127, 126]
    with open_tiff_panel(compressed, max_tile_bytes=128) as source:
        with pytest.raises(ValueError, match="codec buffers"):
            source.read_tile(Region(126, 127, 1, 1))

    output = tmp_path / "too-small.tif"
    with pytest.raises(ValueError, match="working byte budget"):
        render_mosaic([compressed], output, replace(SPEC, max_working_bytes=128 * 1024))
    assert not output.exists()
    assert not list(tmp_path.glob("*.part"))


def test_tiff_cancel_releases_inputs_and_allows_retry(tmp_path: Path) -> None:
    first, second = _write_panels(tmp_path, rgb=True)
    output = tmp_path / "cancelled.tiff"
    cancelled = Event()
    original = first.read_bytes()

    def progress(done: int, total: int) -> None:
        assert (done, total) == (9, 135)
        assert not output.exists()
        cancelled.set()

    with pytest.raises(MosaicCancelled):
        render_mosaic(
            [first, second],
            output,
            SPEC,
            context=JobContext(is_cancelled=cancelled.is_set, on_progress=progress),
        )
    assert not output.exists()
    assert not list(tmp_path.glob("*.part"))
    renamed = first.rename(tmp_path / "Gök alanı.tif")
    assert renamed.read_bytes() == original
    assert render_mosaic([renamed, second], output, SPEC).covered_pixels == 65


def test_tiff_rejects_incompatible_output_and_invalid_binary_coverage(tmp_path: Path) -> None:
    sources = _write_panels(tmp_path, rgb=True)
    output = tmp_path / "output.tiff"
    with pytest.raises(ValueError, match="RGB mosaics require TIFF"):
        render_mosaic(sources, output.with_suffix(".fits"), SPEC)
    with pytest.raises(ValueError, match="refinement currently requires mono"):
        render_mosaic(sources, output, SPEC, refinement=RefinementSpec())
    with pytest.raises(ValueError, match="output byte limit"):
        render_mosaic(sources, output, replace(SPEC, max_output_bytes=1000))
    assert not output.exists()

    broken = tmp_path / "invalid-coverage.tif"
    with tifffile.TiffWriter(broken) as tiff:
        pixels = np.ones((3, 4), dtype=np.uint16)
        tiff.write(pixels, description=_description(source_header(0, 0)), metadata=None, subifds=1)
        tiff.write(np.full((3, 4), 255, dtype=np.uint8), metadata=None)
    with open_tiff_panel(broken) as source:
        with pytest.raises(ValueError, match="binary values"):
            source.read_tile(Region(0, 0, 1, 1))


def test_tiff_rejects_transformed_orientation_and_truncated_raster(tmp_path: Path) -> None:
    path = tmp_path / "orientation.tif"
    values = np.ones((7, 8), dtype=np.uint16)
    tifffile.imwrite(path, values, metadata=None, extratags=[(274, "H", 1, 8, False)])
    with pytest.raises(ValueError, match="top-left TIFF orientation"), open_tiff_panel(path):
        pytest.fail("Unsupported TIFF orientation was accepted.")
    truncated = tmp_path / "truncated.tiff"
    tifffile.imwrite(truncated, values, metadata=None)
    with truncated.open("r+b") as stream:
        stream.truncate(truncated.stat().st_size - 1)
    with pytest.raises(ValueError, match="missing or truncated"), open_tiff_panel(truncated):
        pytest.fail("Truncated TIFF pixels were accepted.")
