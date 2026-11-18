"""Render an ICRS TAN mosaic with a bounded, synchronous tile loop."""

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from importlib.metadata import version
from math import isfinite
from pathlib import Path
from typing import Protocol

import numpy as np
from astropy import units as u
from astropy.coordinates import ICRS
from astropy.io import fits
from astropy.wcs import WCS
from numpy.typing import NDArray

from astromosaic.core import Region, SourceFingerprint, Tile
from astromosaic.core.job import DEFAULT_JOB_CONTEXT
from astromosaic.core.job import JobContext as JobContext
from astromosaic.core.job import MosaicCancelled as MosaicCancelled
from astromosaic.geometry import (
    PanelGeometry,
    TileSky,
    raster_pixels,
    read_panel_geometry,
    tan_output_wcs,
)
from astromosaic.geometry.footprint import PixelBounds, raster_bounds, tan_footprint
from astromosaic.io import TIFF_SUFFIXES, PanelSource, SkyMask, open_panel
from astromosaic.io.fits_export import open_fits_mosaic
from astromosaic.photometry import PanelCorrection
from astromosaic.pipeline.refinement import RefinementReport, RefinementSpec, refine_panels
from astromosaic.resampling import sample, source_window

MIB = 1024**2
DEFAULT_WORKING_BYTES = 64 * MIB
DEFAULT_OUTPUT_BYTES = 2048 * MIB
DEFAULT_TILE_SIZE = 128
# Include live WCS/frame and inverse-iteration arrays, blend buffers, and endian conversion.
_OUTPUT_BYTES_PER_PIXEL = 1024
_TILE_FIXED_BYTES = 64 * 1024
_FOOTPRINT_BYTES_PER_PANEL = 256
_PROXY_EDGE = 160
_PREVIEW_EDGE = 512


@dataclass(frozen=True, slots=True)
class RenderSpec:
    center: tuple[float, float]
    size: tuple[int, int]
    scale_arcsec: float
    rotation_deg: float = 0.0
    crop: Region | None = None
    tile_size: int = DEFAULT_TILE_SIZE
    max_working_bytes: int = DEFAULT_WORKING_BYTES
    max_output_bytes: int = DEFAULT_OUTPUT_BYTES

    def output_region(self) -> Region:
        width, height = self.size
        crop = self.crop or Region(0, 0, width, height)
        if not (
            0 <= crop.x < crop.x + crop.width <= width
            and 0 <= crop.y < crop.y + crop.height <= height
        ):
            raise ValueError("Expected a positive output size and a nonempty in-bounds crop.")
        if min(self.tile_size, self.max_working_bytes, self.max_output_bytes) < 1:
            raise ValueError("Tile size and resource budgets must be positive.")
        return crop


@dataclass(frozen=True, slots=True)
class MosaicResult:
    width: int
    height: int
    covered_pixels: int
    panels: int
    tiles: int
    peak_reserved_bytes: int
    rejected_coordinates: int
    backend: str = "cpu"
    refinement: RefinementReport | None = None
    common_pixels: int | None = None


@dataclass(frozen=True, slots=True, eq=False)
class PreviewFrame:
    """Read-only linear raster over the full cropped export rectangle."""

    tile: Tile
    output_size: tuple[int, int]
    output_wcs: WCS | None
    peak_reserved_bytes: int
    common_coverage: NDArray[np.bool_] | None = None
    seam_width: float | None = None


class _RasterPanel(Protocol):
    @property
    def source(self) -> PanelSource: ...
    @property
    def weight(self) -> float: ...
    @property
    def correction(self) -> PanelCorrection | None: ...


type _Coordinates = tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]]
type _Scale = tuple[float, float]


@dataclass(frozen=True, slots=True)
class _Panel:
    source: PanelSource
    geometry: PanelGeometry
    weight: float
    wcs_origin: str = "primary WCS"
    correction: PanelCorrection | None = None
    footprint: PixelBounds | None = None


def _footprint_reservation(panels: int, working_bytes: int) -> int:
    reserved = panels * _FOOTPRINT_BYTES_PER_PANEL
    # Preserve the sampling budget on small jobs. Footprint selection is optional.
    return reserved if panels > 1 and reserved <= working_bytes // 32 else 0


