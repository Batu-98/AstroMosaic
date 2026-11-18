"""Render bounded foreground and visual composition tiles from original panels."""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from importlib.metadata import version
from math import atan2, degrees, hypot

import numpy as np
from astropy.io import fits

from astromosaic.core import Region, Tile
from astromosaic.core.job import JobContext
from astromosaic.core.masks import FOREGROUND, SKY, SourceMask
from astromosaic.geometry import raster_pixels
from astromosaic.geometry.footprint import (
    MAX_FOOTPRINT_COORDINATE,
    PixelBounds,
    enclosing_bounds,
    raster_bounds,
)
from astromosaic.geometry.image import CompositionSpec, LayerPlacement, Points
from astromosaic.io import PanelSource
from astromosaic.photometry import PanelCorrection
from astromosaic.pipeline.foreground import ForegroundAlignment, GroundPanel
from astromosaic.pipeline.mosaic import (
    RenderSpec,
    _Coordinates,
    _footprint_reservation,
    _PreparedMosaic,
    _RasterPlan,
    _RenderedTile,
    _Scale,
    _set_calibration,
    _try_tile,
    _WorkingBudget,
)


@dataclass(frozen=True, slots=True)
class ForegroundSource:
    source: PanelSource
    weight: float
    mask: SourceMask
    transform: GroundPanel
    correction: PanelCorrection | None = None


@dataclass(frozen=True, slots=True)
class ForegroundLayer:
    panels: Sequence[ForegroundSource]
    alignment: ForegroundAlignment
    spec: RenderSpec
    filter_name: str | None
    assume_brightness: bool

    @property
    def size(self) -> tuple[int, int]:
        return self.alignment.canvas.width, self.alignment.canvas.height

    @property
    def channels(self) -> int:
        return 3 if self.panels[0].source.descriptor.channel_layout == "rgb" else 1

    def raster(
        self,
        *,
        origin: tuple[int, int] = (0, 0),
        placement: LayerPlacement | None = None,
    ) -> _RasterPlan:
        layout = self.panels[0].source.descriptor.channel_layout
        if any(panel.source.descriptor.channel_layout != layout for panel in self.panels):
            raise ValueError("Supply either all mono or all RGB foreground panels.")
        header = fits.Header()
        _set_calibration(
            header,
            [panel.source for panel in self.panels],
            self.filter_name,
            self.assume_brightness,
        )
        _history(header, "CPU image-space foreground mosaic.")
        x, y = self.alignment.canvas.x, self.alignment.canvas.y
        header.add_history(f"Foreground canvas starts at anchor pixel ({x}, {y}).")
        for panel in self.panels:
            fingerprint = panel.source.descriptor.fingerprint
            index = panel.transform.index + 1
            dx, dy = panel.transform.shift
            header.add_history(
                f"Ground panel {index}: {fingerprint.size_bytes} B, mtime {fingerprint.modified_ns} ns."
            )
            header.add_history(
                f"Ground panel {index}: shift ({dx:.8g}, {dy:.8g}) px, weight {panel.weight:g}."
            )
        for edge in self.alignment.overlaps:
            left, right = (index + 1 for index in edge.panels)
            header.add_history(
                f"Ground match {left}-{right}: correlation {edge.correlation:.5f}, support {edge.support}."
            )
        footprint_bytes = _footprint_reservation(len(self.panels), self.spec.max_working_bytes)
        footprints = (
            tuple(self._footprint(panel, placement) for panel in self.panels)
            if footprint_bytes
            else ()
        )
        if not any(footprint is not None for footprint in footprints):
            footprint_bytes = 0
            footprints = ()

        def render(
            region: Region, scale: _Scale, budget: _WorkingBudget, context: JobContext
        ) -> _RenderedTile | None:
            return self.try_tile(
                region,
                scale,
                budget,
                context,
                origin=origin,
                placement=placement,
                footprints=footprints,
            )

        return _RasterPlan(
            render,
            len(self.panels),
            self.channels,
            header,
            self.size,
            self.spec,
            footprint_bytes=footprint_bytes,
        )

    def _footprint(
        self, panel: ForegroundSource, placement: LayerPlacement | None
    ) -> PixelBounds | None:
        dx, dy = panel.transform.shift
        canvas = self.alignment.canvas
        if max(abs(dx), abs(dy), abs(canvas.x), abs(canvas.y)) > MAX_FOOTPRINT_COORDINATE:
            return None
        source = panel.source.descriptor
        corners = raster_bounds(
            Region(0, 0, source.width, source.height), origin=(dx - canvas.x, dy - canvas.y)
        ).corners()
        bounds = enclosing_bounds(corners)
        if bounds is None or placement is None:
            return bounds
        with np.errstate(over="ignore", invalid="ignore"):
            return enclosing_bounds(placement.forward(bounds.corners()))

    def try_tile(
        self,
        region: Region,
        scale: _Scale,
        budget: _WorkingBudget,
        context: JobContext,
        *,
        origin: tuple[int, int] = (0, 0),
        placement: LayerPlacement | None = None,
        footprints: Sequence[PixelBounds | None] = (),
    ) -> _RenderedTile | None:
        candidates: Iterable[ForegroundSource] = self.panels
        if footprints:
            tile_bounds = raster_bounds(region, scale, origin)
            candidates = (
                panel
                for panel, footprint in zip(self.panels, footprints, strict=True)
                if footprint is None or footprint.intersects(tile_bounds)
            )

        def make_mapper() -> Callable[[ForegroundSource], _Coordinates]:
            x, y = raster_pixels(region, scale, origin)
            if placement is not None:
                with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                    x, y = placement.inverse(np.column_stack((x, y))).T
            usable = (x >= -0.5) & (x < self.size[0] - 0.5) & (y >= -0.5) & (y < self.size[1] - 0.5)
            px, py = x + self.alignment.canvas.x, y + self.alignment.canvas.y

            def locate(panel: ForegroundSource) -> _Coordinates:
                dx, dy = panel.transform.shift
                return px - dx, py - dy, usable

            return locate

        return _try_tile(region, candidates, make_mapper, budget, context, self.channels)


