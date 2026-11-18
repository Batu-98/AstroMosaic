from dataclasses import replace
from math import cos, degrees, radians, sin
from pathlib import Path

import fitsio
import numpy as np
import pytest
import tifffile
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from numpy.typing import NDArray
from xisf_reference import read_xisf_attachments

from astromosaic.core import Region
from astromosaic.geometry import TileSky, read_panel_geometry
from astromosaic.io import open_panel
from astromosaic.pipeline.mosaic import RenderSpec, preview_mosaic, render_mosaic

_WIDE = RenderSpec((359.4, 23.0), (63, 39), 2880.0, 21.0, Region(5, 9, 51, 27), projection="ZEA")


def _basis(center: tuple[float, float]) -> NDArray[np.float64]:
    ra, dec = map(radians, center)
    return np.array(
        [
            (cos(ra) * cos(dec), sin(ra) * cos(dec), sin(dec)),
            (-sin(ra), cos(ra), 0.0),
            (-cos(ra) * sin(dec), -sin(ra) * sin(dec), cos(dec)),
        ]
    )


def _lambert_directions(spec: RenderSpec) -> NDArray[np.float64]:
    crop = spec.output_region()
    y, x = np.indices((crop.height, crop.width), dtype=np.float64)
    x += crop.x - (spec.size[0] - 1) / 2
    y += crop.y - (spec.size[1] - 1) / 2
    rotation = radians(spec.rotation_deg)
    step = radians(spec.scale_arcsec / 3600)
    east = step * (-cos(rotation) * x + sin(rotation) * y)
    north = step * (sin(rotation) * x + cos(rotation) * y)
    radius_squared = east**2 + north**2
    factor = np.sqrt(1 - radius_squared / 4)
    return np.stack((1 - radius_squared / 2, east * factor, north * factor), axis=-1) @ _basis(
        spec.center
    )


def _fixture_header(
    center: tuple[float, float], size: tuple[int, int], step: float, projection: str
) -> fits.Header:
    # Build the reference directly from FITS cards.
    return fits.Header(
        [
            ("CTYPE1", f"RA---{projection}"),
            ("CTYPE2", f"DEC--{projection}"),
            ("RADESYS", "ICRS"),
            ("CRPIX1", (size[0] + 1) / 2),
            ("CRPIX2", (size[1] + 1) / 2),
            ("CRVAL1", center[0]),
            ("CRVAL2", center[1]),
            ("CDELT1", -step),
            ("CDELT2", step),
            ("BUNIT", "MJy/sr"),
            ("FILTER", "L"),
        ]
    )


def _tan_support(
    directions: NDArray[np.float64],
    center: tuple[float, float],
    step: float,
    valid: NDArray[np.bool_],
) -> NDArray[np.bool_]:
    normal, east, north = np.moveaxis(directions @ _basis(center).T, -1, 0)
    height, width = valid.shape
    x = (width - 1) / 2 - np.degrees(east / normal) / step
    y = (height - 1) / 2 + np.degrees(north / normal) / step
    contained = (normal > 0) & (x >= -0.5) & (x < width - 0.5) & (y >= -0.5) & (y < height - 0.5)
    sx, sy = np.clip(x, 0, width - 1), np.clip(y, 0, height - 1)
    valid_neighbors = np.logical_and.reduce(
        [
            valid[rows(sy).astype(int), columns(sx).astype(int)]
            for rows in (np.floor, np.ceil)
            for columns in (np.floor, np.ceil)
        ]
    )
    return np.asarray(contained & valid_neighbors, dtype=np.bool_)


def _check_wcs(wcs: WCS, directions: NDArray[np.float64]) -> None:
    ra = np.degrees(np.arctan2(directions[..., 1], directions[..., 0])) % 360
    dec = np.degrees(np.arcsin(directions[..., 2]))
    y, x = np.indices(ra.shape, dtype=np.float64)
    observed_ra, observed_dec = wcs.all_pix2world(x, y, 0)
    assert observed_ra.min() < 2 and observed_ra.max() > 358
    np.testing.assert_allclose((observed_ra - ra + 180) % 360 - 180, 0, rtol=0, atol=1e-9)
    np.testing.assert_allclose(observed_dec, dec, rtol=0, atol=1e-9)
    np.testing.assert_allclose(wcs.all_world2pix(ra, dec, 0), (x, y), rtol=0, atol=1e-7)


