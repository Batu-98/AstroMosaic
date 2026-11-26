"""Check signed detector samples and the combined science and flat masks."""

from pathlib import Path

import numpy as np
from astropy.io import fits

from astromosaic.core import Region
from tools.phase8d_nircam_flat import (
    DetectorTile,
    StarMeasurements,
    _aperture,
    _compare_pair,
    _read_tile,
)


def test_flat_replay_masks_response_and_preserves_signed_science(tmp_path: Path) -> None:
    rate_path = tmp_path / "rate.fits"
    flat_path = tmp_path / "flat.fits"
    for path, samples, flags in (
        (rate_path, [[-2, 0, 3, 4], [9, 10, 11, 12]], [[0, 0, 0, 0], [1, 0, 0, 0]]),
        (flat_path, [[0.5, 2, 1.5, 0.1], [1, 2, float("nan"), 0]], [[0, 0, 0, 0], [0, 1, 0, 0]]),
    ):
        fits.HDUList(
            [
                fits.PrimaryHDU(),
                fits.ImageHDU(np.asarray(samples, dtype=np.float32), name="SCI"),
                fits.ImageHDU(np.asarray(flags, dtype=np.uint32), name="DQ"),
            ]
        ).writeto(path)

    with fits.open(rate_path, memmap=False) as rate, fits.open(flat_path, memmap=False) as flat:
        tile = _read_tile(rate, flat, Region(0, 0, 4, 2))

    np.testing.assert_array_equal(tile.valid, [[True, True, True, False], [False] * 4])
    np.testing.assert_array_equal(tile.corrected[0, :3], [-4, 0, 2])
    assert np.isnan(tile.corrected[~tile.valid]).all()


def test_high_signal_aperture_uses_original_rate_error() -> None:
    rate = np.full((25, 25), 2, dtype=np.float32)
    rate[12, 12] += 1200
    response = np.full_like(rate, 0.5)
    tile = DetectorTile(rate, response, np.ones(rate.shape, dtype=np.bool_), rate / response)
    error = np.ones_like(rate)

    np.testing.assert_allclose(
        _aperture(tile, 12.0, 12.0, error, 100)[:3], [1200, 2400, 4800], rtol=0.001
    )
    assert np.isnan(_aperture(tile, 12.0, 12.0, 2 * error, 100)).all()
    error[12, 12] = np.nan
    assert np.isnan(_aperture(tile, 12.0, 12.0, error, 100)).all()


def test_weak_overlap_reports_apertures_without_an_exposure_scale() -> None:
    xy = np.array([[32.0, 32.0], [96.0, 32.0]])
    flux = np.full((2, 3), 100.0)
    first = StarMeasurements(xy, xy, flux, np.ones(2))
    second = StarMeasurements(xy, xy, flux, np.full(2, 1.03))

    result = _compare_pair(first, second)

    assert result["training_apertures"] == 1
    assert result["training_flux_ratios"] is None
    assert result["held_out_geometry_p95_px"] is None
    assert result["held_out_apertures"] == {
        "all": {"stars": 1, "blocks": 1},
        "one_percent_response_change": {"stars": 1, "blocks": 1},
    }
