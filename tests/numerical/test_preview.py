from dataclasses import replace
from pathlib import Path
from struct import pack

import fitsio
import imagecodecs
import numpy as np
import pytest
import tifffile
from astropy.io import fits
from astropy.wcs import WCS
from mosaic_reference import CENTER, SCALE_ARCSEC, WEIGHTS, write_reference_panels
from numpy.typing import NDArray

from astromosaic.core import Region
from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.display import normalize_preview, stretch_rgba
from astromosaic.geometry import tan_output_wcs
from astromosaic.io import open_panel
from astromosaic.photometry.photo import PhotoTone
from astromosaic.pipeline.mosaic import (
    PhotoExport,
    PreviewFrame,
    RenderSpec,
    preview_mosaic,
    render_mosaic,
)


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


def test_adaptive_preview_averages_valid_subsamples_and_reuses_tone(tmp_path: Path) -> None:
    width, height = 2048, 12
    spec = RenderSpec(CENTER, (width, height), SCALE_ARCSEC, tile_size=127)
    pattern = np.array([
        [8, 0, 0, np.nan],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 4],
    ], np.float32)
    source = tmp_path / "area.fits"
    values = np.tile(pattern, (height // 4, width // 4))
    values[:, :4] = np.nan
    header = spec.output_wcs().to_header()
    header["BUNIT"] = "MJy/sr"
    fits.writeto(source, values, header)
    reference = preview_mosaic([source], spec)
    filtered = preview_mosaic([source], spec, adaptive_edge=512)
    assert filtered.output_size == (width, height)
    assert filtered.tile.valid.shape == (3, 512)
    assert not filtered.tile.valid[:, 0].any() and filtered.tile.valid[:, 1:].all()
    np.testing.assert_allclose(filtered.tile.pixels[:, 1:], 12 / 15, atol=1e-5)
    assert reference.tile.pixels[1, 2] == pytest.approx(0)
    assert filtered.tone_levels == (0.0, 0.0)
    assert filtered.peak_reserved_bytes <= spec.max_working_bytes

    window = Region(899, 2, 13, 7)
    detail = preview_mosaic([source], spec, window=window)
    export = tmp_path / "detail.fits"
    cropped = replace(spec, crop=window)
    render_mosaic([source], export, cropped)
    with fitsio.FITS(export) as reopened:
        np.testing.assert_array_equal(detail.tile.pixels, reopened[0].read())
        np.testing.assert_array_equal(detail.tile.valid, reopened["COVERAGE"].read())
    assert detail.tile.region == window and detail.output_size == spec.size


def test_auto_framing_respects_partial_locks_and_recommends_a_crop(tmp_path: Path) -> None:
    source = tmp_path / "inclined.fits"
    _write_sky_panel(source, RenderSpec(CENTER, (56, 18), SCALE_ARCSEC, 25))
    region = Region(18, 13, 90, 26)
    spec = RenderSpec(CENTER, (124, 62), SCALE_ARCSEC, crop=region, projection="ZEA")
    automatic = preview_mosaic([source], spec, auto_frame=True)
    locked = preview_mosaic(
        [source], spec, auto_frame=True,
        frame_locks=frozenset(("center", "projection", "size", "scale", "crop")),
    )
    assert locked.fitted_grid == spec
    assert locked.fitted_grid.output_region() == region
    assert locked.suggested_crop is not None and locked.suggested_crop != region
    assert Region(0, 0, *spec.size).contains(locked.suggested_crop)
    assert locked.suggested_rotation is not None
    assert abs(locked.suggested_rotation - 25) <= 3
    assert automatic.fitted_grid is not None and automatic.fitted_grid.size != spec.size
    uncropped = preview_mosaic([source], replace(spec, crop=None), inspect_crop=True)
    assert uncropped.output_size == spec.size and uncropped.suggested_crop == locked.suggested_crop


@pytest.mark.parametrize("preserve", [False, True], ids=["preview-tone", "preserve-tone"])
def test_photo_encodes_the_full_weighted_grid_and_preserves_coverage(
    tmp_path: Path, preserve: bool
) -> None:
    spec = RenderSpec(CENTER, (1536, 144), SCALE_ARCSEC, tile_size=91)
    header = spec.output_wcs().to_header()
    header["CRPIX1"] += 0.5
    header["FILTER"] = "RGB"
    row, col = np.indices(spec.size[::-1])
    first = np.stack((col % 2 * 50000, row * 350, col * 3), axis=-1).astype(np.uint16)
    second = np.stack((col % 2 * 2000, col * 40, row * 400), axis=-1).astype(np.uint16)
    first[:, :6] = second[:, :6] = 0
    panels = [tmp_path / f"sRGB-{index}.tiff" for index in (1, 2)]
    for path, pixels in zip(panels, (first, second), strict=True):
        tifffile.imwrite(
            path, pixels, photometric="rgb", metadata=None, iccprofile=_matrix_icc(srgb=True),
            description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False),
        )
    mask = tmp_path / "sky.fits"
    valid = np.ones(spec.size[::-1], np.uint8)
    valid[:9] = 0
    fits.writeto(mask, valid)
    masks = {0: mask, 1: mask}
    weights = (1, 3)
    midtones = 0.31
    original = [path.read_bytes() for path in panels]
    preview = preview_mosaic(panels, spec, weights=weights, sky_masks=masks, allow_visual=True)
    photo = tmp_path / "photo.tiff"
    result = render_mosaic(
        panels, photo, spec, weights=weights, sky_masks=masks,
        photo=PhotoExport(None if preserve else PhotoTone(midtones)),
    )
    assert (result.width, result.height) == spec.size
    assert result.peak_reserved_bytes <= spec.max_working_bytes
    rgba = imagecodecs.tiff_decode(photo.read_bytes())
    assert rgba.dtype == np.uint16 and rgba.shape == (*first.shape[:2], 4)
    pixels = rgba[..., :3]
    alpha = rgba[..., 3]

    def decode(rgb: NDArray[np.uint16]) -> NDArray[np.float64]:
        encoded = rgb.astype(np.float64) / 65535
        return np.where(encoded <= 0.04045, encoded / 12.92, ((encoded + 0.055) / 1.055) ** 2.4)

    first_linear, second_linear = decode(first), decode(second)
    blended = (
        first_linear[:, :-1] + first_linear[:, 1:]
        + 3 * (second_linear[:, :-1] + second_linear[:, 1:])
    ) / 8
    linear_samples = blended[1::3, 1::3]
    covered = preview.tile.valid
    np.testing.assert_allclose(preview.tile.pixels[covered], linear_samples[covered], atol=1e-6)
    if not preserve:
        black, white = np.percentile(linear_samples[covered], (1, 99.5))
        linear_samples = np.clip((linear_samples - black) / (white - black), 0.0, 1.0)
        linear_samples = (1 - midtones) * linear_samples / (
            midtones + (1 - 2 * midtones) * linear_samples
        )
    encoded = np.where(
        linear_samples <= 0.0031308, linear_samples * 12.92,
        1.055 * linear_samples ** (1 / 2.4) - 0.055,
    )
    np.testing.assert_allclose(
        pixels[1::3, 1::3][covered], np.rint(encoded[covered] * 65535), atol=2, rtol=0
    )
    display = stretch_rgba(normalize_preview(preview), midtones, preserve_tone=preserve)
    np.testing.assert_allclose(
        display[covered, :3], np.rint(pixels[1::3, 1::3][covered] / 257), atol=1, rtol=0
    )
    with tifffile.TiffFile(photo) as output:
        page = output.pages[0]
        assert isinstance(page, tifffile.TiffPage)
        assert imagecodecs.cms_info(page.tags[34675].value)["description"] == "sRGB2014"
        assert page.extrasamples == (tifffile.EXTRASAMPLE.ASSOCALPHA,)
        assert not page.subifds
    assert set(np.unique(alpha)) == {0, 65535}
    coverage = alpha == 65535
    np.testing.assert_array_equal(coverage[1::3, 1::3], covered)
    assert int(coverage.sum()) == result.covered_pixels
    assert (pixels[~coverage] == 0).all()
    if preserve:
        assert coverage[12, 1] and not pixels[12, 1].any()
    with open_panel(photo) as output_panel:
        metadata = output_panel.header
        assert output_panel.descriptor.icc_encoding == "srgb"
        assert output_panel.descriptor.icc_profile_sha256 == (
            "384b832de3412066743b52a75ee906b6fb9fb8d9e09e936fc2c43223815c6e0a"
        )
        assert metadata["AMINTENT"] == "PHOTO" and "BUNIT" not in metadata
        assert metadata["FILTER"] == "RGB"
        assert metadata["PHOTOTON"] == ("preserve" if preserve else "preview")
        assert output_panel.descriptor.channel_layout == "rgb"
        window = output_panel.read_tile(Region(0, 7, 12, 6))
        np.testing.assert_array_equal(window.valid, coverage[7:13, :12])
        np.testing.assert_array_equal(window.pixels[window.valid], pixels[7:13, :12][window.valid])
        if not preserve:
            assert metadata["PHOTOMID"] == midtones
            assert metadata["PHOTOBLK"] == pytest.approx(black, abs=1e-6)
            assert metadata["PHOTOWHT"] == pytest.approx(white, abs=1e-6)
    xy = ([0, 767, 1535], [0, 71, 143])
    np.testing.assert_allclose(
        WCS(metadata).pixel_to_world_values(*xy), spec.output_wcs().pixel_to_world_values(*xy),
        atol=1e-9, rtol=0,
    )
    with pytest.raises(ValueError, match="uses sRGB-encoded samples"):
        render_mosaic([photo], tmp_path / "science.tiff", spec, assume_surface_brightness=True)
    assert [path.read_bytes() for path in panels] == original


def test_reopen_legacy_photo_tiff_with_binary_coverage(tmp_path: Path) -> None:
    photo = tmp_path / "legacy-photo.tiff"
    header = RenderSpec(CENTER, (2, 1), SCALE_ARCSEC).output_wcs().to_header()
    header["AMINTENT"] = "PHOTO"
    with tifffile.TiffWriter(photo) as writer:
        writer.write(
            np.zeros((1, 2, 3), np.uint16), photometric="rgb", metadata=None, subifds=1,
            iccprofile=_matrix_icc(srgb=True),
            description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False),
        )
        writer.write(np.array([[1, 0]], np.uint8), photometric="minisblack", metadata=None)
    with open_panel(photo) as panel:
        assert panel.descriptor.icc_encoding == "srgb"
        tile = panel.read_tile(Region(0, 0, 2, 1))
        np.testing.assert_array_equal(tile.valid, [[True, False]])
        np.testing.assert_array_equal(tile.pixels[0, 0], [0, 0, 0])


