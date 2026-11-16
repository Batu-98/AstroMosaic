from pathlib import Path

import numpy as np
import pytest
import tifffile
from astropy.io import fits

from astromosaic.core import Region, Tile
from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.core.masks import FOREGROUND, MASK_EDGE, SKY, UNCLASSIFIED, SourceMask
from astromosaic.io import open_panel
from astromosaic.pipeline.masking import (
    DETECTION_EDGE,
    propose_mask,
    read_thumbnail,
    suggest_foreground,
)

_BUDGET = 64 * 1024**2


@pytest.mark.parametrize("suffix", [".fits", ".tiff"])
def test_proposed_mask_excludes_irregular_low_contrast_ground(tmp_path: Path, suffix: str) -> None:
    size = (521, 365)
    width, height = size
    y, x = np.mgrid[:height, :width]
    ground = y >= 210 + 16 * np.sin(x / 42) + 7 * np.sin(x / 12)
    rng = np.random.default_rng(9312)
    luma = 0.0003 * (x + y) - 0.32 * ground + rng.normal(0, 0.11, ground.shape)
    for sx, sy in ((50, 35), (110, 98), (192, 46), (300, 60), (415, 172), (478, 160)):
        luma += 4 * np.exp(-((x - sx) ** 2 + (y - sy) ** 2) / 6)
    luma[30, 20] = 0
    luma[30, 21] = -0.5
    luma[:, 220:226] = np.nan
    pixels = luma.astype(np.float32)
    path = tmp_path / f"mixed{suffix}"
    if suffix == ".tiff":
        pixels = np.stack((pixels - 1, pixels, pixels + 1), axis=-1)
        tifffile.imwrite(path, pixels, photometric="rgb", tile=(64, 64), compression="deflate")
    else:
        fits.writeto(path, pixels)
    original = path.read_bytes()

    with open_panel(path, max_tile_bytes=_BUDGET) as source:
        detection = read_thumbnail(source, DETECTION_EDGE, 4 * 1024**2, JobContext())
        assert suggest_foreground(detection) == "mixed"
        thumb = read_thumbnail(source, MASK_EDGE, _BUDGET, JobContext())
    mask = propose_mask(thumb, size, JobContext())
    assert mask is not None
    labels = mask.read_labels(Region(0, 0, width, height))
    assert not np.any((labels == SKY) & ground)
    assert not np.any((labels == FOREGROUND) & ~ground)
    assert np.count_nonzero((labels == SKY) & ~ground) > 0.8 * np.count_nonzero(~ground)
    assert np.count_nonzero((labels == FOREGROUND) & ground) > 0.8 * np.count_nonzero(ground)
    assert np.any(labels == UNCLASSIFIED)

    with open_panel(path, sky_mask=mask, max_tile_bytes=_BUDGET) as source:
        tile = source.read_tile(Region(0, 0, width, height))
    valid = (labels == SKY) & np.isfinite(luma)
    np.testing.assert_array_equal(tile.valid, valid)
    np.testing.assert_array_equal(tile.pixels[valid], pixels[valid])
    assert tile.valid[30, 20] and tile.valid[30, 21]
    assert np.isnan(tile.pixels[~valid]).all()
    assert path.read_bytes() == original


def test_foreground_check_distinguishes_partial_horizon_and_smooth_sky() -> None:
    width, height = 128, 96
    region = Region(0, 0, width, height)
    y, x = np.mgrid[:height, :width]
    rng = np.random.default_rng(421)
    sky = (0.04 * y + 0.015 * x + rng.normal(0, 0.1, y.shape)).astype(np.float32)
    valid = np.ones(y.shape, dtype=np.bool_)
    assert suggest_foreground(Tile(region, sky, valid)) == "sky-only"
    partial = (y > 58 + 4 * np.sin(x / 6)) & (x < 60)
    mixed = Tile(region, (sky - 3.0 * partial).astype(np.float32), valid)
    assert suggest_foreground(mixed) == "uncertain"
    mask = propose_mask(mixed, (width, height), JobContext())
    assert mask is not None
    assert np.all(mask.grid()[:, 70:] == UNCLASSIFIED)
    assert not np.any((mask.grid() == SKY) & partial)


def test_thumbnail_and_source_mask_share_grid_across_tile_boundaries(tmp_path: Path) -> None:
    width, height, edge = 533, 171, 32
    y, x = np.mgrid[:height, :width]
    pixels = (y - x / 2).astype(np.float32)
    pixels[:24, :54] = np.nan
    path = tmp_path / "source.fits"
    fits.writeto(path, pixels)
    with open_panel(path) as source:
        thumb = read_thumbnail(source, edge, 1 * 1024**2, JobContext())
        with pytest.raises(ValueError, match="cannot fit"):
            read_thumbnail(source, edge, 4096, JobContext())
        stops: list[int] = []
        with pytest.raises(MosaicCancelled):
            read_thumbnail(
                source, edge, _BUDGET, JobContext(lambda: bool(stops), lambda n, _: stops.append(n))
            )
    cols, rows = thumb.region.width, thumb.region.height
    expected = np.full((rows, cols), np.nan, dtype=np.float32)
    for row, col in np.ndindex(expected.shape):
        block = pixels[
            row * height // rows : (row + 1) * height // rows,
            col * width // cols : (col + 1) * width // cols,
        ]
        if np.isfinite(block).any():
            expected[row, col] = np.nanmean(block, dtype=np.float64)
    np.testing.assert_array_equal(thumb.pixels, expected)
    np.testing.assert_array_equal(thumb.valid, np.isfinite(expected))

    cols, rows = MASK_EDGE, 123
    labels = (np.indices((rows, cols)).sum(axis=0) % 3).astype(np.uint8)
    mask = SourceMask((width, height), labels.tobytes())
    expanded = np.repeat(labels, np.diff(np.arange(rows + 1) * height // rows), axis=0)
    expanded = np.repeat(expanded, np.diff(np.arange(cols + 1) * width // cols), axis=1)
    region = Region(251, 62, 89, 47)
    np.testing.assert_array_equal(mask.read_labels(region), expanded[region.slices])
