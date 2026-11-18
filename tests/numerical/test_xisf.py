import struct
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import tifffile
from astropy.io import fits
from astropy.wcs import WCS
from numpy.typing import NDArray
from xisf_reference import read_xisf_attachments

from astromosaic.core import Region
from astromosaic.geometry import tan_output_wcs
from astromosaic.io import open_panel
from astromosaic.io.xisf import XisfTileSource
from astromosaic.pipeline.mosaic import RenderSpec, render_mosaic

_SIZE = (7, 6)
_CENTER = (359.999, 20.0)
_SCALE = 7.2
_NAMESPACE = "{http://www.pixinsight.com/xisf}"


def _fixture(
    path: Path,
    pixels: NDArray[np.generic],
    coverage: NDArray[np.uint8],
    storage: str = "Planar",
    extra: str = "",
    mask_offset: int = 8192,
) -> None:
    width, height = _SIZE
    sample_format = "Float32" if pixels.dtype.kind == "f" else "UInt16"
    byte_order = "big" if pixels.dtype.byteorder == ">" else "little"
    channels = pixels.shape[-1] if pixels.ndim == 3 else 1
    color_space = "RGB" if channels == 3 else "Gray"
    stored = np.moveaxis(pixels, -1, 0) if channels == 3 and storage == "Planar" else pixels
    xml = f"""
<xisf xmlns="http://www.pixinsight.com/xisf" version="1.0">
    <Image geometry="{width}:{height}:{channels}" sampleFormat="{sample_format}"
           colorSpace="{color_space}" pixelStorage="{storage}" byteOrder="{byte_order}"
           location="attachment:4096:{stored.nbytes}" {extra}>
        <FITSKeyword name="FILTER" value="'L'" comment="Filter"/>
        <FITSKeyword name="BUNIT" value="'MJy/sr'" comment="Brightness"/>
        <FITSKeyword name="OBJECT" value="'Barnard''s star'" comment="Quoted name"/>
        <FITSKeyword name="BSCALE" value="100" comment="Earlier FITS representation"/>
        <FITSKeyword name="BZERO" value="32768" comment="Earlier FITS representation"/>
        <FITSKeyword name="CTYPE1" value="'RA---TAN'" comment=""/>
        <FITSKeyword name="CTYPE2" value="'DEC--TAN'" comment=""/>
        <FITSKeyword name="CRPIX1" value="4.0" comment=""/>
        <FITSKeyword name="CRPIX2" value="3.5" comment=""/>
        <FITSKeyword name="CRVAL1" value="{_CENTER[0]}" comment=""/>
        <FITSKeyword name="CRVAL2" value="{_CENTER[1]}" comment=""/>
        <FITSKeyword name="CDELT1" value="-0.002" comment=""/>
        <FITSKeyword name="CDELT2" value="2.0D-3" comment=""/>
    </Image>
    <Image id="AstroMosaicCoverage" geometry="{width}:{height}:1" sampleFormat="UInt8"
           location="attachment:{mask_offset}:{coverage.nbytes}"/>
    <Metadata>
        <Property id="XISF:CreationTime" type="TimePoint" value="2026-11-18T00:00:00Z"/>
        <Property id="XISF:CreatorApplication" type="String">AstroMosaic tests</Property>
    </Metadata>
</xisf>
""".encode()
    with path.open("wb") as stream:
        stream.write(struct.pack("<8sII", b"XISF0100", len(xml), 0))
        stream.write(xml)
        stream.seek(4096)
        stream.write(stored.tobytes())
        stream.seek(8192)
        stream.write(coverage.tobytes())


@pytest.mark.parametrize(
    ("storage", "dtype"), [("Planar", ">u2"), ("Planar", "<f4"), ("Normal", ">f4")]
)
def test_xisf_import_preserves_layout_samples_and_masks(
    tmp_path: Path, storage: str, dtype: str
) -> None:
    source = tmp_path / "Gökyüzü.XISF"
    values = np.arange(42).reshape(6, 7)
    if dtype.endswith("u2"):
        pixels = values.astype(dtype)
        pixels[0, 1] = 65535
    else:
        pixels = np.stack((values, -values, values * 2), axis=-1).astype(dtype)
        pixels[1, 3, 1] = np.inf
    coverage = np.ones(values.shape, dtype="uint8")
    coverage[2, 2] = 0
    _fixture(source, pixels, coverage, storage)
    original = source.read_bytes(), source.stat().st_mtime_ns
    sky_mask = tmp_path / "sky.fits"
    sky = np.ones(values.shape, dtype="uint8")
    sky[3, 1] = 0
    fits.writeto(sky_mask, sky)

    region = Region(0, 0, 3, 3)
    with open_panel(source, sky_mask=sky_mask) as panel:
        descriptor = panel.descriptor
        assert descriptor.channel_layout == ("mono" if pixels.ndim == 2 else "rgb")
        assert descriptor.wcs_provenance == "xisf-fits-keywords"
        assert descriptor.unit == "MJy/sr" and descriptor.filter_name == "L"
        assert (descriptor.bscale, descriptor.bzero) == (1.0, 0.0)
        assert panel.header["OBJECT"] == "Barnard's star"
        assert "BZERO" not in panel.header and "BSCALE" not in panel.header
        tile = panel.read_tile(region, halo=1)
        assert tile.region == Region(0, 0, 4, 4)
        valid = (coverage & sky).astype(bool)
        finite = np.isfinite(pixels)
        valid &= finite.all(axis=-1) if pixels.ndim == 3 else finite
        expected = pixels.astype(np.float32)
        expected[~valid] = np.nan
        np.testing.assert_array_equal(tile.valid, valid[:4, :4])
        np.testing.assert_array_equal(tile.pixels, expected[:4, :4])
        offset = panel.read_tile(Region(5, 4, 2, 2))
        np.testing.assert_array_equal(offset.pixels, expected[4:, 5:])
    with open_panel(source, max_tile_bytes=1) as panel:
        with pytest.raises(ValueError, match="XISF tile.*byte budget"):
            panel.read_tile(region)
    assert (source.read_bytes(), source.stat().st_mtime_ns) == original


