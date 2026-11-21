"""Run blocking desktop jobs on Qt worker threads."""

import logging
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Event
from time import monotonic

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from astromosaic.astrometry.solve import SolveOptions
from astromosaic.astrometry.solve_budget import SolveBudget, SolveBudgetExceeded
from astromosaic.core import Tile
from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.core.masks import MASK_EDGE, SKY, UNCLASSIFIED, SourceMask
from astromosaic.display import DisplayFrame, normalize_preview, normalize_tile
from astromosaic.geometry.image import CompositionSpec
from astromosaic.io import open_panel
from astromosaic.io.fits import open_fits_sky_mask
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
    SkyCalibrationError,
    SkyCalibrationRequirement,
)
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
    solve_project_panel,
)


class BackgroundJob[Result](QThread):
    progress = Signal(object, object)
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
            self.result = self.perform(JobContext(self._cancel.is_set, self._progress))
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
    label = "plate solve"
    progress_label = "Solving"
    progress_units = "panels"

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

    def perform(self, context: JobContext) -> None:
        started = monotonic()
        self.queue_seconds = started - self.queued_at
        if self.batch_budget is not None:
            context = self.batch_budget.context(context)
        try:
            try:
                context.check_cancelled()
                indices = (
                    (self.selected_panel,)
                    if self.selected_panel is not None
                    else panels_needing_wcs(self.project, context)
                )
                context.check_cancelled()
            finally:
                self.eligibility_seconds = monotonic() - started
            self.total = len(indices)
            if self.total:
                self._progress(0, self.total)
            for done, index in enumerate(indices, 1):
                context.check_cancelled()
                outcome = solve_project_panel(
                    index,
                    self.project.panels[index],
                    self.options,
                    self.directory,
                    context,
                    job_budget=self.batch_budget,
                )
                self.outcomes.append(outcome)
                self._progress(done, self.total)
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
    ) -> None:
        super().__init__(project, parent)
        self.destination = destination
        self.layer = layer
        self.band = band

    def perform(self, context: JobContext) -> MosaicResult:
        if self.layer == "sky" and self.band is None:
            return render_project(self.project, self.destination, context)
        return render_project_layer(
            self.project, self.layer, self.destination, context, band=self.band
        )


class PreviewJob(_ProjectJob[DisplayFrame]):
    proxy_ready = Signal(object)
    label = "preview"
    progress_label = "Previewing"

    def __init__(
        self,
        project: MosaicProject,
        parent: QObject,
        layer: Layer = "sky",
        *,
        band: str | None = None,
    ) -> None:
        super().__init__(project, parent)
        self.layer = layer
        self.band = band

    def _publish_proxy(self, preview: PreviewFrame) -> None:
        self.proxy_ready.emit(normalize_preview(preview))

    def perform(self, context: JobContext) -> DisplayFrame:
        preview = (
            preview_project(self.project, context, self._publish_proxy)
            if self.layer == "sky" and self.band is None
            else preview_project_layer(
                self.project, self.layer, context, self._publish_proxy, band=self.band
            )
        )
        frame = normalize_preview(preview)
        context.check_cancelled()
        return frame


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