def _history(header: fits.Header, mode: str) -> None:
    header.add_history(f"AstroMosaic {version('astromosaic')}: {mode}")
    header.add_history("Bilinear valid support; normalized panel weights; linear float32.")


def _horizon_points(mask: SourceMask) -> Points:
    labels = mask.grid()
    rows, columns = labels.shape
    sky, ground = labels == SKY, labels == FOREGROUND
    sky_end = rows - np.argmax(sky[::-1], axis=0)
    ground_start = np.argmax(ground, axis=0)
    usable = sky.any(axis=0) & ground.any(axis=0) & (sky_end <= ground_start)
    x = np.flatnonzero(usable)
    if x.size < 4 or x[-1] - x[0] < columns / 4:
        return np.empty((0, 2), dtype=np.float64)
    x = x[np.linspace(0, x.size - 1, min(x.size, 48), dtype=np.int64)]
    width, height = mask.source_size
    return np.column_stack(
        (
            (x * width // columns + (x + 1) * width // columns) / 2.0 - 0.5,
            (sky_end[x] * height // rows + ground_start[x] * height // rows) / 2.0 - 0.5,
        )
    )


def _fit_placement(ground: Points, sky: Points) -> tuple[LayerPlacement, float] | None:
    if len(ground) < 4 or np.ptp(ground[:, 0]) < 8 or np.ptp(sky, axis=0).max() < 8:
        return None
    center = ground.mean(axis=0)
    target = sky.mean(axis=0)
    x, y = (ground - center).T
    u, v = (sky - target).T
    energy = x @ x + y @ y
    a = (x @ u + y @ v) / energy
    b = (x @ v - y @ u) / energy
    size = hypot(a, b)
    if not 1e-4 < size < 1e4:
        return None
    rotation = degrees(atan2(b, a))
    transform = LayerPlacement(rotation_deg=rotation, scale=size)
    dx, dy = target - transform.forward(center)
    transform = replace(transform, offset=(float(dx), float(dy)))
    errors = np.linalg.norm(transform.forward(ground) - sky, axis=1)
    if np.quantile(errors, 0.95) > 3.0:
        return None
    return transform, float(np.sqrt(np.mean(errors**2)))


def propose_composition(
    sky: _PreparedMosaic,
    sky_indices: Sequence[int],
    ground: ForegroundLayer,
    settings: CompositionSpec,
    context: JobContext,
) -> CompositionSpec:
    sky_panels = dict(zip(sky_indices, sky.panels, strict=True))
    candidates = []
    for panel in ground.panels:
        context.check_cancelled()
        reference = sky_panels.get(panel.transform.index)
        if reference is None:
            continue
        points = _horizon_points(panel.mask)
        if not points.size:
            continue
        target = sky.target.inverse(reference.geometry.forward(*points.T))
        if reference.correction is not None:
            target += reference.correction.shift
        usable = np.isfinite(target).all(axis=1)
        canvas = ground.alignment.canvas
        foreground = points[usable] + panel.transform.shift - (canvas.x, canvas.y)
        target = target[usable]
        fit = _fit_placement(foreground, target)
        if fit is not None:
            placement, rms = fit
            candidates.append(
                (rms, panel.transform.index, placement, float(np.median(target[:, 1])))
            )
    if not candidates:
        raise ValueError("No reliable shared horizon. Set the composition placement manually.")
    rms, index, placement, seam_y = min(candidates, key=lambda item: (item[0], item[1]))
    return replace(
        settings, placement=placement, seam_y=seam_y, reference_panel=index, placement_rms_px=rms
    )


def composition_raster(
    sky: _PreparedMosaic, ground: ForegroundLayer, spec: CompositionSpec
) -> _RasterPlan:
    canvas, seam_width = spec.frame(sky.size, ground.size)
    origin = (canvas.x, canvas.y)
    ground_plan = ground.raster(origin=origin, placement=spec.placement)
    if sky.channels != ground_plan.channels:
        raise ValueError("The sky and foreground require the same channel layout for composition.")
    header = fits.Header()
    _set_calibration(
        header,
        [p.source for p in sky.panels] + [p.source for p in ground.panels],
        ground.filter_name,
        ground.assume_brightness,
    )
    sky_height = sky.size[1] - spec.sky_crop_bottom
    _history(header, "CPU visual sky and foreground composition.")
    header["LAYERS"] = (True, "Layer contribution raster present")
    header.add_history("Layer codes 0 uncovered, 1 sky, 2 foreground, 3 both.")
    header.add_history(f"Composition starts at sky-grid pixel {origin}.")
    header.add_history(f"Foreground offset {spec.placement.offset} in the sky grid.")
    header.add_history(
        f"Foreground rotation {spec.placement.rotation_deg:g} deg, scale {spec.placement.scale:g}."
    )
    header.add_history(f"Sky bottom crop {spec.sky_crop_bottom} px, seam row {spec.seam_y:g}.")
    header.add_history(f"Requested overlap {spec.overlap_percent:g}%, width {seam_width:g} px.")
    if spec.reference_panel is not None:
        header.add_history(f"Placement reference: project panel {spec.reference_panel + 1}.")
    header.add_history(f"Uncomposed sky size: {sky.size[0]} x {sky.size[1]} px.")
    for key in (
        "CRVAL1",
        "CRVAL2",
        "CRPIX1",
        "CRPIX2",
        "CDELT1",
        "CDELT2",
        "PC1_1",
        "PC1_2",
        "PC2_1",
        "PC2_2",
    ):
        if key in sky.header:
            header.add_history(f"Sky TAN grid {key}={sky.header[key]}.")
    for layer_header in (sky.header, ground_plan.header):
        for card in layer_header.cards:
            if card.keyword == "HISTORY":
                header.add_history(card.value)

    def render(
        region: Region, scale: _Scale, budget: _WorkingBudget, context: JobContext
    ) -> _RenderedTile | None:
        blend_bytes = 48 * 1024 + 192 * region.width * region.height
        if not budget.reserve(blend_bytes):
            return None
        local = _WorkingBudget(budget.limit - blend_bytes)
        try:
            above = sky.try_tile(
                region, scale, local, context, origin=origin, sky_height=sky_height
            )
            if above is None:
                return None
            below = ground_plan.render_tile(region, scale, local, context)
            if below is None:
                return None
        finally:
            budget.reserve(local.peak + blend_bytes)
        _, rows = raster_pixels(region, scale, origin)
        return _blend(
            above, below, rows.reshape(region.height, region.width), spec.seam_y, seam_width
        )

    return _RasterPlan(
        render,
        len(sky.panels) + len(ground.panels),
        sky.channels,
        header,
        (canvas.width, canvas.height),
        sky.spec,
        refinement=sky.refinement,
        seam_width=seam_width,
        footprint_bytes=sky.footprint_bytes + ground_plan.footprint_bytes,
    )


def _blend(
    sky: _RenderedTile, ground: _RenderedTile, rows: Points, seam_y: float, seam_width: float
) -> _RenderedTile:
    common = sky.tile.valid & ground.tile.valid
    if seam_width > 0:
        weight = np.clip((seam_y - rows) / seam_width + 0.5, 0, 1)
        weight = weight * weight * (3 - 2 * weight)
    else:
        weight = (rows < seam_y).astype(np.float64)
    use_sky = sky.tile.valid & (~common | (weight > 0))
    use_ground = ground.tile.valid & (~common | (weight < 1))
    both = use_sky & use_ground
    pixels = sky.tile.pixels.copy()
    ground_only = use_ground & ~use_sky
    pixels[ground_only] = ground.tile.pixels[ground_only]
    mix = weight[both]
    if pixels.ndim == 3:
        mix = mix[:, None]
    pixels[both] = mix * sky.tile.pixels[both] + (1 - mix) * ground.tile.pixels[both]
    valid = use_sky | use_ground
    contributions = use_sky.astype(np.uint8) + np.uint8(2) * use_ground.astype(np.uint8)
    return _RenderedTile(
        Tile(sky.tile.region, pixels, valid),
        sky.rejected_coordinates + ground.rejected_coordinates,
        contributions,
        common,
    )