def test_photo_errors_cancel_and_retry(tmp_path: Path) -> None:
    spec = RenderSpec(CENTER, (32, 16), SCALE_ARCSEC, tile_size=8)
    source = tmp_path / "sRGB.tif"
    linear = tmp_path / "linear.tif"
    for path, profile in ((source, _matrix_icc(srgb=True)), (linear, None)):
        tifffile.imwrite(
            path, np.ones((16, 32, 3), np.uint16), photometric="rgb", metadata=None,
            iccprofile=profile,
            description="AstroMosaic TIFF 1\n" + spec.output_wcs().to_header().tostring(sep="\n"),
        )
    output = tmp_path / "new.tiff"
    photo = PhotoExport(None)
    with pytest.raises(ValueError, match=r"linear\.tif: Photo export requires"):
        render_mosaic([source, linear], output, spec, photo=photo)
    with pytest.raises(ValueError, match="requires a .tif or .tiff"):
        render_mosaic([source], output.with_suffix(".xisf"), spec, photo=photo)
    with pytest.raises(ValueError, match="output byte limit"):
        render_mosaic(
            [source], output, replace(spec, max_output_bytes=spec.size[0] * spec.size[1] * 8),
            photo=photo,
        )
    with pytest.raises(ValueError, match="no valid input coverage"):
        render_mosaic([source], output, replace(spec, center=(150.0, -20.0)), photo=photo)
    cancelled = False

    def cancel_after_tile(_done: int, _total: int) -> None:
        nonlocal cancelled
        cancelled = True

    with pytest.raises(MosaicCancelled):
        render_mosaic(
            [source], output, spec, photo=photo,
            context=JobContext(is_cancelled=lambda: cancelled, on_progress=cancel_after_tile),
        )
    assert cancelled and not output.exists() and not list(tmp_path.glob("*.part"))
    render_mosaic([source], output, spec, photo=photo)
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        render_mosaic([source], output, spec, photo=photo)
    assert output.read_bytes() == original
