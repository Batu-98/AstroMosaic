from pathlib import Path
from struct import pack

import fitsio
import numpy as np
import pytest
import tifffile
from astropy.io import fits
from astropy.wcs import WCS
from mosaic_reference import CENTER, SCALE_ARCSEC, WEIGHTS, write_reference_panels

from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.display import normalize_preview
from astromosaic.geometry import tan_output_wcs
from astromosaic.io import open_panel
from astromosaic.pipeline.mosaic import PreviewFrame, RenderSpec, preview_mosaic, render_mosaic


def test_fits_preview_uses_rotated_cropped_export_grid(tmp_path: Path) -> None:
    paths = write_reference_panels(tmp_path)
    crop = Region(1, 2, 12, 6)
    spec = RenderSpec(CENTER, (15, 9), SCALE_ARCSEC, 19.0, crop, tile_size=3)
    preview = preview_mosaic(paths, spec, weights=WEIGHTS)
    destination = tmp_path / "crop.fits"
    render_mosaic(paths, destination, spec, weights=WEIGHTS)

    assert preview.output_size == (crop.width, crop.height)
    assert preview.tile.valid.any() and not preview.tile.valid.all()
    assert not preview.tile.pixels.flags.writeable
    assert not preview.tile.valid.flags.writeable
    with fitsio.FITS(destination) as output:
        np.testing.assert_array_equal(preview.tile.pixels, output[0].read())
        np.testing.assert_array_equal(preview.tile.valid, output["COVERAGE"].read())
    with open_panel(destination) as output_panel:
        reopened = WCS(output_panel.header)
    y, x = np.indices((crop.height, crop.width))
    assert preview.output_wcs is not None
    np.testing.assert_allclose(
        preview.output_wcs.pixel_to_world_values(x, y),
        reopened.pixel_to_world_values(x, y),
        atol=1e-9,
        rtol=0,
    )


def test_rgb_proxy_and_preview_sample_the_same_export_rectangle(tmp_path: Path) -> None:
    source = tmp_path / "color.tiff"
    width, height = 601, 97
    y, x = np.indices((height, width), dtype=np.float32)
    signal = x * 0.5 - y * 4
    samples = np.stack((signal, np.zeros_like(signal), signal * -2), axis=-1)
    samples[30:43, 200:300, 1] = np.nan
    header = tan_output_wcs(
        CENTER, (width, height), SCALE_ARCSEC, 4.0, Region(0, 0, width, height)
    ).to_header()
    header["FILTER"], header["BUNIT"] = "L", "MJy/sr"
    tifffile.imwrite(
        source,
        samples,
        photometric="rgb",
        metadata=None,
        description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False),
    )
    spec = RenderSpec(CENTER, (1544, 160), SCALE_ARCSEC, 19.0, Region(3, 2, 1536, 144))
    proxy: list[PreviewFrame] = []
    progress: list[tuple[int, int]] = []
    preview = preview_mosaic(
        [source],
        spec,
        on_proxy=proxy.append,
        context=JobContext(on_progress=lambda done, total: progress.append((done, total))),
    )
    assert len(proxy) == 1
    assert proxy[0].tile.valid.shape == (15, 160)
    assert proxy[0].output_size == preview.output_size == (1536, 144)
    assert preview.tile.valid.shape == (48, 512)
    assert preview.peak_reserved_bytes <= spec.max_working_bytes
    total = 160 * 15 + 512 * 48
    assert progress[-1] == (total, total)
    assert all(a[0] < b[0] for a, b in zip(progress, progress[1:], strict=False))

    destination = tmp_path / "export.tiff"
    render_mosaic([source], destination, spec)
    with tifffile.TiffFile(destination) as reopened:
        page = reopened.pages[0]
        # The center of each 3x3 preview cell coincides with an exact export pixel.
        np.testing.assert_array_equal(preview.tile.pixels, page.asarray()[1::3, 1::3])
        assert page.pages is not None
        np.testing.assert_array_equal(preview.tile.valid, page.pages[0].asarray()[1::3, 1::3])
    valid = preview.tile.valid
    assert valid.any() and not valid.all()
    values = preview.tile.pixels[valid].copy()
    assert values.min() < 0 < 1 < values.max()
    np.testing.assert_array_equal(values[:, 1], 0)
    display = normalize_preview(preview)
    assert display.has_coverage and not display.rgba.flags.writeable
    np.testing.assert_array_equal(display.rgba[..., 3], valid)
    np.testing.assert_array_equal(preview.tile.pixels[valid], values)


def _write_sky_panel(path: Path, spec: RenderSpec) -> None:
    header = spec.output_wcs().to_header()
    header["BUNIT"] = "MJy/sr"
    fits.writeto(path, np.ones(spec.size[::-1], dtype=np.float32), header)


def test_auto_frame_encloses_both_panels_across_the_ra_wrap(tmp_path: Path) -> None:
    paths = [tmp_path / "west.fits", tmp_path / "east.fits"]
    for path, ra in zip(paths, (359.8, 0.2), strict=True):
        _write_sky_panel(path, RenderSpec((ra, 55), (80, 64), 30))
    saved = RenderSpec((180, -14), (40, 40), 2)

    manual = preview_mosaic(paths, saved)
    assert not manual.tile.valid.any() and manual.fitted_grid is None
    preview = preview_mosaic(paths, saved, auto_frame=True)
    fitted = preview.fitted_grid
    assert fitted is not None and fitted.projection == "TAN"
    assert min(fitted.center[0], 360 - fitted.center[0]) < 1e-8
    assert fitted.scale_arcsec == pytest.approx(30)
    left, right = (preview_mosaic([path], fitted).tile.valid for path in paths)
    assert (left & right).any() and (left & ~right).any() and (right & ~left).any()
    np.testing.assert_array_equal(preview.tile.valid, left | right)
    assert preview.peak_reserved_bytes <= fitted.max_working_bytes

    destination = tmp_path / "adopted.fits"
    render_mosaic(paths, destination, fitted)
    with fitsio.FITS(destination) as output:
        np.testing.assert_array_equal(preview.tile.pixels, output[0].read())
        np.testing.assert_array_equal(preview.tile.valid, output["COVERAGE"].read())