@pytest.mark.parametrize(
    ("extra", "mask_offset", "truncate", "diagnostic"),
    [
        ('compression="zlib:168"', 8192, False, "without compression"),
        ("", 4097, False, "attachments overlap"),
        ("", 8192, True, "attachment is truncated"),
    ],
)
def test_xisf_attachment_failures_are_explicit(
    tmp_path: Path, extra: str, mask_offset: int, truncate: bool, diagnostic: str
) -> None:
    source = tmp_path / "invalid.xisf"
    _fixture(
        source,
        np.zeros((6, 7), dtype="<f4"),
        np.ones((6, 7), dtype="uint8"),
        extra=extra,
        mask_offset=mask_offset,
    )
    if truncate:
        with source.open("r+b") as stream:
            stream.truncate(source.stat().st_size - 1)
    with pytest.raises(ValueError, match=diagnostic), open_panel(source):
        pytest.fail("An invalid XISF source opened.")


def test_rotated_rgb_xisf_export_matches_tiff_and_does_not_clip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "linear.xisf"
    values = np.arange(42, dtype=np.float32).reshape(6, 7)
    values[1:4, 2:5] = 0
    rgb = np.stack((values, -values, 2 * values), axis=-1)
    mask = np.ones((6, 7), dtype=np.uint8)
    mask[4, 4] = 0
    _fixture(source, rgb, mask)
    spec = RenderSpec(_CENTER, _SIZE, _SCALE, 11.5, Region(1, 1, 5, 4), tile_size=2)
    destination = tmp_path / "rotated.xisf"
    tiff = destination.with_suffix(".tiff")
    render_mosaic([source], tiff, spec)
    summary = render_mosaic([source], destination, spec)
    (pixels, coverage), science = read_xisf_attachments(destination)
    assert summary.covered_pixels == int(coverage.sum())
    assert np.any(~coverage.astype(bool)) and np.any((pixels == 0) & coverage[..., None])
    finite = pixels[np.isfinite(pixels)].astype(np.float32, copy=False)
    bounds = float(finite.min()), float(finite.max())
    assert bounds[0] < 0 and bounds[1] > 1
    assert tuple(map(float, science.attrib["bounds"].split(":"))) == bounds
    with tifffile.TiffFile(tiff) as reference:
        page = reference.pages[0]
        assert isinstance(page, tifffile.TiffPage) and page.pages is not None
        np.testing.assert_array_equal(pixels, page.asarray())
        np.testing.assert_array_equal(coverage, page.pages[0].asarray())
    keywords = {
        item.attrib["name"]: item.attrib["value"]
        for item in science.findall(f"{_NAMESPACE}FITSKeyword")
    }
    assert keywords["FILTER"] == "'L'" and keywords["BUNIT"] == "'MJy/sr'"
    header = fits.Header.fromstring(
        "\n".join(f"{name:8}= {value}" for name, value in keywords.items() if name != "HISTORY"),
        sep="\n",
    )
    points = ([0, 4, 2], [0, 3, 1])
    target = tan_output_wcs(_CENTER, _SIZE, _SCALE, spec.rotation_deg, spec.output_region())
    np.testing.assert_allclose(
        WCS(header).pixel_to_world_values(*points),
        target.pixel_to_world_values(*points),
        rtol=0,
        atol=1e-9,
    )
    with open_panel(destination) as panel:
        tile = panel.read_tile(Region(0, 0, summary.width, summary.height))
        np.testing.assert_array_equal(tile.pixels, pixels)
        np.testing.assert_array_equal(tile.valid, coverage)

    def unexpected_read(*args: object, **kwargs: object) -> None:
        pytest.fail("A job beyond the XISF file limit read image pixels.")

    monkeypatch.setattr(XisfTileSource, "read_tile", unexpected_read)
    refused = tmp_path / "refused.xisf"
    limited = replace(spec, max_output_bytes=destination.stat().st_size - 1)
    with pytest.raises(ValueError, match="XISF mosaic.*output byte limit"):
        render_mosaic([source], refused, limited)
    assert not refused.exists() and not list(tmp_path.glob("*.part"))
