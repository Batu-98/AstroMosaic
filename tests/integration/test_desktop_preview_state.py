from dataclasses import replace

import numpy as np

from astromosaic.core import Region
from astromosaic.display import DisplayFrame
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.storage.project import MosaicProject
from astromosaic.ui.preview_state import PreviewResult, PreviewSelection, PreviewState


def _photo_frame(grid: RenderSpec) -> DisplayFrame:
    region = grid.output_region()
    return DisplayFrame(
        (region.width, region.height),
        np.ones((2, 2, 4), dtype=np.float32),
        has_coverage=True,
        photo_levels=(0.0, 1.0),
        tone_levels=(0.0, 1.0),
    )


def test_only_current_request_can_publish_after_returning_to_the_same_band() -> None:
    project = MosaicProject(render=RenderSpec((32.0, 10.0), (24, 18), 7.2))
    red = PreviewSelection(project, "sky", "R")
    green = replace(red, band="G")
    result = PreviewResult(_photo_frame(project.render), visual_only=True)
    state = PreviewState()
    first = state.start(red)
    assert state.show_proxy(first, red, result.frame)
    assert state.frame is result.frame and state.photo_overview(red) is None
    assert state.is_stale(green, linked=True)
    assert not state.show_proxy(first, green, result.frame)

    state.start(green)
    newest = state.start(red)
    assert not state.show_proxy(first, red, result.frame)
    assert state.complete(first, red, result) is None
    overview = state.complete(newest, red, result)
    assert overview is not None and state.photo_overview(red) is overview
    assert state.current(green) is None


def test_crop_uses_full_grid_and_restores_photo_overview_with_new_identity() -> None:
    grid = RenderSpec((32.0, 10.0), (24, 18), 7.2)
    fitted = replace(grid, size=(40, 36), crop=Region(2, 3, 30, 28))
    selection = PreviewSelection(MosaicProject(render=grid), "sky", "R")
    state = PreviewState()
    original = state.complete(
        state.start(selection),
        selection,
        PreviewResult(_photo_frame(fitted), visual_only=True, fitted_grid=fitted, overview_edge=512),
    )
    assert original is not None and state.photo_overview(selection) is original

    request = state.start_crop(selection)
    full_grid = replace(fitted, crop=None)
    assert request is not None and request.crop_grid == full_grid
    assert state.photo_overview(selection) is None
    suggested = Region(1, 1, 34, 29)
    crop_overview = state.complete(
        request,
        selection,
        PreviewResult(_photo_frame(full_grid), visual_only=True, suggested_crop=suggested),
    )
    assert crop_overview is not None and crop_overview.grid == full_grid
    assert state.crop is not None and state.crop.suggested == suggested
    assert state.grid_for_crop(selection, suggested) == replace(fitted, crop=suggested)
    assert state.photo_overview(selection) is None

    restored = state.restore_crop(selection)
    assert restored is not None and restored is not original
    assert restored.frame is original.frame and restored.grid == fitted
    assert state.photo_overview(selection) is restored and restored.overview_edge == 512
    assert state.current(selection) is not crop_overview


def test_crop_cannot_apply_or_restore_to_a_changed_project() -> None:
    grid = RenderSpec((32.0, 10.0), (24, 18), 7.2)
    project = MosaicProject(render=grid)
    selection = PreviewSelection(project, "sky", "R")
    edited = replace(selection, project=replace(project, auto_frame_preview=True))
    state = PreviewState()
    result = PreviewResult(_photo_frame(grid), visual_only=True)
    assert state.complete(state.start(selection), selection, result) is not None
    request = state.start_crop(selection)
    assert request is not None and state.is_stale(edited, linked=True)
    assert state.complete(request, edited, result) is None
    assert state.grid_for_crop(edited, Region(1, 1, 20, 15)) is None
    assert state.restore_crop(edited) is None
    assert state.crop is None and state.frame is None
    assert state.complete(request, selection, result) is None


def test_adaptive_preview_keeps_the_resolved_grid_and_previous_frame() -> None:
    grid = RenderSpec((32.0, 10.0), (24, 18), 7.2)
    fitted = replace(grid, crop=Region(2, 3, 18, 12))
    selection = PreviewSelection(MosaicProject(render=grid), "sky", "R")
    state = PreviewState()
    frame = _photo_frame(fitted)
    result = PreviewResult(frame, visual_only=True, fitted_grid=fitted, overview_edge=512)
    original = state.complete(state.start(selection), selection, result)
    assert original is not None

    request = state.start_adaptive(original)
    assert request.adaptive_from is original and state.frame is frame
    state.finish_adaptive()
    assert state.current(selection) is original
    assert state.complete(request, selection, result) is None

    request = state.start_adaptive(original)
    updated_frame = _photo_frame(fitted)
    updated = state.complete(request, selection, PreviewResult(updated_frame, overview_edge=768))
    assert updated is not None and updated.frame is updated_frame
    assert updated.fitted_grid == fitted and updated.visual_only and updated.overview_edge == 768