def _set_calibration(
    header: fits.Header,
    sources: Sequence[PanelSource],
    declared_filter: str | None,
    assume_brightness: bool,
) -> None:
    descriptors = [source.descriptor for source in sources]
    declared_filter = declared_filter.strip() if declared_filter is not None else None
    band = declared_filter or descriptors[0].filter_name
    if not band or any((panel.filter_name or declared_filter) != band for panel in descriptors):
        raise ValueError("Expected a common FILTER. Use --filter to declare missing metadata.")

    labels = [panel.unit for panel in descriptors if panel.unit is not None]
    units = [u.Unit(label, format="fits", parse_strict="silent") for label in labels]
    if units and any(unit != units[0] for unit in units):
        raise ValueError("Input BUNIT values must use the same brightness scale.")
    if any(u.pix in unit.bases for unit in units):
        raise ValueError("Per-pixel units require an area-aware conversion before mosaicking.")
    brightness_units = (u.Jy / u.sr, u.W / (u.m**2 * u.sr), u.W / (u.m**2 * u.nm * u.sr))
    if not assume_brightness and (
        len(units) != len(sources)
        or not any(units[0].is_equivalent(candidate) for candidate in brightness_units)
    ):
        raise ValueError("Expected a surface-brightness BUNIT or --assume-surface-brightness.")

    header["FILTER"] = band
    if labels:
        header["BUNIT"] = labels[0]
    if assume_brightness:
        header.add_history("User declared a common surface-brightness scale for all panels.")
    if declared_filter:
        header.add_history("User provided FILTER for panels with missing filter metadata.")


def _export_header(
    target: WCS, panels: Sequence[_Panel], declared_filter: str | None, assume_brightness: bool
) -> fits.Header:
    header = target.to_header()
    _set_calibration(header, [panel.source for panel in panels], declared_filter, assume_brightness)
    header.add_history(f"AstroMosaic {version('astromosaic')}: CPU ICRS TAN reprojection.")
    header.add_history("Bilinear valid support; normalized panel weights; linear float32.")
    for index, panel in enumerate(panels, start=1):
        fingerprint = panel.source.descriptor.fingerprint
        header.add_history(
            f"Input {index}: {fingerprint.size_bytes} bytes; weight {panel.weight:g}"
        )
        header.add_history(f"Input {index}: mtime_ns {fingerprint.modified_ns}; {panel.wcs_origin}")
        mask = panel.source.sky_mask_fingerprint
        if isinstance(mask, SourceFingerprint):
            header.add_history(
                f"Input {index}: sky mask {mask.size_bytes} bytes; mtime_ns {mask.modified_ns}"
            )
        elif mask is not None:
            header.add_history(f"Input {index}: project sky mask SHA-256")
            header.add_history(mask)
        correction = panel.correction
        if correction is not None:
            dx, dy = correction.shift
            offset, gradient_x, gradient_y = correction.background
            header.add_history(f"Input {index}: TAN shift ({dx:.8g}, {dy:.8g}) px")
            header.add_history(f"Input {index}: relative gain {correction.gain:.8g}")
            header.add_history(
                f"Input {index}: background {offset:.8g}, {gradient_x:.8g}, {gradient_y:.8g}"
            )
    return header


@dataclass(frozen=True, slots=True)
class _RenderedTile:
    tile: Tile
    rejected_coordinates: int
    contributions: NDArray[np.uint8] | None = None
    common_coverage: NDArray[np.bool_] | None = None


@dataclass(slots=True)
class _WorkingBudget:
    limit: int
    peak: int = 0

    def reserve(self, size: int) -> bool:
        if size > self.limit:
            return False
        self.peak = max(self.peak, size)
        return True


