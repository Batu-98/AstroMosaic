import json
from contextlib import ExitStack
from pathlib import Path

import fitsio
import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS
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
from astromosaic.astrometry.solve import load_solution
from astromosaic.astrometry.stars import measure_stars
from astromosaic.cli import main
from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.core.masks import FOREGROUND, SKY, SourceMask
from astromosaic.geometry import read_panel_geometry, tan_output_wcs
from astromosaic.io import open_panel
from astromosaic.photometry.background import BackgroundPanel, fit_background
from astromosaic.pipeline.mosaic import (
    DEFAULT_WORKING_BYTES,
    RenderSpec,
    preview_mosaic,
    render_mosaic,
)
from astromosaic.pipeline.refinement import RefinementSpec
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    load_project,
    render_project,
    save_project,
)


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
        spec = RenderSpec(CENTER, SIZE, ARCSEC, tile_size=37)
        refinement = RefinementSpec(background="plane")
        if injected:
            labels = np.where(fits.getdata(fixture.mask) == 1, SKY, FOREGROUND).astype(np.uint8)
            height, width = labels.shape
            mask = SourceMask((width, height), labels.tobytes())
            panels = tuple(
                ProjectPanel(FileReference.capture(path), source_mask=mask if index == 1 else None)
                for index, path in enumerate(fixture.paths)
            )
            manifest = directory / "mixed.astromosaic"
            save_project(manifest, MosaicProject(panels, spec, refinement=refinement))
            result = render_project(load_project(manifest), output, JobContext())
        else:
            result = render_mosaic(
                fixture.paths, output, spec, sky_masks={1: fixture.mask}, refinement=refinement
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
            assert np.nanmax(pixels) < 150  # The injected ground is at least 300 brightness units.
            products.append(pixels)
        if injected:
            preview = preview_mosaic(
                fixture.paths,
                spec,
                sky_masks={1: fixture.mask},
                refinement=refinement,
            )
            np.testing.assert_array_equal(preview.tile.pixels, pixels)
            np.testing.assert_array_equal(preview.tile.valid, coverage)
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


def test_narrow_overlap_prefers_offset_to_plane(tmp_path: Path) -> None:
    width, height = 176, 144
    size = (348, height)
    header = tan_output_wcs(CENTER, size, ARCSEC, 0, Region(0, 0, *size)).to_header()
    target = read_panel_geometry(header, *size)
    normalized_x = 2 * np.arange(width) / (width - 1) - 1
    left = np.full((height, width), 10, dtype=np.float32)
    right = np.tile(10 - (3 + normalized_x), (height, 1)).astype(np.float32)

    with ExitStack() as stack:
        panels = []
        for x_origin, pixels in ((0, left), (172, right)):
            path = tmp_path / f"strip-{x_origin}.fits"
            panel_header = header.copy()
            panel_header["CRPIX1"] -= x_origin
            fits.writeto(path, pixels, panel_header)
            source = stack.enter_context(open_panel(path))
            panels.append(
                BackgroundPanel(
                    source=source,
                    geometry=read_panel_geometry(source.header, width, height),
                    bounds=(x_origin - 0.5, -0.5, x_origin + width - 0.5, height - 0.5),
                    exclusions=np.empty((0, 3), dtype=np.float64),
                    shift=(0.0, 0.0),
                    gain=1.0,
                )
            )
        coefficients, report = fit_background(
            panels, ((0, 1),), target, "plane", DEFAULT_WORKING_BYTES, JobContext()
        )

    assert report.model == "offset"
    assert 0 < report.held_out < report.samples
    np.testing.assert_array_equal(coefficients[0], 0.0)
    np.testing.assert_array_equal(coefficients[1, 1:], 0.0)
    # The common strip spans the first four columns of the right panel.
    assert coefficients[1, 0] == pytest.approx(2 + 3 / (width - 1), abs=0.05, rel=0)
    assert report.uncorrected_median is not None and report.corrected_median is not None
    assert report.corrected_median <= 0.95 * report.uncorrected_median


def test_saturated_stars_are_excluded_from_flux_and_masked_for_background(tmp_path: Path) -> None:
    shape = (144, 160)
    y, x = np.indices(shape, dtype=np.float64)
    pixels = np.random.default_rng(4819).normal(5.0, 0.03, shape)
    saturated = ((40, 50), (110, 100))
    unsaturated = ((110, 50), (40, 100))
    for positions, amplitude in ((saturated, 180), (unsaturated, 80)):
        for sx, sy in positions:
            pixels += amplitude * np.exp(-((x - sx) ** 2 + (y - sy) ** 2) / (2 * 1.6**2))
    path = tmp_path / "saturated.fits"
    fits.writeto(path, pixels.astype(np.float32), fits.Header({"SATURATE": 120}))
    with open_panel(path) as panel:
        field = measure_stars(panel, DEFAULT_WORKING_BYTES, JobContext())

    measured = np.array([(star.x, star.y) for star in field.stars]).reshape(-1, 2)
    for position in unsaturated:
        assert np.any(np.linalg.norm(measured - position, axis=1) <= 1), position
    for position in saturated:
        assert not np.any(np.linalg.norm(measured - position, axis=1) <= 1), position
        assert np.any(np.linalg.norm(field.exclusions[:, :2] - position, axis=1) <= 1), position


def _assert_matching_wcs(first: WCS, second: WCS, width: int, height: int) -> None:
    x = [(width - 1) / 2, 0, 0, width - 1, width - 1]
    y = [(height - 1) / 2, 0, height - 1, 0, height - 1]
    sky = first.pixel_to_world(x, y)
    assert np.all(sky.separation(second.pixel_to_world(x, y)).deg <= 1e-9)


def test_refined_cli_reuses_masked_wcs_sidecar(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = write_panels(tmp_path)
    middle = fixture.paths[1]
    originals = {path: path.read_bytes() for path in (*fixture.paths, fixture.mask)}
    sidecar = tmp_path / "middle.wcs.json"
    assert main(["solve", str(middle), "--sky-mask", str(fixture.mask), "-o", str(sidecar)]) == 0
    assert json.loads(capsys.readouterr().out)["stage"] == "existing-wcs"
    with open_panel(middle, sky_mask=fixture.mask) as source:
        geometry, _ = load_solution(sidecar, source)
        _assert_matching_wcs(
            WCS(source.header), geometry.wcs, source.descriptor.width, source.descriptor.height
        )

    arguments = [
        "mosaic",
        *map(str, fixture.paths),
        "--sky-mask",
        f"2={fixture.mask}",
        "--center",
        *map(str, CENTER),
        "--size",
        *map(str, SIZE),
        "--scale",
        str(ARCSEC),
        "--refine",
        "--background",
        "plane",
        "--tile-size",
        "37",
    ]
    embedded = tmp_path / "embedded.fits"
    reused = tmp_path / "reused.fits"
    assert main([*arguments, "-o", str(embedded)]) == 0
    assert json.loads(capsys.readouterr().out)["refinement"]["status"] == "ready"
    assert main([*arguments, "--wcs", f"2={sidecar}", "-o", str(reused)]) == 0
    assert json.loads(capsys.readouterr().out)["refinement"]["status"] == "ready"

    with fitsio.FITS(embedded) as expected, fitsio.FITS(reused) as actual:
        pixels = actual[0].read()
        coverage = actual["COVERAGE"].read()
        np.testing.assert_array_equal(coverage, expected["COVERAGE"].read())
        np.testing.assert_array_equal(coverage, np.isfinite(pixels))
        np.testing.assert_allclose(pixels, expected[0].read(), rtol=0, atol=2e-6, equal_nan=True)
        assert coverage[133, 180] == 0 and coverage[60, 180] == 1

    header = fits.getheader(reused)
    assert "existing-wcs WCS sidecar" in str(header["HISTORY"])
    _assert_matching_wcs(WCS(fits.getheader(embedded)), WCS(header), *SIZE)
    assert {path: path.read_bytes() for path in originals} == originals


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
