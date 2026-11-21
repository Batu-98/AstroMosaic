"""Read terrain views and fit reviewed points on cancellable worker threads."""

from dataclasses import dataclass
from math import isqrt

from PySide6.QtCore import QObject

from astromosaic.core import Region, Tile
from astromosaic.core.job import JobContext
from astromosaic.core.masks import MASK_EDGE
from astromosaic.display import DisplayFrame, normalize_tile
from astromosaic.io import PanelSource
from astromosaic.pipeline.control_points import XY, ControlPointFit, GroundControlPoint, ModelChoice
from astromosaic.pipeline.masking import read_thumbnail
from astromosaic.storage.project import (
    MosaicProject,
    apply_project_ground_fit,
    fit_project_foreground_points,
    open_project_ground_panel,
)
from astromosaic.ui.mosaic_job import BackgroundJob

_DETAIL_EDGE = 256


@dataclass(frozen=True, slots=True)
class TerrainImage:
    region: Region
    display: DisplayFrame


def _read_detail(source: PanelSource, focus: XY, budget: int, context: JobContext) -> Tile:
    width, height = source.descriptor.width, source.descriptor.height
    side = _DETAIL_EDGE
    while side:
        w, h = min(width, side), min(height, side)
        x = min(width - w, max(0, round(focus[0]) - w // 2))
        y = min(height - h, max(0, round(focus[1]) - h // 2))
        region = Region(x, y, w, h)
        if source.tile_bytes(region) + 128 * w * h <= budget:
            context.check_cancelled()
            return source.read_tile(region)
        side //= 2
    raise ValueError("The working budget cannot fit a foreground detail tile.")


class TerrainImageJob(BackgroundJob[dict[int, TerrainImage]]):
    label = "foreground preview"

    def __init__(
        self, project: MosaicProject, panels: tuple[int, ...], parent: QObject, *, focus: XY | None
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.panels = panels
        self.focus = focus

    def perform(self, context: JobContext) -> dict[int, TerrainImage]:
        masks = dict(self.project.foreground_inputs())
        remaining = self.project.render.max_working_bytes
        frames = {}
        for index in self.panels:
            panel, mask = self.project.panels[index], masks[index]
            with open_project_ground_panel(panel, mask, remaining, context) as source:
                if self.focus is None:
                    region = Region(0, 0, *mask.source_size)
                    edge = max(1, min(MASK_EDGE, isqrt(remaining // 256)))
                    tile = read_thumbnail(source, edge, remaining, context)
                else:
                    tile = _read_detail(source, self.focus, remaining, context)
                    region = tile.region
                display = normalize_tile(tile, mask.source_size)
            remaining -= display.rgba.nbytes
            frames[index] = TerrainImage(region, display)
            del tile
        context.check_cancelled()
        return frames


class TerrainFitJob(BackgroundJob[tuple[ControlPointFit, MosaicProject | None]]):
    label = "terrain fit"

    def __init__(
        self,
        project: MosaicProject,
        points: tuple[GroundControlPoint, ...],
        model: ModelChoice,
        anchor: int,
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.points = points
        self.model = model
        self.anchor = anchor

    def perform(self, context: JobContext) -> tuple[ControlPointFit, MosaicProject | None]:
        fit = fit_project_foreground_points(
            self.project, self.points, context, model=self.model, anchor=self.anchor
        )
        aligned = None
        if fit.status == "accepted":
            aligned = apply_project_ground_fit(self.project, fit, self.points, "manual", context)
        context.check_cancelled()
        return fit, aligned
