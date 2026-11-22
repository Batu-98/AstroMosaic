"""Run blocking desktop jobs on Qt worker threads."""

import logging
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from threading import Event
from time import monotonic

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from astromosaic.astrometry.solve import SolveOptions, SolveStep
from astromosaic.astrometry.solve_budget import SolveBudget, SolveBudgetExceeded
from astromosaic.core import Region, Tile
from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.core.masks import MASK_EDGE, SKY, UNCLASSIFIED, SourceMask
from astromosaic.display import DisplayFrame, normalize_preview, normalize_tile
from astromosaic.geometry.image import CompositionSpec
from astromosaic.io import open_panel
from astromosaic.io.fits import open_fits_sky_mask
from astromosaic.photometry.photo import PhotoTone
from astromosaic.pipeline.foreground import (
    ForegroundAlignmentRejected,
    ForegroundGraphResiduals,
    ForegroundPairDiagnostic,
)
from astromosaic.pipeline.masking import (
    DETECTION_EDGE,
    propose_mask,
    read_thumbnail,
    suggest_foreground,
)
from astromosaic.pipeline.mosaic import (
    MosaicResult,
    PreviewFrame,
    RenderSpec,
    SkyCalibrationError,
    SkyCalibrationRequirement,
)
from astromosaic.pipeline.photo_fit import PhotoReport
from astromosaic.storage.project import (
    Layer,
    MosaicProject,
    PanelInspection,
    PanelSolveOutcome,
    ProjectPanel,
    align_project_foreground,
    inspect_project_panel,
    panels_needing_wcs,
    preview_project,
    preview_project_layer,
    propose_project_composition,
    render_project,
    render_project_layer,
    render_project_photo,
    solve_project_panel,
)


class BackgroundJob[Result](QThread):
    progress = Signal(object, object)
    stage_changed = Signal(str)
    label = "job"
    progress_label = "Processing"
    progress_units = "pixels"

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.result: Result | None = None
        self.error: str | None = None
        self.calibration_requirement: SkyCalibrationRequirement | None = None
        self.cancelled = False
        self._cancel = Event()
        self._last_update = 0.0

    def cancel(self) -> None:
        self._cancel.set()

    def _progress(self, done: int, total: int) -> None:
        now = monotonic()
        if done == total or now - self._last_update >= 0.05:
            self._last_update = now
            self.progress.emit(done, total)

    def run(self) -> None:
        try:
            self.result = self.perform(JobContext(
                self._cancel.is_set, self._progress, on_stage=self.stage_changed.emit
            ))
        except MosaicCancelled:
            self.cancelled = True
        except (OSError, RuntimeError, ValueError) as error:
            self.error = str(error)
            if isinstance(error, SkyCalibrationError):
                self.calibration_requirement = error.requirement
        except Exception as error:
            logging.getLogger(__name__).error("Unexpected job error (%s).", type(error).__name__)
            self.error = f"Unexpected job error ({type(error).__name__})."

    def perform(self, context: JobContext) -> Result:
        raise NotImplementedError


class _ProjectJob[Result](BackgroundJob[Result]):
    def __init__(self, project: MosaicProject, parent: QObject) -> None:
        super().__init__(parent)
        self.project = project


class PanelInspectionJob(_ProjectJob[tuple[PanelInspection, ...]]):
    """Read and validate lightweight panel metadata off the UI thread."""

    def perform(self, context: JobContext) -> tuple[PanelInspection, ...]:
        return tuple(inspect_project_panel(panel, context) for panel in self.project.panels)


