import json
from pathlib import Path

import fitsio
import numpy as np
import pytest
from astropy.io import fits
from numpy.typing import NDArray
from phase2_reference import (
    ARCSEC,
    CENTER,
    EMISSION_CENTER,
    GAINS,
    PLANES,
    SHIFTS,
    SIZE,
    STAR_CENTER,
    write_panels,
)

from astromosaic.astrometry.registration import ProjectedField, register
from astromosaic.cli import main
from astromosaic.core.job import JobContext
from astromosaic.pipeline.mosaic import RenderSpec, render_mosaic
from astromosaic.pipeline.refinement import RefinementSpec


def _profile(
    flux: NDArray[np.float64], x: NDArray[np.float64], y: NDArray[np.float64]
) -> tuple[NDArray[np.float64], float, float]:
    positions = np.column_stack((x, y))
    centroid = np.average(positions, weights=flux, axis=0)
    centered = positions - centroid
    covariance = (centered.T * flux) @ centered / flux.sum()
    minor, major = np.sqrt(np.linalg.eigvalsh(covariance))
    return centroid, float(2.355 * np.sqrt(minor * major)), float(1 - minor / major)


def test_three_panel_refinement_preserves_stars_emission_and_sky_mask(tmp_path: Path) -> None:
    products = []
    for injected in (True, False):
        directory = tmp_path / ("injected" if injected else "control")
        directory.mkdir()
        fixture = write_panels(directory, injected=injected)
        originals = {path: path.read_bytes() for path in (*fixture.paths, fixture.mask)}
        output = directory / "refined.fits"
        result = render_mosaic(
            fixture.paths,
            output,
            RenderSpec(CENTER, SIZE, ARCSEC, tile_size=37),
            sky_masks={1: fixture.mask},
            refinement=RefinementSpec(background="plane"),
        )
        refined = result.refinement
        assert refined is not None and refined.status == "ready"
        assert refined.components == ((1, 2, 3),)
        assert [(1, 2), (2, 3)] == [edge.panels for edge in refined.edges if edge.training_inliers]
        alignment = refined.held_out_alignment
        assert alignment is not None and alignment.count >= 4 and alignment.p95_px < 0.5
        assert refined.held_out_gain_error is not None and refined.held_out_gain_error < 0.01
        np.testing.assert_allclose(
            [item.shift for item in refined.corrections], -np.array(SHIFTS), atol=0.05
        )
        np.testing.assert_allclose([item.gain for item in refined.corrections], GAINS, rtol=0.01)
        np.testing.assert_allclose(
            [item.background for item in refined.corrections], PLANES, atol=0.06
        )
        background = refined.background
        assert background is not None and background.model == "plane"
        assert background.uncorrected_median is not None and background.corrected_median is not None
        assert background.corrected_median < 0.1 * background.uncorrected_median

        with fitsio.FITS(output) as hdus:
            pixels = hdus[0].read()
            coverage = hdus["COVERAGE"].read()
            assert coverage[133, 180] == 0 and np.isnan(pixels[133, 180])
            assert coverage[60, 180] == 1
            assert np.nanmax(pixels) < 150  # The supplied ground is at least 300 brightness units.
            products.append(pixels)
        assert {path: path.read_bytes() for path in originals} == originals

    y, x = np.indices(products[0].shape, dtype=np.float64)
    star_radius = np.hypot(x - STAR_CENTER[0], y - STAR_CENTER[1])
    sky = 5 + 0.003 * (x - 170) - 0.004 * (y - 70)
    observed = (products[1] - sky)[star_radius < 8]
    reference = (fixture.truth - sky)[star_radius < 8]
    np.testing.assert_allclose(observed.sum(), reference.sum(), rtol=0.01)
    centroid, fwhm, ellipticity = _profile(observed, x[star_radius < 8], y[star_radius < 8])
    _, truth_fwhm, truth_ellipticity = _profile(reference, x[star_radius < 8], y[star_radius < 8])
    np.testing.assert_allclose(centroid, STAR_CENTER, rtol=0, atol=0.12)
    np.testing.assert_allclose(fwhm, truth_fwhm, rtol=0.08)
    np.testing.assert_allclose(ellipticity, truth_ellipticity, rtol=0, atol=0.05)
    assert np.min((products[1] - sky)[(star_radius >= 7) & (star_radius < 10)]) > -0.2

    emission_aperture = np.hypot(x - EMISSION_CENTER[0], y - EMISSION_CENTER[1]) < 22
    recovered = (products[0] - products[1])[emission_aperture].sum()
    np.testing.assert_allclose(recovered, fixture.emission[emission_aperture].sum(), rtol=0.05)


def test_constant_background_prefers_offset_to_plane(tmp_path: Path) -> None:
    fixture = write_panels(tmp_path, planes=False)
    first, second = tmp_path / "first-tiles.fits", tmp_path / "second-tiles.fits"
    refine = RefinementSpec(background="plane")
    prepared = []
    for output, tile_size in ((first, 37), (second, 96)):
        result = render_mosaic(
            fixture.paths,
            output,
            RenderSpec(CENTER, SIZE, ARCSEC, tile_size=tile_size),
            sky_masks={1: fixture.mask},
            refinement=refine,
        )
        report = result.refinement
        assert report is not None and report.background is not None
        assert report.background.model == "offset"
        np.testing.assert_allclose(
            [item.background for item in report.corrections],
            [(plane[0], 0, 0) for plane in PLANES],
            atol=0.035,
        )
        with fitsio.FITS(output) as hdus:
            prepared.append((hdus[0].read(), hdus["COVERAGE"].read()))
    np.testing.assert_array_equal(prepared[0][0], prepared[1][0])
    np.testing.assert_array_equal(prepared[0][1], prepared[1][1])


@pytest.mark.parametrize("status", ["weak", "disconnected"])
def test_refined_cli_declines_weak_or_disconnected_panels(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], status: str
) -> None:
    fixture = write_panels(tmp_path)
    first, middle, _ = fixture.paths
    invalid = tmp_path / "unsuitable.fits"
    header = fits.getheader(middle)
    values = fits.getdata(middle)
    if status == "weak":
        values.fill(1.0)
    else:
        header["CRPIX1"] -= 1000
    fits.writeto(invalid, values, header)
    output = tmp_path / "failed.fits"
    assert (
        main(
            [
                "mosaic",
                str(first),
                str(invalid),
                "-o",
                str(output),
                "--refine",
                "--center",
                *map(str, CENTER),
                "--size",
                *map(str, SIZE),
                "--scale",
                str(ARCSEC),
            ]
        )
        == 1
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == status
    assert result["refinement"]["components"] == [[1], [2]]
    assert not output.exists()


def test_stellar_fit_discards_training_mismatches_and_variable_flux() -> None:
    index = np.arange(32, dtype=np.float64)
    positions = np.column_stack((15 * index, 17 * (index % 7)))
    shifted = positions + [1.3, -0.6]
    shifted[[5, 9, 17]] += [2.25, 0.75]
    flux = 10 + index
    scaled = flux / 1.4
    scaled[11] *= 4
    bounds = (-20.0, -20.0, 500.0, 150.0)
    result = register(
        [ProjectedField(bounds, positions, flux), ProjectedField(bounds, shifted, scaled)],
        6.0,
        JobContext(),
    )
    assert result.status == "ready"
    assert result.edges[0].training_inliers < (result.edges[0].matched - result.edges[0].held_out)
    np.testing.assert_allclose(result.shifts[1], [-1.3, 0.6], rtol=0, atol=1e-10)
    np.testing.assert_allclose(result.gains[1], 1.4, rtol=1e-10)