def test_auto_frame_switches_to_zea_for_opposite_footprints(tmp_path: Path) -> None:
    paths = [tmp_path / "near.fits", tmp_path / "far.fits"]
    for path, center in zip(paths, ((0, 0), (180, 0)), strict=True):
        _write_sky_panel(path, RenderSpec(center, (48, 40), 3600))
    preview = preview_mosaic(paths, RenderSpec((0, 0), (32, 32), 2), auto_frame=True)
    fitted = preview.fitted_grid
    assert fitted is not None and fitted.projection == "ZEA"
    near, far = (preview_mosaic([path], fitted).tile.valid for path in paths)
    assert near.any() and far.any() and not (near & far).any()
    np.testing.assert_array_equal(preview.tile.valid, near | far)


def _matrix_icc(*, srgb: bool) -> bytes:
    def fixed(values: tuple[float, ...]) -> bytes:
        return pack(f">{len(values)}i", *(round(value * 65536) for value in values))

    colorants = (
        (0.43607, 0.22249, 0.01392),
        (0.38506, 0.71689, 0.09708),
        (0.14308, 0.06062, 0.71410),
    )
    curve = (
        b"para"
        + bytes(4)
        + pack(">HH", 4, 0)
        + fixed((2.4 if srgb else 1.8, 1 / 1.055, 0.055 / 1.055, 1 / 12.92, 0.04045, 0, 0))
    )
    header = bytearray(128)
    header[8] = 4
    header[12:24] = b"mntrRGB XYZ "
    header[36:40] = b"acsp"
    tags = bytearray(pack(">I", 6))
    offset = 128 + 4 + 6 * 12
    payload = bytearray()
    for channel, xyz in zip((b"r", b"g", b"b"), colorants, strict=True):
        for tag, data in ((b"XYZ", b"XYZ " + bytes(4) + fixed(xyz)), (b"TRC", curve)):
            tags.extend(pack(">4sII", channel + tag, offset + len(payload), len(data)))
            payload.extend(data)
    header[:4] = pack(">I", offset + len(payload))
    return bytes(header + tags + payload)


def test_srgb_preview_linearizes_before_sampling_and_rejects_scientific_export(
    tmp_path: Path,
) -> None:
    spec = RenderSpec(CENTER, (12, 10), SCALE_ARCSEC)
    header = spec.output_wcs().to_header()
    header["CRPIX1"] += 0.5
    samples = np.full((10, 12, 3), (0, 32768, 2000), dtype=np.uint16)
    samples[:, 1::2, 0] = 65535
    tagged = tmp_path / "display.tiff"
    unsupported = tmp_path / "different-profile.tiff"
    untagged = tmp_path / "untagged.tiff"
    for path, profile in (
        (tagged, _matrix_icc(srgb=True)),
        (unsupported, _matrix_icc(srgb=False)),
        (untagged, None),
    ):
        tifffile.imwrite(
            path,
            samples,
            photometric="rgb",
            metadata=None,
            iccprofile=profile,
            description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False),
        )
    mask_path = tmp_path / "sky.fits"
    mask = np.ones(samples.shape[:2], np.uint8)
    mask[:3] = 0
    fits.writeto(mask_path, mask)

    preview = preview_mosaic([tagged], spec, sky_masks={0: mask_path}, allow_visual=True)
    assert preview.visual_only and preview.fitted_grid is None
    assert not preview.tile.valid[:2].any() and preview.tile.valid[4, 4]
    mid = ((32768 / 65535 + 0.055) / 1.055) ** 2.4
    np.testing.assert_allclose(
        preview.tile.pixels[4, 4], [0.5, mid, 2000 / 65535 / 12.92], atol=1e-6
    )
    with open_panel(tagged) as panel:
        np.testing.assert_array_equal(panel.read_tile(Region(0, 0, 12, 10)).pixels, samples)
    destination = tmp_path / "science.tiff"
    with pytest.raises(ValueError, match="display.tiff uses sRGB-encoded samples"):
        render_mosaic([tagged], destination, spec, assume_surface_brightness=True)
    assert not destination.exists()
    with pytest.raises(ValueError, match="different-profile.tiff has an unsupported TIFF ICC"):
        preview_mosaic([tagged, unsupported], spec, allow_visual=True)
    with pytest.raises(ValueError, match="untagged.tiff does not declare a supported sRGB"):
        preview_mosaic([tagged, untagged], spec, allow_visual=True)
    mask[4, 4] = 2
    fits.writeto(mask_path, mask, overwrite=True)
    with pytest.raises(ValueError, match=r"display\.tiff: .*sky mask"):
        preview_mosaic([tagged], spec, sky_masks={0: mask_path}, allow_visual=True)


def test_desktop_preview_names_the_panel_that_needs_a_wcs(tmp_path: Path) -> None:
    source = tmp_path / "unsolved.fits"
    fits.writeto(source, np.ones((8, 8), np.float32))
    spec = RenderSpec(CENTER, (12, 10), SCALE_ARCSEC)
    with pytest.raises(ValueError, match=r"unsolved\.fits.*Run Plate Solve for this panel"):
        preview_mosaic([source], spec, auto_frame=True, allow_visual=True)