class PlateSolveJob(_ProjectJob[None]):
    solve_progress = Signal(int, str)
    label = "plate solve"
    _eligibility_percent = 10

    def __init__(
        self,
        project: MosaicProject,
        options: SolveOptions,
        directory: Path,
        parent: QObject,
        *,
        selected_panel: int | None = None,
    ) -> None:
        super().__init__(project, parent)
        self.options = options
        self.directory = directory
        self.selected_panel = selected_panel
        self.batch_budget = (
            SolveBudget.begin(options.job_seconds, scope="job")
            if options.job_seconds is not None
            else None
        )
        self.queued_at = monotonic()
        self.queue_seconds = self.eligibility_seconds = self.elapsed_seconds = 0.0
        self.total = 0
        self.outcomes: list[PanelSolveOutcome] = []

    def _checking(self, checked: int, total: int) -> None:
        now = monotonic()
        if 0 < checked < total and now - self._last_update < 0.05:
            return
        self._last_update = now
        self.solve_progress.emit(
            self._eligibility_percent * checked // total,
            f"Plate Solve · Checking sky panels for reusable WCS ({checked:,} of {total:,})",
        )

    def _panel_progress(self, ordinal: int, index: int, percent: int, phase: str) -> None:
        progress = self._eligibility_percent + (
            (100 - self._eligibility_percent) * (100 * ordinal + percent) // (100 * self.total)
        )
        name = self.project.panels[index].source.path.name
        self.solve_progress.emit(
            progress, f"Plate Solve · Panel {ordinal + 1:,} of {self.total:,} · {name}\n{phase}"
        )

    def _solve_step(self, ordinal: int, index: int, step: SolveStep) -> None:
        if step.phase == "publish":
            self._panel_progress(ordinal, index, 75, "Saving validated WCS…")
            return
        offset, label = {
            "prepare": (0, "Preparing {backend}"),
            "search": (1, "Searching with {backend}"),
            "validate": (2, "Validating {backend} result"),
        }[step.phase]
        backend = "Gaia DR3" if step.stage == "gaia-dr3" else "ASTAP"
        method = {"hinted": "Hinted", "blind": "Blind", "fov-recovery": "Field-of-view recovery"}
        description = label.format(backend=backend)
        if name := method.get(step.method or ""):
            description += f" · {name}"
        # Within a panel, preparation and publication each have one quarter.
        # The middle half covers preparation, search and validation of the planned attempts.
        percent = 25 + 50 * (3 * (step.attempt - 1) + offset) // (3 * step.attempts)
        self._panel_progress(ordinal, index, percent, f"{description}…")

    def perform(self, context: JobContext) -> None:
        started = monotonic()
        self.queue_seconds = started - self.queued_at
        if self.batch_budget is not None:
            context = self.batch_budget.context(context)
        try:
            try:
                context.check_cancelled()
                if self.selected_panel is None:
                    indices = panels_needing_wcs(self.project, context, on_inspected=self._checking)
                else:
                    indices = (self.selected_panel,)
                context.check_cancelled()
            finally:
                self.eligibility_seconds = monotonic() - started
            self.total = len(indices)
            for ordinal, index in enumerate(indices):
                context.check_cancelled()
                self._panel_progress(ordinal, index, 0, "Reading image and solve hints…")
                outcome = solve_project_panel(
                    index,
                    self.project.panels[index],
                    self.options,
                    self.directory,
                    context,
                    job_budget=self.batch_budget,
                    on_step=partial(self._solve_step, ordinal, index),
                )
                self.outcomes.append(outcome)
                if self.batch_budget is not None and outcome.status == "budget-exhausted":
                    self.batch_budget.check()
                    if outcome.budget is not None and outcome.budget["limiting_scope"] == "job":
                        raise SolveBudgetExceeded(outcome.error or "The job solve budget elapsed.")
        finally:
            self.elapsed_seconds = monotonic() - self.queued_at


class MosaicJob(_ProjectJob[MosaicResult]):
    label = "mosaic"
    progress_label = "Rendering"

    def __init__(
        self,
        project: MosaicProject,
        destination: Path,
        parent: QObject,
        layer: Layer = "sky",
        *,
        band: str | None = None,
        photo_grid: RenderSpec | None = None,
        photo_tone: PhotoTone | None = None,
    ) -> None:
        super().__init__(project, parent)
        self.destination = destination
        self.layer = layer
        self.band = band
        self.photo_grid = photo_grid
        self.photo_tone = photo_tone

    def perform(self, context: JobContext) -> MosaicResult:
        if self.photo_grid is not None:
            return render_project_photo(
                self.project,
                self.destination,
                context,
                band=self.band,
                grid=self.photo_grid,
                tone=self.photo_tone,
            )
        if self.layer == "sky" and self.band is None:
            return render_project(self.project, self.destination, context)
        return render_project_layer(
            self.project, self.layer, self.destination, context, band=self.band
        )


