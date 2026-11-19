"""Phase 6D regressions on the frozen PA4 observations and source-bound WCS."""

import warnings
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import tifffile
from astropy import units as u
from astropy.coordinates import ICRS, SkyCoord
from astropy.wcs import SingularMatrixError

from astromosaic.astrometry.solve import load_solution
from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.geometry import PanelGeometry, TileSky
from astromosaic.geometry.footprint import zea_footprint
from astromosaic.pipeline import mosaic
from astromosaic.storage.project import (
    MosaicProject,
    load_project,
    open_project_sky_panel,
    render_project,
)

_PA4 = (
    Path(__file__).resolve().parents[2] / "data/application-tests/owner01-pa4/project.astromosaic"
)
_WARNING_TILE = Region(0, 0, 128, 128)


@pytest.fixture
def pa4_project() -> MosaicProject:
    if not _PA4.is_file():
        pytest.skip("Prepare the Phase 6 PA4 observational reference in docs/phase-6.md.")
    project = load_project(_PA4)
    assert project.sky_indices() == tuple(range(8, 23))
    assert project.render.projection == "ZEA" and project.render.size == (2097, 2071)
    return project


@pytest.fixture
def pa4_10_geometry(pa4_project: MosaicProject) -> PanelGeometry:
    panel = pa4_project.panels[9]
    assert panel.wcs_sidecar is not None
    with open_project_sky_panel(
        panel, pa4_project.render.max_working_bytes, JobContext()
    ) as source:
        geometry, _ = load_solution(panel.wcs_sidecar.path, source)
    assert tuple(geometry.wcs.wcs.ctype) == ("RA---TAN-SIP", "DEC--TAN-SIP")
    return geometry


def test_real_pa4_projection_rejects_whole_and_mixed_batches(
    pa4_project: MosaicProject, pa4_10_geometry: PanelGeometry
) -> None:
    output = PanelGeometry(pa4_project.render.output_wcs(), ICRS())
    source = pa4_10_geometry
    tile = TileSky.from_output(output, _WARNING_TILE)
    world = np.column_stack((tile.sky.ra.deg, tile.sky.dec.deg))
    assert np.isfinite(world).all()
    assert np.isnan(source.wcs.wcs_world2pix(world, 0)).all()
    pointing = SkyCoord(*source.wcs.wcs.crval, unit="deg", frame="icrs")
    assert np.all(tile.sky.separation(pointing).deg > 90)

    # Project independently chosen subpixel locations in the observed PA4-10 detector.
    detector = np.array([[2999.25, 1999.5], [0.125, 1800.5], [5998.75, 2190.25]])
    supported = output.wcs.wcs_world2pix(source.wcs.all_pix2world(detector, 0), 0)
    center = output.wcs.wcs.crpix - 1
    radius = 2 / np.deg2rad(pa4_project.render.scale_arcsec / 3600)
    beyond_disk = center + np.array([radius + 1, 0])
    positions = np.vstack((supported, np.column_stack((tile.x, tile.y)), beyond_disk))
    mixed = TileSky.from_pixels(output, *positions.T)
    assert np.isnan(mixed.sky.dec.deg[-1])
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        for rejected in (tile, TileSky.from_pixels(output, *np.atleast_2d(beyond_disk).T)):
            x, y, usable = rejected.in_panel(source)
            assert np.isnan(x).all() and np.isnan(y).all() and not usable.any()
        x, y, usable = mixed.in_panel(source)

    np.testing.assert_allclose(
        np.column_stack((x, y))[: len(detector)], detector, atol=1e-7, rtol=0
    )
    assert usable[: len(detector)].all() and not usable[len(detector) :].any()
    assert np.isnan(x[len(detector) :]).all() and np.isnan(y[len(detector) :]).all()


def test_real_pa4_inverse_propagates_invalid_wcs(pa4_10_geometry: PanelGeometry) -> None:
    source = pa4_10_geometry
    sky = source.wcs.pixel_to_world(3000.0, 2000.0)
    damaged = source.wcs.deepcopy()
    damaged.wcs.pc = np.zeros((2, 2))
    with pytest.raises(SingularMatrixError):
        PanelGeometry(damaged, source.frame).inverse(sky)


def test_real_pa4_zea_bounds_keep_supported_samples_and_fall_back_near_rim(
    pa4_project: MosaicProject, pa4_10_geometry: PanelGeometry
) -> None:
    source = pa4_10_geometry
    render = replace(pa4_project.render, crop=Region(350, 40, 1560, 1320), rotation_deg=31.0)
    target = PanelGeometry(render.output_wcs(), ICRS())
    crop = render.output_region()
    shift = (18.25, -13.75)
    bounds = zea_footprint(source, target, (6000, 4000), (crop.width, crop.height), shift)
    assert bounds is not None

    x, y = np.meshgrid(np.linspace(-0.5, 5999.5, 93), np.linspace(-0.5, 3999.5, 61))
    world = source.wcs.all_pix2world(np.column_stack((x.ravel(), y.ravel())), 0)
    projected = target.wcs.wcs_world2pix(world, 0) + shift
    assert np.all((bounds.left <= projected[:, 0]) & (projected[:, 0] <= bounds.right))
    assert np.all((bounds.top <= projected[:, 1]) & (projected[:, 1] <= bounds.bottom))

    pointing = source.wcs.pixel_to_world(3000.0, 2000.0)
    pole = pointing.directional_offset_by(90 * u.deg, 174 * u.deg)
    near_rim = replace(render, center=(pole.ra.deg, pole.dec.deg), size=(3661, 3661), crop=None)
    target = PanelGeometry(near_rim.output_wcs(), ICRS())
    edge = target.wcs.wcs_world2pix([[pointing.ra.deg, pointing.dec.deg]], 0)[0]
    assert zea_footprint(source, target, (6000, 4000), near_rim.size, (0.0, 0.0)) is None
    core = TileSky.from_pixels(target, *np.atleast_2d(edge).T)
    x, y, usable = core.in_panel(source)
    assert usable.item()
    np.testing.assert_allclose([x.item(), y.item()], [3000, 2000], atol=1e-7, rtol=0)


def test_real_pa4_cropped_render_matches_all_panels(
    pa4_project: MosaicProject, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = replace(pa4_project, render=replace(pa4_project.render, crop=Region(0, 0, 384, 384)))
    selected = tmp_path / "selected.tiff"
    all_panels = tmp_path / "all-panels.tiff"
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        optimized = render_project(project, selected, JobContext())
        monkeypatch.setattr(mosaic, "zea_footprint", lambda *_args: None)
        reference = render_project(project, all_panels, JobContext())

    assert optimized.covered_pixels == reference.covered_pixels == 4869
    assert optimized.rejected_coordinates < reference.rejected_coordinates
    with tifffile.TiffFile(selected) as actual, tifffile.TiffFile(all_panels) as expected:
        actual_page, expected_page = actual.pages[0], expected.pages[0]
        assert isinstance(actual_page, tifffile.TiffPage)
        assert isinstance(expected_page, tifffile.TiffPage)
        assert actual_page.description == expected_page.description
        assert actual_page.asarray().tobytes() == expected_page.asarray().tobytes()
        assert actual_page.pages is not None and expected_page.pages is not None
        assert (
            actual_page.pages[0].asarray().tobytes() == expected_page.pages[0].asarray().tobytes()
        )
