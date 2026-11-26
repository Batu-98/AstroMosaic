"""Track which project and grid the desktop preview represents."""

from dataclasses import dataclass, replace

from astromosaic.core import Region
from astromosaic.display import DisplayFrame
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.pipeline.photo_fit import PhotoReport
from astromosaic.storage.project import Layer, MosaicProject


@dataclass(frozen=True, slots=True)
class PreviewSelection:
    project: MosaicProject
    layer: Layer
    band: str | None


@dataclass(frozen=True, slots=True, eq=False)
class PreviewRequest:
    selection: PreviewSelection
    crop_grid: RenderSpec | None = None


@dataclass(frozen=True, slots=True)
class PreviewResult:
    frame: DisplayFrame
    visual_only: bool = False
    fitted_grid: RenderSpec | None = None
    suggested_crop: Region | None = None
    suggested_rotation: float | None = None
    photo: PhotoReport | None = None
    overview_edge: int = 0


@dataclass(frozen=True, slots=True, eq=False)
class PreviewOverview:
    selection: PreviewSelection
    frame: DisplayFrame
    grid: RenderSpec
    visual_only: bool
    fitted: bool
    suggested_rotation: float | None
    overview_edge: int

    @property
    def fitted_grid(self) -> RenderSpec | None:
        return self.grid if self.fitted else None


@dataclass(frozen=True, slots=True)
class CropDraft:
    previous: PreviewOverview
    suggested: Region | None = None

    @property
    def grid(self) -> RenderSpec:
        return self.previous.grid


class PreviewState:
    """Accept worker results only for the current request or displayed overview."""

    def __init__(self) -> None:
        self._request: PreviewRequest | None = None
        self._proxy: DisplayFrame | None = None
        self._overview: PreviewOverview | None = None
        self.crop: CropDraft | None = None

    @property
    def frame(self) -> DisplayFrame | None:
        return self._overview.frame if self._overview is not None else self._proxy

    def current(self, selection: PreviewSelection) -> PreviewOverview | None:
        overview = self._overview
        return overview if overview is not None and overview.selection == selection else None

    def sky_overview(self, selection: PreviewSelection) -> PreviewOverview | None:
        if self.crop is not None or selection.layer != "sky":
            return None
        overview = self.current(selection)
        return overview if overview is not None and overview.frame.has_coverage else None

    def photo_overview(self, selection: PreviewSelection) -> PreviewOverview | None:
        overview = self.sky_overview(selection)
        return overview if overview is not None and overview.frame.photo_levels is not None else None

    def is_stale(self, selection: PreviewSelection, *, linked: bool) -> bool:
        if self._request is not None:
            return self._request.selection != selection
        return self._overview is not None and (self._overview.selection != selection or not linked)

    def clear(self) -> None:
        self._request = None
        self._proxy = None
        self._overview = None
        self.crop = None

    def start(self, selection: PreviewSelection) -> PreviewRequest:
        self.clear()
        request = self._request = PreviewRequest(selection)
        return request

    def start_crop(self, selection: PreviewSelection) -> PreviewRequest | None:
        previous = self.sky_overview(selection)
        if previous is None:
            return None
        self.clear()
        self.crop = CropDraft(previous)
        request = self._request = PreviewRequest(selection, replace(previous.grid, crop=None))
        return request

    def accepts(self, request: PreviewRequest, selection: PreviewSelection) -> bool:
        return self._request is request and request.selection == selection

    def show_proxy(
        self, request: PreviewRequest, selection: PreviewSelection, frame: DisplayFrame
    ) -> bool:
        if not self.accepts(request, selection):
            return False
        self._proxy = frame
        return True

    def complete(
        self, request: PreviewRequest, selection: PreviewSelection, result: PreviewResult
    ) -> PreviewOverview | None:
        if not self.accepts(request, selection):
            return None
        self._request = None
        self._proxy = None
        fitted = (
            result.fitted_grid
            if request.crop_grid is None and result.frame.has_coverage
            else None
        )
        if self.crop is not None:
            self.crop = replace(self.crop, suggested=result.suggested_crop)
        self._overview = PreviewOverview(
            request.selection,
            result.frame,
            request.crop_grid or fitted or selection.project.render,
            result.visual_only,
            fitted is not None,
            result.suggested_rotation,
            result.overview_edge,
        )
        return self._overview

    def grid_for_crop(self, selection: PreviewSelection, crop: Region) -> RenderSpec | None:
        draft = self.crop
        if draft is None or draft.previous.selection != selection:
            return None
        grid = draft.grid
        return replace(grid, crop=None if crop == Region(0, 0, *grid.size) else crop)

    def restore_crop(self, selection: PreviewSelection) -> PreviewOverview | None:
        if self.crop is None:
            return None
        previous = self.crop.previous
        self.clear()
        if previous.selection == selection:
            # Restore the pixels with a new overview identity for detail workers.
            self._overview = replace(previous)
        return self._overview

    def adopt_grid(self, project: MosaicProject) -> None:
        overview = self._overview
        assert overview is not None and overview.fitted_grid == project.render
        self._overview = replace(
            overview, selection=replace(overview.selection, project=project), fitted=False
        )