class PreviewJob(_ProjectJob[DisplayFrame]):
    proxy_ready = Signal(object, bool)
    label = "preview"
    progress_label = "Previewing"

    def __init__(
        self,
        project: MosaicProject,
        parent: QObject,
        layer: Layer = "sky",
        *,
        band: str | None = None,
        adaptive_edge: int | None = None,
        crop_grid: RenderSpec | None = None,
    ) -> None:
        super().__init__(project, parent)
        self.layer = layer
        self.band = band
        self.fitted_grid: RenderSpec | None = None
        self.visual_only = False
        self.photo_report: PhotoReport | None = None
        self.adaptive_edge = adaptive_edge
        self.crop_grid = crop_grid
        self.suggested_crop: Region | None = None
        self.suggested_rotation: float | None = None

    def _publish_proxy(self, preview: PreviewFrame) -> None:
        self.proxy_ready.emit(normalize_preview(preview), preview.visual_only)

    def perform(self, context: JobContext) -> DisplayFrame:
        preview = (
            preview_project(
                self.project, context, self._publish_proxy, band=self.band, allow_visual=True,
                adaptive_edge=self.adaptive_edge,
                grid=replace(self.crop_grid, crop=None) if self.crop_grid is not None else None,
                inspect_crop=self.crop_grid is not None,
            )
            if self.layer == "sky"
            else preview_project_layer(
                self.project, self.layer, context, self._publish_proxy, band=self.band,
                adaptive_edge=self.adaptive_edge,
            )
        )
        frame = normalize_preview(preview)
        context.check_cancelled()
        self.fitted_grid = preview.fitted_grid
        self.visual_only = preview.visual_only
        self.photo_report = preview.photo
        self.suggested_crop = preview.suggested_crop
        self.suggested_rotation = preview.suggested_rotation
        return frame


class PreviewDetailJob(_ProjectJob[DisplayFrame]):
    def __init__(
        self, project: MosaicProject, parent: QObject, layer: Layer, window: Region,
        levels: tuple[float, float], *, band: str | None, grid: RenderSpec | None,
    ) -> None:
        super().__init__(project, parent)
        self.layer = layer
        self.window = window
        self.levels = levels
        self.band = band
        self.grid = grid

    def perform(self, context: JobContext) -> DisplayFrame:
        if self.layer == "sky":
            frame = preview_project(
                self.project, context, band=self.band, grid=self.grid, window=self.window,
                allow_visual=True,
            )
        else:
            frame = preview_project_layer(self.project, self.layer, context, window=self.window)
        display = normalize_preview(frame, levels=self.levels)
        context.check_cancelled()
        return display


@dataclass(frozen=True, slots=True)
class ForegroundAlignmentReport:
    pairs: tuple[ForegroundPairDiagnostic, ...]
    groups: tuple[tuple[int, ...], ...]
    residuals: ForegroundGraphResiduals
    error: str | None


class ForegroundAlignmentJob(_ProjectJob[MosaicProject]):
    label = "foreground alignment"
    progress_label = "Comparing foreground"
    progress_units = "steps"

    def __init__(self, project: MosaicProject, parent: QObject) -> None:
        super().__init__(project, parent)
        self.pairs: list[ForegroundPairDiagnostic] = []
        self.groups: tuple[tuple[int, ...], ...] = ()
        self.residuals: ForegroundGraphResiduals = ()

    def report(self) -> ForegroundAlignmentReport | None:
        if not self.pairs or self.cancelled:
            return None
        return ForegroundAlignmentReport(tuple(self.pairs), self.groups, self.residuals, self.error)

    def perform(self, context: JobContext) -> MosaicProject:
        try:
            result = align_project_foreground(self.project, context, on_pair=self.pairs.append)
        except ForegroundAlignmentRejected as rejection:
            self.groups = rejection.groups
            self.residuals = rejection.residuals
            raise
        assert result.foreground is not None
        self.groups = (tuple(panel.index for panel in result.foreground.alignment.panels),)
        return result