def _try_tile[P: _RasterPanel](
    region: Region,
    panels: Iterable[P],
    make_mapper: Callable[[], Callable[[P], _Coordinates]],
    budget: _WorkingBudget,
    context: JobContext,
    channels: int,
) -> _RenderedTile | None:
    count = region.width * region.height
    output_bytes = _TILE_FIXED_BYTES + count * (_OUTPUT_BYTES_PER_PIXEL + 64 * (channels - 1))
    if not budget.reserve(output_bytes):
        return None

    rejected = 0
    map_panel = None
    numerator = np.zeros((count, channels), dtype=np.float64)
    denominator = np.zeros(count, dtype=np.float64)
    weight_scale = np.zeros(count, dtype=np.float64)
    for panel in panels:
        context.check_cancelled()
        if map_panel is None:
            map_panel = make_mapper()
        correction = panel.correction
        px, py, usable = map_panel(panel)
        rejected += count - int(np.count_nonzero(usable))
        descriptor = panel.source.descriptor
        window = source_window(px, py, usable, descriptor.width, descriptor.height)
        if window is None:
            continue
        reserved_bytes = output_bytes + panel.source.tile_bytes(window.region)
        if not budget.reserve(reserved_bytes):
            return None
        indices, values = sample(panel.source.read_tile(window.region), window)
        if correction is not None:
            correction.apply(values, px[indices], py[indices], descriptor.width, descriptor.height)

        # Scale at each pixel so both very large and very small finite weights remain usable.
        scale = np.maximum(weight_scale[indices], panel.weight)
        previous = weight_scale[indices] / scale
        current = panel.weight / scale
        numerator[indices] = (
            numerator[indices] * previous[:, None]
            + values.reshape(indices.size, channels) * current[:, None]
        )
        denominator[indices] = denominator[indices] * previous + current
        weight_scale[indices] = scale

    valid = denominator > 0
    pixels = np.full(numerator.shape, np.nan, dtype=np.float32)
    channel_valid = valid[:, None]
    with np.errstate(over="ignore", invalid="ignore"):
        np.divide(numerator, denominator[:, None], out=pixels, where=channel_valid)
    if np.any(channel_valid & ~np.isfinite(pixels)):
        raise ValueError("A corrected mosaic sample exceeds the supported float32 range.")
    shape = (region.height, region.width)
    pixel_shape = shape if channels == 1 else (*shape, channels)
    return _RenderedTile(Tile(region, pixels.reshape(pixel_shape), valid.reshape(shape)), rejected)


def _split(region: Region) -> tuple[Region, Region]:
    if region.width == region.height == 1:
        raise ValueError(
            "The working byte budget cannot fit one output pixel and its source window."
        )
    if region.width >= region.height:
        left = region.width // 2
        return (
            Region(region.x, region.y, left, region.height),
            Region(region.x + left, region.y, region.width - left, region.height),
        )
    top = region.height // 2
    return (
        Region(region.x, region.y, region.width, top),
        Region(region.x, region.y + top, region.width, region.height - top),
    )


type _TileRenderer = Callable[[Region, _Scale, _WorkingBudget, JobContext], _RenderedTile | None]


def _fit_tile(
    region: Region,
    render_tile: _TileRenderer,
    budget: _WorkingBudget,
    context: JobContext,
    scale: _Scale,
) -> Iterator[_RenderedTile]:
    context.check_cancelled()
    rendered = render_tile(region, scale, budget, context)
    if rendered is not None:
        yield rendered
        return
    for smaller in _split(region):
        yield from _fit_tile(smaller, render_tile, budget, context, scale)


@dataclass(frozen=True, slots=True)
class _RasterPlan:
    render_tile: _TileRenderer
    panel_count: int
    channels: int
    header: fits.Header
    size: tuple[int, int]
    spec: RenderSpec
    output_wcs: WCS | None = None
    refinement: RefinementReport | None = None
    seam_width: float | None = None
    footprint_bytes: int = 0

    def tiles(
        self, width: int, height: int, budget: _WorkingBudget, context: JobContext
    ) -> Iterator[_RenderedTile]:
        if not budget.reserve(self.footprint_bytes):
            raise ValueError("The working byte budget cannot fit the panel footprints.")
        tile_budget = _WorkingBudget(budget.limit - self.footprint_bytes)
        scale = (self.size[0] / width, self.size[1] / height)
        step = self.spec.tile_size
        try:
            for y in range(0, height, step):
                for x in range(0, width, step):
                    region = Region(x, y, min(step, width - x), min(step, height - y))
                    yield from _fit_tile(region, self.render_tile, tile_budget, context, scale)
        finally:
            budget.reserve(self.footprint_bytes + tile_budget.peak)