def test_zea_wide_crop_preserves_same_samples_across_preview_and_formats(tmp_path: Path) -> None:
    size = (43, 35)
    step = 1.25
    directions = _lambert_directions(_WIDE)
    paths = []
    weights = (1.0, 2.0)
    numerator = np.zeros(directions.shape[:2])
    denominator = np.zeros_like(numerator)
    for index, (center, brightness, weight) in enumerate(
        zip(((351.0, 12.0), (9.0, 28.0)), (-3.0, 1.5), weights, strict=True)
    ):
        image = np.full(size[::-1], brightness, dtype=np.float32)
        image[8 + index : 13 + index, 12:17] = np.nan
        path = tmp_path / f"tan-{index}.fits"
        fits.writeto(path, image, _fixture_header(center, size, step, "TAN"))
        paths.append(path)
        covered = _tan_support(directions, center, step, np.isfinite(image))
        numerator[covered] += brightness * weight
        denominator[covered] += weight

    coverage = denominator > 0
    expected = np.full(coverage.shape, np.nan, dtype=np.float32)
    expected[coverage] = numerator[coverage] / denominator[coverage]
    assert {-3.0, 0.0, 1.5} == set(np.unique(expected[coverage]))
    assert not coverage.all()
    frame = preview_mosaic(paths, _WIDE, weights=weights)
    np.testing.assert_array_equal(frame.tile.valid, coverage)
    np.testing.assert_allclose(frame.tile.pixels, expected, rtol=0, atol=1e-7)
    assert frame.output_wcs is not None
    _check_wcs(frame.output_wcs, directions)

    for suffix in (".fits", ".tiff", ".xisf"):
        output = tmp_path / f"zea{suffix}"
        report = render_mosaic(paths, output, _WIDE, weights=weights)
        assert report.covered_pixels == int(coverage.sum())
        if suffix == ".fits":
            with fitsio.FITS(output) as hdus:
                pixels, mask = hdus[0].read(), hdus["COVERAGE"].read()
        elif suffix == ".tiff":
            with tifffile.TiffFile(output) as tiff:
                page = tiff.pages[0]
                assert isinstance(page, tifffile.TiffPage) and page.pages is not None
                pixels, mask = page.asarray(), page.pages[0].asarray()
        else:
            (pixels, mask), _ = read_xisf_attachments(output)
        assert (pixels.dtype.kind, pixels.dtype.itemsize) == ("f", 4)
        np.testing.assert_array_equal(pixels, frame.tile.pixels)
        np.testing.assert_array_equal(mask, coverage)
        with open_panel(output) as panel:
            assert panel.header["CTYPE1"] == "RA---ZEA" and panel.header["CTYPE2"] == "DEC--ZEA"
            assert panel.descriptor.unit == "MJy/sr" and panel.descriptor.filter_name == "L"
            _check_wcs(WCS(panel.header), directions)

    limited = replace(_WIDE, max_working_bytes=256 * 1024)
    tight = tmp_path / "limited.fits"
    report = render_mosaic(paths, tight, limited, weights=weights)
    assert report.tiles > 1 and report.peak_reserved_bytes <= limited.max_working_bytes
    with fitsio.FITS(tight) as reopened:
        np.testing.assert_array_equal(reopened[0].read(), frame.tile.pixels)
        np.testing.assert_array_equal(reopened["COVERAGE"].read(), coverage)


def test_zea_antipodal_rim_is_uncovered_and_valid_crops_reopen(tmp_path: Path) -> None:
    spec = RenderSpec((359.4, 90.0), (13, 11), degrees(0.5) * 3600, tile_size=4, projection="ZEA")
    y, x = np.indices((11, 13), dtype=np.float32)
    field = x - 2 * y
    valid = (x - 6) ** 2 + (y - 5) ** 2 < 16
    expected = np.where(valid, field, np.nan)
    source = tmp_path / "polar.fits"
    fits.writeto(source, field, _fixture_header(spec.center, spec.size, degrees(0.5), "ZEA"))
    with open_panel(source) as panel:
        geometry = read_panel_geometry(panel.header, *spec.size)
        # The serialized FITS WCS can put these rim points barely inside the disk.
        sky = geometry.forward(np.array([2.0, 3.0, 6.0, 10.0]), np.array([5.0] * 4))
        np.testing.assert_array_equal(np.isfinite(sky.dec.deg), [False, True, True, False])
        antipode = SkyCoord([179.4], [-90.0], unit="deg", frame="icrs")
        assert np.isnan(geometry.inverse(antipode)).all()
        near_rim = TileSky.from_output(geometry, Region(9, 5, 3, 1))
        _, _, usable = near_rim.in_panel(geometry, shift=(1.0, 0.0))
        np.testing.assert_array_equal(usable, [True, False, False])

    frame = preview_mosaic([source], spec)
    np.testing.assert_array_equal(frame.tile.pixels, expected)
    np.testing.assert_array_equal(frame.tile.valid, valid)
    assert np.any(frame.tile.valid & (frame.tile.pixels == 0.0))
    cropped = replace(spec, crop=Region(8, 0, 5, 11))
    output = tmp_path / "part of disk.fits"
    result = render_mosaic([source], output, cropped)
    assert result.covered_pixels == int(valid[:, 8:].sum())
    with fitsio.FITS(output) as reopened:
        np.testing.assert_array_equal(reopened[0].read(), expected[:, 8:])
        np.testing.assert_array_equal(reopened["COVERAGE"].read(), valid[:, 8:])
    roundtrip = preview_mosaic([output], cropped)
    np.testing.assert_array_equal(roundtrip.tile.pixels, expected[:, 8:])
    np.testing.assert_array_equal(roundtrip.tile.valid, valid[:, 8:])

    outside = tmp_path / "outside.fits"
    with pytest.raises(ValueError, match="no valid input coverage"):
        render_mosaic([source], outside, replace(spec, crop=Region(11, 0, 2, 11)))
    assert not outside.exists() and not list(tmp_path.glob("*.part"))
