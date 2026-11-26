import json
from dataclasses import replace
from pathlib import Path
from threading import Event

import fitsio
import numpy as np
import pytest
import tifffile
from astropy.io import fits
from astropy.wcs import WCS
from numpy.typing import NDArray
from xisf_reference import read_xisf_attachments

from astromosaic.core import Region
from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.io import open_panel
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.pipeline.refinement import RefinementSpec
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    load_project,
    preview_project,
    project_sky_bands,
    render_project,
    render_project_layer,
    save_project,
    validate_project_sky,
)


def _fixture(
    tmp_path: Path,
) -> tuple[MosaicProject, NDArray[np.float32], NDArray[np.float32]]:
    spec = RenderSpec(
        (359.999, 20.0), (18, 14), 7.2, 11.0, Region(3, 2, 11, 9), tile_size=4, projection="ZEA"
    )
    header = replace(spec, crop=None).output_wcs().to_header()
    first, color, second, excluded, mask_path = (
        tmp_path / name
        for name in ("Ha 1.fits", "O III.tiff", "Ha 2.fits", "Ground.fits", "sky.fits")
    )
    y, x = np.indices((14, 18), dtype=np.float32)
    ha = x - y
    first_ha = ha.copy()
    first_ha[4, 5] = np.nan
    second_ha = 2 * ha
    sky_mask = np.ones(ha.shape, dtype=np.uint8)
    sky_mask[4, 5:7] = 0
    fits.writeto(mask_path, sky_mask)

    header["BUNIT"], header["FILTER"] = "MJy/sr", "H-alpha"
    fits.writeto(first, first_ha, header)
    del header["FILTER"]
    fits.writeto(second, second_ha, header)
    fits.writeto(excluded, ha, header)

    rgb = np.stack((ha, -2 * ha, 3 * ha), axis=-1)
    rgb[3, 7, 1] = np.nan
    header["BUNIT"] = "Jy/sr"
    tifffile.imwrite(
        color,
        rgb,
        photometric="rgb",
        metadata=None,
        description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False),
    )

    project = MosaicProject(
        (
            ProjectPanel(FileReference.capture(first)),
            ProjectPanel(FileReference.capture(color), band_override="O III"),
            ProjectPanel(
                FileReference.capture(second), weight=3.0, sky_mask=FileReference.capture(mask_path)
            ),
            ProjectPanel(FileReference.capture(excluded), include_sky=False),
        ),
        spec,
        filter_name="H-alpha",
    )
    expected = 1.75 * ha
    expected[4, 5], expected[4, 6] = np.nan, first_ha[4, 6]
    rgb[3, 7] = np.nan
    crop = spec.output_region().slices
    return project, expected[crop], rgb[crop]


def test_bands_preserve_independent_values_and_wcs(tmp_path: Path) -> None:
    project, expected_ha, expected_rgb = _fixture(tmp_path)
    sources = {ref.path for panel in project.panels for _, ref in panel.references()}
    originals = {path: path.read_bytes() for path in sources}
    manifest = tmp_path / "Saved field.astromosaic"
    save_project(manifest, project)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["version"] == 6 and data["panels"][1]["band_override"] == "O III"
    reopened = load_project(manifest)
    assert reopened == project
    context = JobContext()
    assert project_sky_bands(reopened, context) == {"H-alpha": [0, 2], "O III": [1]}
    points = ([0, 5, 10], [0, 4, 8])
    target = reopened.render.output_wcs().pixel_to_world_values(*points)
    assert reopened.render.projection == "ZEA"

    for band, unit, suffix, expected in (
        ("H-alpha", "MJy/sr", ".fits", expected_ha),
        ("O III", "Jy/sr", ".tiff", expected_rgb),
        ("O III", "Jy/sr", ".xisf", expected_rgb),
    ):
        valid = np.isfinite(expected)
        if expected.ndim == 3:
            valid = valid.all(axis=-1)
        preview = preview_project(reopened, context, band=band)
        np.testing.assert_array_equal(preview.tile.pixels, expected)
        np.testing.assert_array_equal(preview.tile.valid, valid)
        output = tmp_path / f"{band} mosaic{suffix}"
        summary = render_project(reopened, output, context, band=band)
        assert summary.covered_pixels == int(valid.sum())
        assert summary.peak_reserved_bytes <= reopened.render.max_working_bytes
        assert summary.panels == (2 if band == "H-alpha" else 1)
        if suffix == ".fits":
            with fitsio.FITS(output) as hdus:
                pixels, coverage = hdus[0].read(), hdus["COVERAGE"].read()
        elif suffix == ".tiff":
            with tifffile.TiffFile(output) as tiff:
                page = tiff.pages[0]
                assert isinstance(page, tifffile.TiffPage) and page.pages is not None
                pixels, coverage = page.asarray(), page.pages[0].asarray()
        else:
            (pixels, coverage), _ = read_xisf_attachments(output)
        np.testing.assert_array_equal(pixels, expected)
        np.testing.assert_array_equal(coverage, valid)
        assert pixels.dtype.kind == "f" and pixels.dtype.itemsize == 4
        with open_panel(output) as source:
            header = source.header
        assert header["FILTER"] == band and header["BUNIT"] == unit
        assert header["CTYPE1"] == "RA---ZEA"
        np.testing.assert_allclose(
            WCS(header).pixel_to_world_values(*points), target, atol=1e-9, rtol=0
        )
        if band == "O III":
            assert any("FILTER (missing) assigned as O III" in line for line in header["HISTORY"])
    assert np.nanmin(expected_ha) < 0 and np.nanmax(expected_ha) > 1
    assert np.any(expected_ha == 0) and np.any(
        np.isfinite(expected_ha) != np.isfinite(expected_rgb).all(axis=-1)
    )
    assert all(path.read_bytes() == data for path, data in originals.items())

    data["version"] = 5
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="require project manifest version 6"):
        load_project(manifest)