@dataclass(frozen=True, slots=True)
class _PreparedMosaic:
    target: PanelGeometry
    panels: Sequence[_Panel]
    channels: int
    header: fits.Header
    size: tuple[int, int]
    spec: RenderSpec
    refinement: RefinementReport | None
    footprint_bytes: int

    def try_tile(
        self,
        region: Region,
        scale: _Scale,
        budget: _WorkingBudget,
        context: JobContext,
        *,
        origin: tuple[int, int] = (0, 0),
        sky_height: int | None = None,
    ) -> _RenderedTile | None:
        candidates: Iterable[_Panel] = self.panels
        if self.footprint_bytes or sky_height is not None:
            tile_bounds = raster_bounds(region, scale, origin)
            if sky_height is not None and not tile_bounds.intersects(
                raster_bounds(Region(0, 0, self.size[0], sky_height))
            ):
                candidates = ()
            elif self.footprint_bytes:
                candidates = (
                    panel
                    for panel in self.panels
                    if panel.footprint is None or panel.footprint.intersects(tile_bounds)
                )

        def make_mapper() -> Callable[[_Panel], _Coordinates]:
            x, y = raster_pixels(region, scale, origin)
            sky = TileSky.from_pixels(self.target, x, y)
            inside = None
            if sky_height is not None:
                inside = (
                    (x >= -0.5) & (x < self.size[0] - 0.5) & (y >= -0.5) & (y < sky_height - 0.5)
                )

            def locate(panel: _Panel) -> _Coordinates:
                shift = panel.correction.shift if panel.correction else (0.0, 0.0)
                px, py, usable = sky.in_panel(panel.geometry, shift)
                if inside is not None:
                    usable &= inside
                return px, py, usable

            return locate

        return _try_tile(region, candidates, make_mapper, budget, context, self.channels)

    def raster(self) -> _RasterPlan:
        return _RasterPlan(
            self.try_tile,
            len(self.panels),
            self.channels,
            self.header,
            self.size,
            self.spec,
            self.target.wcs,
            self.refinement,
            footprint_bytes=self.footprint_bytes,
        )


@contextmanager
def _prepare_mosaic(
    paths: Sequence[Path],
    spec: RenderSpec,
    destination: Path | None,
    *,
    weights: Sequence[float] | None,
    filter_name: str | None,
    assume_surface_brightness: bool,
    sky_masks: Mapping[int, SkyMask] | None,
    wcs_sidecars: Mapping[int, Path] | None,
    refinement: RefinementSpec | None,
    context: JobContext,
) -> Iterator[_PreparedMosaic]:
    if not paths:
        raise ValueError("Supply at least one FITS or TIFF panel.")
    weights = [1.0] * len(paths) if weights is None else weights
    if len(weights) != len(paths) or any(not isfinite(w) or w <= 0 for w in weights):
        raise ValueError("Supply one positive finite weight per input panel.")
    sky_masks = {} if sky_masks is None else sky_masks
    wcs_sidecars = {} if wcs_sidecars is None else wcs_sidecars
    if any(index not in range(len(paths)) for index in (*sky_masks, *wcs_sidecars)):
        raise ValueError("Sky mask and WCS sidecar indices must refer to input panels.")

    crop = spec.output_region()
    output = tan_output_wcs(spec.center, spec.size, spec.scale_arcsec, spec.rotation_deg, crop)
    target = PanelGeometry(output, ICRS())
    total = crop.width * crop.height
    is_tiff = destination is not None and destination.suffix.lower() in TIFF_SUFFIXES
    format_name = "TIFF" if is_tiff else "FITS"
    if destination is not None:
        if total * 5 > spec.max_output_bytes:
            raise ValueError(f"The {format_name} mosaic exceeds the configured output byte limit.")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"The output file already exists: {destination}")
    report = None
    with ExitStack() as inputs:
        panels = []
        for index, (path, weight) in enumerate(zip(paths, weights, strict=True)):
            context.check_cancelled()
            try:
                source = inputs.enter_context(
                    open_panel(
                        path,
                        max_tile_bytes=spec.max_working_bytes,
                        sky_mask=sky_masks.get(index),
                    )
                )
                descriptor = source.descriptor
                provenance = (
                    "TIFF description WCS"
                    if descriptor.wcs_provenance == "tiff-description"
                    else "primary WCS"
                )
                if index in wcs_sidecars:
                    from astromosaic.astrometry.solve import load_solution

                    geometry, provenance = load_solution(wcs_sidecars[index], source)
                else:
                    geometry = read_panel_geometry(
                        source.header, descriptor.width, descriptor.height
                    )
            except ValueError as error:
                raise ValueError(f"Input panel {index + 1}: {error}") from error
            panels.append(_Panel(source, geometry, weight, provenance))

        layout = panels[0].source.descriptor.channel_layout
        if any(panel.source.descriptor.channel_layout != layout for panel in panels):
            raise ValueError("Supply either all mono or all RGB panels.")
        channels = 3 if layout == "rgb" else 1
        if destination is not None:
            if channels == 3 and not is_tiff:
                raise ValueError("RGB mosaics require TIFF output.")
            if total * (4 * channels + 1) > spec.max_output_bytes:
                raise ValueError(
                    f"The {format_name} mosaic exceeds the configured output byte limit."
                )

        header = _export_header(output, panels, filter_name, assume_surface_brightness)
        if refinement is not None:
            report = refine_panels(
                [(panel.source, panel.geometry) for panel in panels],
                target,
                refinement,
                spec.max_working_bytes,
                context,
            )
            panels = [
                replace(panel, correction=correction)
                for panel, correction in zip(panels, report.corrections, strict=True)
            ]
            header = _export_header(output, panels, filter_name, assume_surface_brightness)
            if report.background is not None:
                header.add_history(
                    f"Anchored relative refinement: {report.background.model} background."
                )
        size = crop.width, crop.height
        footprint_bytes = 0
        if _footprint_reservation(len(panels), spec.max_working_bytes):
            for index, panel in enumerate(panels):
                context.check_cancelled()
                descriptor = panel.source.descriptor
                shift = panel.correction.shift if panel.correction else (0.0, 0.0)
                footprint = tan_footprint(
                    panel.geometry, target, (descriptor.width, descriptor.height), size, shift
                )
                if footprint is not None:
                    footprint_bytes += _FOOTPRINT_BYTES_PER_PANEL
                    panels[index] = replace(panel, footprint=footprint)
        yield _PreparedMosaic(target, panels, channels, header, size, spec, report, footprint_bytes)


