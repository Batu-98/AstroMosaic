"""Prepare relative panel corrections for the bounded mosaic renderer."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Literal

from astromosaic.astrometry.registration import EdgeReport, Residuals, project_field, register
from astromosaic.astrometry.stars import measure_stars
from astromosaic.core.job import JobContext
from astromosaic.geometry import PanelGeometry
from astromosaic.io import PanelSource
from astromosaic.photometry import PanelCorrection
from astromosaic.photometry.background import (
    BackgroundMode,
    BackgroundPanel,
    BackgroundReport,
    fit_background,
)


@dataclass(frozen=True, slots=True)
class RefinementSpec:
    max_shift_px: float = 6.0
    background: BackgroundMode = "offset"

    def __post_init__(self) -> None:
        if not isfinite(self.max_shift_px) or self.max_shift_px <= 0:
            raise ValueError("Expected a positive finite registration search radius.")
        if self.background not in ("none", "offset", "plane"):
            raise ValueError("Expected background mode none, offset, or plane.")


@dataclass(frozen=True, slots=True)
class RefinementReport:
    status: Literal["ready", "weak", "disconnected"]
    components: tuple[tuple[int, ...], ...]
    stars_per_panel: tuple[int, ...]
    edges: tuple[EdgeReport, ...]
    held_out_alignment: Residuals | None
    held_out_gain_error: float | None
    background: BackgroundReport | None = None
    corrections: tuple[PanelCorrection, ...] = ()


class RefinementRejected(ValueError):
    def __init__(self, report: RefinementReport) -> None:
        self.report = report
        super().__init__(
            f"The relative refinement is {report.status}. Review the overlap diagnostics."
        )


def validate_refinement_inputs(sources: Sequence[PanelSource]) -> None:
    if any(source.descriptor.channel_layout != "mono" for source in sources):
        raise ValueError("Relative refinement currently requires mono panels.")
    if len(sources) < 2:
        raise ValueError("Relative refinement requires at least two panels.")


def refine_panels(
    panels: Sequence[tuple[PanelSource, PanelGeometry]],
    target: PanelGeometry,
    spec: RefinementSpec,
    budget: int,
    context: JobContext,
) -> RefinementReport:
    validate_refinement_inputs([source for source, _ in panels])
    exclusions = []
    star_counts = []
    fields = []
    reserved = 0
    for source, geometry in panels:
        field = measure_stars(source, budget - reserved, context)
        descriptor = source.descriptor
        projected = project_field(field, geometry, target, descriptor.width, descriptor.height)
        exclusions.append(field.exclusions)
        star_counts.append(len(field.stars))
        fields.append(projected)
        reserved += projected.positions.nbytes + projected.fluxes.nbytes + field.exclusions.nbytes
    registration = register(fields, spec.max_shift_px, context)
    components = tuple(tuple(index + 1 for index in group) for group in registration.components)
    counts = tuple(star_counts)
    edges = tuple(
        EdgeReport(
            (edge.panels[0] + 1, edge.panels[1] + 1),
            edge.matched,
            edge.training_inliers,
            edge.held_out,
        )
        for edge in registration.edges
    )
    alignment, flux_error = registration.held_out, registration.held_out_gain_error
    if registration.status != "ready":
        raise RefinementRejected(
            RefinementReport(registration.status, components, counts, edges, alignment, flux_error)
        )

    background_inputs = []
    for index, (source, geometry) in enumerate(panels):
        dx, dy = registration.shifts[index]
        background_inputs.append(
            BackgroundPanel(
                source,
                geometry,
                fields[index].bounds,
                exclusions[index],
                (float(dx), float(dy)),
                float(registration.gains[index]),
            )
        )
    coefficients, background = fit_background(
        background_inputs, registration.pairs, target, spec.background, budget - reserved, context
    )
    corrections = tuple(
        PanelCorrection(panel.shift, panel.gain, (float(row[0]), float(row[1]), float(row[2])))
        for panel, row in zip(background_inputs, coefficients, strict=True)
    )
    return RefinementReport(
        "ready", components, counts, edges, alignment, flux_error, background, corrections
    )