class CompositionProposalJob(_ProjectJob[CompositionSpec]):
    label = "placement proposal"

    def perform(self, context: JobContext) -> CompositionSpec:
        return propose_project_composition(self.project, context)


def _panel_thumbnail(
    panel: ProjectPanel, edge: int, budget: int, context: JobContext
) -> tuple[Tile, tuple[int, int]]:
    context.check_cancelled()
    with open_panel(panel.source.path, max_tile_bytes=budget) as source:
        descriptor = source.descriptor
        if descriptor.fingerprint != panel.source.fingerprint:
            raise ValueError(f"Source file changed: {panel.source.path.name}")
        return read_thumbnail(source, edge, budget, context), (descriptor.width, descriptor.height)


class ForegroundJob(_ProjectJob[tuple[MosaicProject, tuple[str, ...]]]):
    label = "foreground check"
    progress_label = "Checking"
    progress_units = "panels"

    def __init__(self, project: MosaicProject, indices: tuple[int, ...], parent: QObject) -> None:
        super().__init__(project, parent)
        self.indices = indices

    def perform(self, context: JobContext) -> tuple[MosaicProject, tuple[str, ...]]:
        panels = list(self.project.panels)
        problems = []
        budget = self.project.render.max_working_bytes
        for done, index in enumerate(self.indices, start=1):
            panel = panels[index]
            try:
                thumb, _ = _panel_thumbnail(
                    panel, DETECTION_EDGE, budget, JobContext(context.is_cancelled)
                )
                panels[index] = replace(panel, foreground_suggestion=suggest_foreground(thumb))
            except (OSError, ValueError) as error:
                problems.append(f"{panel.source.path.name}: {error}")
            if context.on_progress is not None:
                context.on_progress(done, len(self.indices))
        context.check_cancelled()
        return replace(self.project, panels=tuple(panels)), tuple(problems)


@dataclass(frozen=True, slots=True)
class MaskEditorFrame:
    image: DisplayFrame
    saved: SourceMask | None
    proposed: SourceMask | None
    attachment_error: str | None


class MaskEditorJob(_ProjectJob[MaskEditorFrame]):
    label = "sky mask"
    progress_label = "Reading mask preview"

    def __init__(self, project: MosaicProject, index: int, propose: bool, parent: QObject) -> None:
        super().__init__(project, parent)
        self.index = index
        self.propose = propose

    def perform(self, context: JobContext) -> MaskEditorFrame:
        panel = self.project.panels[self.index]
        attached = panel.sky_mask
        budget = self.project.render.max_working_bytes
        thumb, size = _panel_thumbnail(panel, MASK_EDGE, budget, context)
        saved = panel.source_mask
        attachment_error = None
        if attached is not None:
            try:
                with open_fits_sky_mask(attached.path, *size) as source:
                    if source.descriptor.fingerprint != attached.fingerprint:
                        raise ValueError("The attached FITS mask changed on disk.")
                    proxy = read_thumbnail(
                        source,
                        MASK_EDGE,
                        budget,
                        JobContext(context.is_cancelled),
                        binary_mask=True,
                    )
                labels = np.where(proxy.pixels == 1.0, SKY, UNCLASSIFIED).astype(np.uint8)
                saved = SourceMask(size, labels.tobytes())
            except (OSError, ValueError) as error:
                attachment_error = str(error)
        if saved is not None and saved.source_size != size:
            raise ValueError("The saved sky mask does not match the source dimensions.")
        proposed = propose_mask(thumb, size, context) if self.propose else None
        image = normalize_tile(thumb, size)
        context.check_cancelled()
        return MaskEditorFrame(image, saved, proposed, attachment_error)
