import gzip
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from astromosaic.core import Region
from astromosaic.io.fits import open_fits_panel
from astromosaic.pipeline.smoke import write_smoke_panel


def test_scaled_tile_preserves_values_mask_and_source(tmp_path: Path) -> None:
    path = tmp_path / "Gök alanı.fits"
    write_smoke_panel(path)
    original = path.read_bytes()
    original_mtime = path.stat().st_mtime_ns

    with open_fits_panel(path) as panel:
        assert (panel.descriptor.width, panel.descriptor.height) == (16, 12)
        assert panel.descriptor.fingerprint.size_bytes == len(original)
        assert panel.descriptor.fingerprint.modified_ns == original_mtime
        assert panel.descriptor.filter_name == "L"
        assert panel.descriptor.unit == "MJy/sr"
        assert (panel.descriptor.bitpix, panel.descriptor.bscale, panel.descriptor.bzero) == (
            16,
            0.5,
            -2,
        )
        assert panel.descriptor.wcs_provenance == "primary-header"
        assert panel.descriptor.mask_provenance == ("finite-raw-pixels", "primary-header-blank")

        tile = panel.read_tile(Region(5, 3, 3, 2))
        assert tile.region == Region(5, 3, 3, 2)
        assert tile.pixels.dtype == np.dtype(np.float32)
        assert tile.valid.dtype == np.dtype(np.bool_)

    assert path.read_bytes() == original
    assert path.stat().st_mtime_ns == original_mtime
    path.unlink()
    np.testing.assert_array_equal(tile.pixels, [[-1, -0.5, 0], [1, np.nan, 2]])
    np.testing.assert_array_equal(tile.valid, [[True, True, True], [True, False, True]])


def test_metadata_and_rejected_budget_do_not_access_sections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "panel.fits"
    write_smoke_panel(path)

    def unexpected_pixels(_hdu: fits.PrimaryHDU) -> None:
        pytest.fail("The reader accessed pixel data before reserving a tile.")

    monkeypatch.setattr(fits.PrimaryHDU, "data", property(unexpected_pixels))
    monkeypatch.setattr(fits.PrimaryHDU, "section", property(unexpected_pixels))
    with open_fits_panel(path, max_tile_bytes=600) as panel:
        assert panel.descriptor.width == 16
        with pytest.raises(ValueError, match="byte budget"):
            panel.read_tile(Region(0, 0, 1, 1), halo=1)


def test_halo_clips_to_image_edges(tmp_path: Path) -> None:
    path = tmp_path / "panel.fits"
    write_smoke_panel(path)
    with open_fits_panel(path) as panel:
        tile = panel.read_tile(Region(0, 0, 1, 1), halo=1)
        assert tile.region == Region(0, 0, 2, 2)
        np.testing.assert_array_equal(tile.pixels, [[-9.5, -9.0], [-7.5, -7.0]])
        with pytest.raises(ValueError, match="in-bounds"):
            panel.read_tile(Region(15, 11, 2, 1))


def test_unsigned_storage_scaling(tmp_path: Path) -> None:
    path = tmp_path / "uint.fits"
    fits.writeto(path, np.array([[0, 32768, 65535]], dtype=np.uint16))
    with open_fits_panel(path) as panel:
        assert panel.descriptor.unit is None
        assert panel.descriptor.bzero == 32768
        tile = panel.read_tile(Region(0, 0, 3, 1))
    np.testing.assert_array_equal(tile.pixels, [[0, 32768, 65535]])
    assert tile.valid.all()


def test_float_nonfinite_samples_and_overflow(tmp_path: Path) -> None:
    path = tmp_path / "float.fits"
    fits.writeto(path, np.array([[-1, np.nan, np.inf, 1e40]], dtype=np.float64))
    with open_fits_panel(path) as panel:
        tile = panel.read_tile(Region(0, 0, 3, 1))
        np.testing.assert_array_equal(tile.valid, [[True, False, False]])
        np.testing.assert_array_equal(tile.pixels, [[-1, np.nan, np.nan]])
        with pytest.raises(ValueError, match="float32 range"):
            panel.read_tile(Region(3, 0, 1, 1))


def test_rejects_extensions_and_stream_compression(tmp_path: Path) -> None:
    path = tmp_path / "mask.fits"
    pixels = np.ones((2, 2), dtype=np.int16)
    fits.HDUList([fits.PrimaryHDU(pixels), fits.ImageHDU(pixels, name="MASK")]).writeto(path)
    with pytest.raises(ValueError, match="extensions"), open_fits_panel(path):
        pytest.fail("An image with an unhandled mask was accepted.")

    compressed_path = tmp_path / "panel.fits.gz"
    compressed_path.write_bytes(gzip.compress(path.read_bytes()))
    with pytest.raises(ValueError, match="uncompressed FITS"), open_fits_panel(compressed_path):
        pytest.fail("A stream-compressed file was accepted for windowed reads.")
