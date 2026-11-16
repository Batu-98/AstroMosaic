from dataclasses import replace
from pathlib import Path
from threading import Event

import fitsio
import numpy as np
import pytest
import tifffile
from astropy.io import fits
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter

from astromosaic.core import Region, Tile
from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.core.masks import FOREGROUND, SKY, UNCLASSIFIED, SourceMask, bounded_grid
from astromosaic.geometry import tan_output_wcs
from astromosaic.geometry.image import LayerPlacement
from astromosaic.io import open_panel
from astromosaic.pipeline.layers import _blend
from astromosaic.pipeline.mosaic import RenderSpec, _RenderedTile
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    align_project_foreground,
    load_project,
    preview_project_layer,
    propose_project_composition,
    render_project_layer,
    save_project,
)


def _write_scene(
    directory: Path,
    size: tuple[int, int],
    shift: tuple[int, int],
    *,
    rgb: bool = False,
) -> tuple[MosaicProject, NDArray[np.float32]]:
    width, height = size
    dx, dy = shift
    gen = np.random.default_rng(271)
    noise = gen.normal(size=(height + dy, width + dx)).astype(np.float32)
    scene = gaussian_filter(noise, sigma=1.45).astype(np.float32)
    spec = RenderSpec((359.999, 25), size, 2.0, tile_size=24)
    panels = []
    for i, (x, y) in enumerate(((0, 0), (dx, dy))):
        grid_x, grid_y = bounded_grid(size, 384)
        rows = y + (np.arange(grid_y) * height // grid_y)[:, None]
        cols = x + np.arange(grid_x) * width // grid_x
        horizon = height // 2 + (cols // 9) % 5 - 2
        labels = np.where(
            rows < horizon - 1, SKY, np.where(rows >= horizon + 1, FOREGROUND, UNCLASSIFIED)
        )
        mask = SourceMask(size, labels.astype(np.uint8).tobytes())
        data = scene[y : y + height, x : x + width].copy()
        sky = mask.read_labels(Region(0, 0, width, height)) == SKY
        data[sky] = 4 + (i + 1) * gen.normal(size=int(sky.sum())).astype(np.float32)
        data[2, 3] = np.nan
        header = (
            tan_output_wcs(
                spec.center, size, spec.scale_arcsec, 0, spec.output_region()
            ).to_header()
            if i == 0
            else fits.Header()
        )
        header["FILTER"], header["BUNIT"] = "L", "MJy/sr"
        path = directory / f"panel-{i + 1}{'.tif' if rgb else '.fits'}"
        if rgb:
            tifffile.imwrite(
                path,
                np.stack([data, data * 2, data * 3], axis=-1),
                photometric="rgb",
                metadata=None,
                description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False),
            )
        else:
            fits.writeto(path, data, header)
        panels.append(
            ProjectPanel(FileReference.capture(path), source_mask=mask, include_sky=i == 0)
        )
    return MosaicProject(tuple(panels), render=spec), scene


@pytest.mark.parametrize("rgb", [False, True], ids=["fits", "rgb-tiff"])
def test_layer_exports_and_composition_roundtrip(tmp_path: Path, rgb: bool) -> None:
    project, truth = _write_scene(tmp_path, (96, 72), (35, 5), rgb=rgb)
    original = [panel.source.path.read_bytes() for panel in project.panels]
    context = JobContext()
    project = align_project_foreground(project, context)
    alignment = project.current_foreground()
    assert alignment is not None
    assert alignment.panels[1].shift == (35.0, 5.0)
    assert alignment.overlaps[0].correlation == pytest.approx(1.0, abs=1e-6)
    foreground = preview_project_layer(project, "foreground", context)
    assert foreground.output_wcs is None
    cropped = truth[alignment.canvas.slices]
    expected = np.stack((cropped, cropped * 2, cropped * 3), axis=-1) if rgb else cropped
    np.testing.assert_array_equal(
        foreground.tile.pixels[foreground.tile.valid], expected[foreground.tile.valid]
    )

    ext = ".tiff" if rgb else ".fits"
    for layer in ("foreground", "sky"):
        path = tmp_path / (layer + ext)
        render_project_layer(project, layer, path, context)
        with open_panel(path) as source:
            assert (source.descriptor.wcs_provenance is not None) == (layer == "sky")
    sky = preview_project_layer(project, "sky", context)

    proposal = propose_project_composition(project, context)
    assert proposal.reference_panel == 0
    assert proposal.placement_rms_px is not None and proposal.placement_rms_px < 1e-7
    np.testing.assert_allclose(
        proposal.placement.offset, (alignment.canvas.x, alignment.canvas.y), rtol=0, atol=1e-7
    )
    settings = replace(
        proposal,
        placement=LayerPlacement((4.0, alignment.canvas.y - 10.0), -2.0, 1.04),
        seam_y=33.0,
        overlap_percent=28.0,
        sky_crop_bottom=35,
        reference_panel=None,
        placement_rms_px=None,
    )
    project = replace(project, composition=settings)
    manifest = tmp_path / "composition.astromosaic"
    save_project(manifest, project)
    reopened = load_project(manifest)
    assert reopened == project
    frame = preview_project_layer(reopened, "composition", context)
    assert frame.seam_width == pytest.approx(37 * 0.28)
    assert frame.common_coverage is not None and frame.common_coverage.any()
    np.testing.assert_array_equal(
        preview_project_layer(reopened, "sky", context).tile.pixels, sky.tile.pixels
    )
    path = tmp_path / ("composite" + ext)
    summary = render_project_layer(reopened, "composition", path, context)
    assert summary.common_pixels == int(frame.common_coverage.sum())
    if rgb:
        with tifffile.TiffFile(path) as tiff:
            page = tiff.pages[0]
            assert isinstance(page, tifffile.TiffPage)
            assert page.description.startswith("AstroMosaic TIFF 2\n")
            np.testing.assert_array_equal(frame.tile.pixels, page.asarray())
            pages = page.pages
            assert pages is not None
            coverage, layers = pages[0].asarray(), pages[1].asarray()
    else:
        with fitsio.FITS(path) as hdus:
            np.testing.assert_array_equal(frame.tile.pixels, hdus[0].read())
            coverage, layers = hdus["COVERAGE"].read(), hdus["LAYERS"].read()
    assert set(np.unique(layers)) == {0, 1, 2, 3}
    assert np.all(frame.common_coverage[layers == 3])
    np.testing.assert_array_equal(layers > 0, coverage)
    np.testing.assert_array_equal(frame.tile.valid, coverage)
    with open_panel(path) as source:
        assert source.descriptor.wcs_provenance is None
        np.testing.assert_array_equal(source.read_tile(frame.tile.region).valid, coverage)
    assert [panel.source.path.read_bytes() for panel in project.panels] == original


