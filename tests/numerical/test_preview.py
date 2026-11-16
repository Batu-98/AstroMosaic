from pathlib import Path

import fitsio
import numpy as np
import tifffile
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
