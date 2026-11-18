import json
from pathlib import Path

import fitsio
import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS, Sip

from astromosaic.astrometry.astap_catalog import CatalogStar
from astromosaic.astrometry.distortion import validate_models
from astromosaic.astrometry.solve import SolveResult, write_solution
from astromosaic.astrometry.solve_validation import (
    Associations,
    QualityRejected,
    associate,
    require_quality,
)
from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.geometry import read_panel_geometry, tan_output_wcs
from astromosaic.io import open_panel
from astromosaic.pipeline.mosaic import RenderSpec, preview_mosaic, render_mosaic

RECIPE = json.loads(
    (Path(__file__).parents[1] / "fixtures/plate_solve_v36.json").read_text("utf-8")
)["synthetic_recipes"]
SIZE = (1024, 768)


@pytest.mark.parametrize("scale", RECIPE["quality_boundary_scales_arcsec_px"])
def test_common_quality_boundary_rejects_invalid_or_too_few_matches(scale: float) -> None:
    limit = max(3, 2 * scale)
    for count in (15, 16):
        assert require_quality(count, limit, (scale, scale * 3)) == limit
        assert require_quality(count, np.nextafter(limit, 0), (scale, scale * 3)) == limit
    for invalid in (np.nextafter(limit, np.inf), -0.1, np.nan, np.inf):
        with pytest.raises(QualityRejected):
            require_quality(15, invalid, (scale, scale * 3))
    with pytest.raises(QualityRejected):
        require_quality(14, 0, (scale, scale))


@pytest.mark.parametrize(
    ("order", "amount", "skew", "mirrored"),
    [
        (0, 0, 0.0, False),
        (0, 0, 1.5, False),
        (2, 1, 0.0, False),
        (2, 3, 0.0, True),
        (3, 3, 0.0, False),
        (3, 8, 0.0, True),
    ],
)
def test_frozen_sip_truth_and_skew_at_ra_wrap(
    order: int,
    amount: float,
    skew: float,
    mirrored: bool,
) -> None:
    rng = np.random.default_rng(RECIPE["seed"])
    wcs = tan_output_wcs(
        tuple(RECIPE["center_deg"]),
        SIZE,
        RECIPE["scale_arcsec_px"],
        RECIPE["rotation_deg"],
        Region(0, 0, *SIZE),
    )
    matrix = wcs.pixel_scale_matrix.copy()
    angle = np.radians(skew)
    matrix[:, 1] = np.cos(angle) * matrix[:, 1] - np.sin(angle) * matrix[:, 0]
    if mirrored:
        matrix[:, 0] *= -1
    wcs.wcs.cdelt = (1, 1)
    wcs.wcs.pc = matrix
    if order:
        a, b = np.zeros((order + 1, order + 1)), np.zeros((order + 1, order + 1))
        a[order, 0] = amount / (np.sqrt(2) * 511.5**order)
        b[0, order] = -amount / (np.sqrt(2) * 383.5**order)
        wcs.wcs.ctype = ("RA---TAN-SIP", "DEC--TAN-SIP")
        wcs.sip = Sip(a, b, None, None, wcs.wcs.crpix)
    truth = read_panel_geometry(wcs.to_header(relax=True), *SIZE)
    x, y = np.meshgrid(np.linspace(20, SIZE[0] - 21, 20), np.linspace(20, SIZE[1] - 21, 15))
    xy = np.column_stack((x.ravel(), y.ravel()))
    xy += rng.uniform(-0.2, 0.2, xy.shape)
    measured = xy + rng.normal(0, 0.05, xy.shape)
    coordinates = truth.forward(*xy.T)
    assert min(coordinates.ra.deg) < 1 < max(coordinates.ra.deg)
    model, report = validate_models(
        truth,
        SIZE,
        Associations(measured, coordinates, 0, len(xy)),
        JobContext(),
        strict_edges=True,
    )
    assert report["model"] == (f"SIP-{order}" if order else "TAN")
    assert report["held_out_matches"] == 60
    assert float(str(report["held_out_p95_source_px"])) < 0.5
    assert float(str(report["held_out_outer_p95_source_px"])) < 0.5
    gx, gy = np.meshgrid(np.linspace(0, SIZE[0] - 1, 9), np.linspace(0, SIZE[1] - 1, 9))
    grid = np.column_stack((gx.ravel(), gy.ravel()))
    assert np.max(np.linalg.norm(truth.inverse(model.forward(*grid.T)) - grid, axis=1)) < 1
    diagnostics = report["field_geometry"]
    assert isinstance(diagnostics, dict) and len(diagnostics["model_grid"]) == 81
    assert diagnostics["parity"] == (1 if mirrored else -1)
    assert diagnostics["linear_skew_deg"] == pytest.approx(skew, abs=0.03)
    assert diagnostics["maximum_model_displacement_source_px"] == pytest.approx(amount, abs=0.12)