def render_mosaic(
    paths: Sequence[Path],
    destination: Path,
    spec: RenderSpec,
    *,
    weights: Sequence[float] | None = None,
    filter_name: str | None = None,
    assume_surface_brightness: bool = False,
    sky_masks: Mapping[int, SkyMask] | None = None,
    wcs_sidecars: Mapping[int, Path] | None = None,
    refinement: RefinementSpec | None = None,
    context: JobContext = DEFAULT_JOB_CONTEXT,
) -> MosaicResult:
    """Reproject original linear samples and publish the finished mosaic on success."""
    with _prepare_mosaic(
        paths,
        spec,
        destination,
        weights=weights,
        filter_name=filter_name,
        assume_surface_brightness=assume_surface_brightness,
        sky_masks=sky_masks,
        wcs_sidecars=wcs_sidecars,
        refinement=refinement,
        context=context,
    ) as mosaic:
        return _write_raster(mosaic.raster(), destination, context)


def _write_raster(mosaic: _RasterPlan, destination: Path, context: JobContext) -> MosaicResult:
    width, height = mosaic.size
    total = width * height
    layers = mosaic.seam_width is not None
    max_bytes = mosaic.spec.max_output_bytes
    budget = _WorkingBudget(mosaic.spec.max_working_bytes)
    covered = completed = tiles = rejected = common = 0
    context.check_cancelled()
    if destination.suffix.lower() in TIFF_SUFFIXES:
        from astromosaic.io.tiff_export import open_tiff_mosaic

        writer_context = open_tiff_mosaic(
            destination,
            width,
            height,
            mosaic.channels,
            mosaic.header,
            max_bytes,
            layers=layers,
            publish_check=context.check_cancelled,
        )
    else:
        if mosaic.channels != 1:
            raise ValueError("RGB mosaics require TIFF output.")
        writer_context = open_fits_mosaic(
            destination,
            width,
            height,
            mosaic.header,
            max_bytes,
            layers=layers,
            publish_check=context.check_cancelled,
        )
    with writer_context as writer:
        for rendered in mosaic.tiles(width, height, budget, context):
            writer.write(rendered.tile, rendered.contributions)
            covered += int(np.count_nonzero(rendered.tile.valid))
            if rendered.common_coverage is not None:
                common += int(np.count_nonzero(rendered.common_coverage))
            completed += rendered.tile.region.width * rendered.tile.region.height
            rejected += rendered.rejected_coordinates
            tiles += 1
            del rendered
            if context.on_progress is not None:
                context.on_progress(completed, total)
        context.check_cancelled()
        if not covered:
            raise ValueError("The requested output grid has no valid input coverage.")

    return MosaicResult(
        width,
        height,
        covered,
        mosaic.panel_count,
        tiles,
        budget.peak,
        rejected,
        refinement=mosaic.refinement,
        common_pixels=common if layers else None,
    )