def test_foreground_native_match_and_cancelled_composition(tmp_path: Path) -> None:
    project, _ = _write_scene(tmp_path, (448, 310), (159, 7))
    project = align_project_foreground(project, JobContext())
    alignment = project.current_foreground()
    assert alignment is not None and alignment.panels[1].shift == (159.0, 7.0)
    assert alignment.overlaps[0].patches >= 2

    proposed = propose_project_composition(project, JobContext())
    setting = replace(proposed, placement=LayerPlacement((0, 322)), seam_y=317.0)
    project = replace(project, composition=setting)
    frame = preview_project_layer(project, "composition", JobContext())
    assert frame.common_coverage is not None and not frame.common_coverage.any()
    assert not frame.tile.valid[int(315 * frame.tile.region.height / frame.output_size[1])].any()

    cancelled = Event()
    out = tmp_path / "cancelled.fits"
    with pytest.raises(MosaicCancelled):
        render_project_layer(
            project, "composition", out, JobContext(cancelled.is_set, lambda *_: cancelled.set())
        )
    assert not out.exists() and not list(tmp_path.glob("*.part"))


def test_foreground_reports_weak_and_mismatched_panels(tmp_path: Path) -> None:
    project, _ = _write_scene(tmp_path, (96, 72), (35, 5))
    first, second = project.panels
    blank = tmp_path / "flat.fits"
    fits.writeto(blank, np.ones((72, 96), dtype=np.float32))
    with pytest.raises(ValueError, match="Weak or disconnected.*1 \\| 2"):
        align_project_foreground(
            replace(project, panels=(first, replace(second, source=FileReference.capture(blank)))),
            JobContext(),
        )
    smaller = tmp_path / "smaller.fits"
    fits.writeto(smaller, np.ones((70, 96), dtype=np.float32))
    mask = SourceMask((96, 70), bytes((FOREGROUND,)) * (96 * 70))
    with pytest.raises(ValueError, match="matching source dimensions"):
        align_project_foreground(
            replace(
                project,
                panels=(
                    first,
                    replace(second, source=FileReference.capture(smaller), source_mask=mask),
                ),
            ),
            JobContext(),
        )
    with pytest.raises(ValueError, match="working budget"):
        align_project_foreground(
            replace(project, render=replace(project.render, max_working_bytes=512)), JobContext()
        )

    sky_mask = SourceMask((96, 72), bytes((SKY,)) * (96 * 72))
    no_shared = align_project_foreground(
        replace(project, panels=(replace(first, source_mask=sky_mask), second)), JobContext()
    )
    with pytest.raises(ValueError, match="shared horizon"):
        propose_project_composition(no_shared, JobContext())


def test_seam_only_feathers_valid_common_samples() -> None:
    region = Region(0, 0, 4, 3)
    slots = np.broadcast_to(np.arange(4), (3, 4))
    sky_valid = (slots == 0) | (slots == 2)
    ground_valid = (slots == 1) | (slots == 2)
    sky = _RenderedTile(
        Tile(region, np.where(sky_valid, -2, np.nan).astype(np.float32), sky_valid), 0
    )
    ground = _RenderedTile(
        Tile(region, np.where(ground_valid, 8, np.nan).astype(np.float32), ground_valid), 0
    )
    rows = np.broadcast_to(np.arange(3, dtype=np.float64)[:, None], (3, 4))
    result = _blend(sky, ground, rows, 1.0, 2.0)
    np.testing.assert_array_equal(
        result.tile.pixels, [[-2, 8, -2, np.nan], [-2, 8, 3, np.nan], [-2, 8, 8, np.nan]]
    )
    np.testing.assert_array_equal(result.contributions, [[1, 2, 1, 0], [1, 2, 3, 0], [1, 2, 2, 0]])
    np.testing.assert_array_equal(result.common_coverage, slots == 2)