def test_center_only_evidence_preserves_unsupported_edges() -> None:
    wcs = tan_output_wcs((359.999, 20), SIZE, 2, 15, Region(0, 0, *SIZE))
    geometry = read_panel_geometry(wcs.to_header(), *SIZE)
    xy = np.random.default_rng(360601).uniform(0.35, 0.65, (120, 2)) * SIZE
    pairs = Associations(xy, geometry.forward(*xy.T), 0, len(xy))
    _, report = validate_models(geometry, SIZE, pairs, JobContext())
    assert report["model"] == "TAN" and report["edge_status"] == "insufficient"
    assert report["held_out_outer_p95_source_px"] is None
    regions = report["measured_regions"]
    assert isinstance(regions, list)
    assert regions[0]["matches"] == 0 and regions[0]["p95_source_px"] is None
    with pytest.raises(QualityRejected, match="field-edge"):
        validate_models(geometry, SIZE, pairs, JobContext(), strict_edges=True)


def test_independent_catalog_associations_reject_duplicates_and_unrelated_stars() -> None:
    size = (256, 256)
    wcs = tan_output_wcs((359.999, 20), size, 2, 15, Region(0, 0, *size))
    geometry = read_panel_geometry(wcs.to_header(), *size)
    rng = np.random.default_rng(360601)
    points = rng.uniform(20, 235, (20, 2))
    sky = geometry.forward(*points.T)
    unique = [
        CatalogStar(str(i), ra, dec, 12)
        for i, (ra, dec) in enumerate(zip(sky.ra.deg, sky.dec.deg, strict=True))
    ]
    duplicates = unique + [
        CatalogStar("copy" + s.identifier, s.ra_deg, s.dec_deg, 12) for s in unique
    ]
    assert len(associate(geometry, size, points, lambda *_: duplicates, JobContext()).xy) == 20
    unrelated = geometry.forward(*rng.uniform(5, 250, (450, 2)).T)
    dense = [
        CatalogStar(str(i), ra, dec, 12)
        for i, (ra, dec) in enumerate(zip(unrelated.ra.deg, unrelated.dec.deg, strict=True))
    ]
    with pytest.raises(QualityRejected, match="shifted control"):
        associate(geometry, size, rng.uniform(5, 250, (450, 2)), lambda *_: dense, JobContext())


def test_saved_sip_drives_the_same_original_samples_in_preview_and_export(tmp_path: Path) -> None:
    size = (68, 49)
    spec = RenderSpec((359.999, 20), size, 3.0, tile_size=13)
    wcs = tan_output_wcs(spec.center, size, 3, 0, Region(0, 0, *size))
    a, b = np.zeros((4, 4)), np.zeros((4, 4))
    a[3, 0], b[0, 3] = 4e-5, -5e-5
    wcs.wcs.ctype = ("RA---TAN-SIP", "DEC--TAN-SIP")
    wcs.sip = Sip(a, b, None, None, wcs.wcs.crpix)
    geometry = read_panel_geometry(wcs.to_header(relax=True), *size)
    y, x = np.indices(size[::-1], dtype=np.float64)
    source = tmp_path / "uncorrected.fits"
    ramp = (0.75 * x + 1.5 * y - 40).astype(np.float32)
    fits.writeto(source, ramp, fits.Header({"BUNIT": "MJy/sr", "FILTER": "L"}))
    sidecar = tmp_path / "sip.wcs.json"
    with open_panel(source) as panel:
        write_solution(sidecar, panel, SolveResult(geometry, "gaia-dr3", ()))
    export = tmp_path / "export.fits"
    preview = preview_mosaic([source], spec, wcs_sidecars={0: sidecar})
    render_mosaic([source], export, spec, wcs_sidecars={0: sidecar})
    with fitsio.FITS(export) as output:
        samples, mask = output[0].read(), output["COVERAGE"].read() != 0
        np.testing.assert_array_equal(preview.tile.pixels, samples)
        np.testing.assert_array_equal(preview.tile.valid, mask)
    sky = WCS(fits.getheader(export)).all_pix2world(x[mask], y[mask], 0)
    sx, sy = wcs.all_world2pix(*sky, 0, tolerance=1e-9, maxiter=100)
    expected = 0.75 * sx + 1.5 * sy - 40
    np.testing.assert_allclose(samples[mask], expected, rtol=0, atol=1e-4)
    with fitsio.FITS(source) as original:
        np.testing.assert_array_equal(original[0].read(), ramp)