def _bounded_size(size: tuple[int, int], edge: int) -> tuple[int, int]:
    width, height = size
    longest = max(width, height, edge)
    return max(1, width * edge // longest), max(1, height * edge // longest)


def _preview_frame(
    mosaic: _RasterPlan, size: tuple[int, int], context: JobContext, completed: int, total: int
) -> PreviewFrame:
    width, height = size
    has_layers = mosaic.seam_width is not None
    frame_bytes = width * height * (4 * mosaic.channels + 1 + int(has_layers))
    budget = _WorkingBudget(mosaic.spec.max_working_bytes - frame_bytes)
    if budget.limit < _TILE_FIXED_BYTES:
        raise ValueError("The working byte budget cannot fit the preview and its render tiles.")
    context.check_cancelled()
    shape = (height, width)
    pixels = np.empty(shape if mosaic.channels == 1 else (*shape, mosaic.channels), np.float32)
    valid = np.empty(shape, np.bool_)
    common = np.empty(shape, np.bool_) if has_layers else None
    for rendered in mosaic.tiles(width, height, budget, context):
        tile = rendered.tile
        pixels[tile.region.slices] = tile.pixels
        valid[tile.region.slices] = tile.valid
        if common is not None and rendered.common_coverage is not None:
            common[tile.region.slices] = rendered.common_coverage
        completed += tile.region.width * tile.region.height
        del rendered, tile
        if context.on_progress is not None:
            context.on_progress(completed, total)
    context.check_cancelled()
    pixels.setflags(write=False)
    valid.setflags(write=False)
    if common is not None:
        common.setflags(write=False)
    return PreviewFrame(
        Tile(Region(0, 0, width, height), pixels, valid),
        mosaic.size,
        mosaic.output_wcs.deepcopy() if mosaic.output_wcs is not None else None,
        frame_bytes + budget.peak,
        common,
        mosaic.seam_width,
    )


def _preview_raster(
    mosaic: _RasterPlan, context: JobContext, on_proxy: Callable[[PreviewFrame], None] | None
) -> PreviewFrame:
    coarse = _bounded_size(mosaic.size, _PROXY_EDGE)
    size = _bounded_size(mosaic.size, _PREVIEW_EDGE)
    completed = coarse[0] * coarse[1] if on_proxy is not None and coarse != size else 0
    total = completed + size[0] * size[1]
    if on_proxy is not None and completed:
        proxy = _preview_frame(mosaic, coarse, context, 0, total)
        if proxy.tile.valid.any():
            on_proxy(proxy)
        del proxy
    return _preview_frame(mosaic, size, context, completed, total)


def preview_mosaic(
    paths: Sequence[Path],
    spec: RenderSpec,
    *,
    weights: Sequence[float] | None = None,
    filter_name: str | None = None,
    assume_surface_brightness: bool = False,
    sky_masks: Mapping[int, SkyMask] | None = None,
    wcs_sidecars: Mapping[int, Path] | None = None,
    refinement: RefinementSpec | None = None,
    context: JobContext = DEFAULT_JOB_CONTEXT,
    on_proxy: Callable[[PreviewFrame], None] | None = None,
) -> PreviewFrame:
    """Sample the export grid at preview raster centers without opening an output file."""
    with _prepare_mosaic(
        paths,
        spec,
        None,
        weights=weights,
        filter_name=filter_name,
        assume_surface_brightness=assume_surface_brightness,
        sky_masks=sky_masks,
        wcs_sidecars=wcs_sidecars,
        refinement=refinement,
        context=context,
    ) as mosaic:
        return _preview_raster(mosaic.raster(), context, on_proxy)