def test_unlabeled_panel_has_a_separate_selectable_band(tmp_path: Path) -> None:
    project, _, _ = _fixture(tmp_path)
    project = replace(project, filter_name=None)
    context = JobContext()
    assert project_sky_bands(project, context) == {"H-alpha": [0], "O III": [1], "Unspecified": [2]}
    assert validate_project_sky(project, context, band="Unspecified").panels == 1

    preview = preview_project(project, context, band="Unspecified")
    with fits.open(project.panels[2].source.path) as source:
        expected = source[0].data[project.render.output_region().slices].copy()
    expected[2, 2:4] = np.nan
    np.testing.assert_array_equal(preview.tile.pixels, expected)
    output = tmp_path / "Unspecified.fits"
    assert render_project(project, output, context, band="Unspecified").panels == 1
    assert fits.getheader(output)["FILTER"] == "Unspecified"


def test_band_preflight_reports_bad_membership_units_and_layout(tmp_path: Path) -> None:
    project, _, _ = _fixture(tmp_path)
    context = JobContext()
    with pytest.raises(ValueError, match="Unknown sky band.*H-alpha, O III"):
        validate_project_sky(project, context, band="h-alpha")
    with pytest.raises(ValueError, match="RGB mosaics require"):
        validate_project_sky(project, context, tmp_path / "rgb.fits", band="O III")
    refined = replace(project, refinement=RefinementSpec())
    with pytest.raises(ValueError, match="Relative refinement currently requires mono panels"):
        validate_project_sky(refined, context, band="O III")
    mono = replace(refined, panels=refined.panels[:1])
    with pytest.raises(ValueError, match="Relative refinement requires at least two panels"):
        validate_project_sky(mono, context, band="H-alpha")
    with pytest.raises(ValueError, match="requires the sky layer"):
        render_project_layer(project, "composition", tmp_path / "bad.tiff", context, band="O III")
    mixed = replace(project.panels[1], band_override="H-alpha")
    with pytest.raises(ValueError, match="either all mono or all RGB"):
        validate_project_sky(
            replace(project, panels=(project.panels[0], mixed)), context, band="H-alpha"
        )

    faulty = tmp_path / "wrong-scale.fits"
    with fits.open(project.panels[0].source.path) as original:
        header = original[0].header
        header["BUNIT"] = "Jy/sr"
        fits.writeto(faulty, original[0].data, header)
    mismatch = replace(
        project, panels=(*project.panels, ProjectPanel(FileReference.capture(faulty)))
    )
    with pytest.raises(ValueError, match="same brightness scale"):
        validate_project_sky(mismatch, context, band="H-alpha")
    assert validate_project_sky(mismatch, context, band="O III").channels == 3
    assert not (tmp_path / "bad.tiff").exists()


def test_selected_band_cancellation_cleans_up_and_retries(tmp_path: Path) -> None:
    project, _, _ = _fixture(tmp_path)
    destination = tmp_path / "selected.fits"
    cancel = Event()

    def report(done: int, total: int) -> None:
        assert 0 < done < total
        assert not destination.exists() and list(tmp_path.glob("*.part"))
        cancel.set()

    with pytest.raises(MosaicCancelled):
        render_project(project, destination, JobContext(cancel.is_set, report), band="H-alpha")
    assert not destination.exists() and not list(tmp_path.glob("*.part"))
    assert render_project(project, destination, JobContext(), band="H-alpha").panels == 2
    with pytest.raises(FileExistsError):
        render_project(project, destination, JobContext(), band="H-alpha")
