"""Render an ICRS TAN FITS mosaic with a bounded, synchronous tile loop."""

from collections.abc import Callable, Iterator, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from importlib.metadata import version
from math import isfinite
from pathlib import Path

import numpy as np
from astropy import units as u
from astropy.coordinates import ICRS
from astropy.io import fits
from astropy.wcs import WCS

from astromosaic.core import Region, Tile
from astromosaic.geometry import PanelGeometry, TileSky, read_panel_geometry, tan_output_wcs
from astromosaic.io.fits import FitsTileSource, fits_tile_bytes, open_fits_panel
from astromosaic.io.fits_export import open_fits_mosaic
from astromosaic.resampling import sample, source_window

MIB = 1024**2
DEFAULT_WORKING_BYTES = 64 * MIB
DEFAULT_OUTPUT_BYTES = 2048 * MIB
DEFAULT_TILE_SIZE = 128
# Include live WCS/frame and inverse-iteration arrays, blend buffers, and endian conversion.
_OUTPUT_BYTES_PER_PIXEL = 1024
_TILE_FIXED_BYTES = 64 * 1024


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


class MosaicCancelled(RuntimeError):
    """The job stopped before publishing a FITS file."""


@dataclass(frozen=True, slots=True)
class JobContext:
    is_cancelled: Callable[[], bool] | None = None
    on_progress: Callable[[int, int], None] | None = None

    def check_cancelled(self) -> None:
        if self.is_cancelled is not None and self.is_cancelled():
            raise MosaicCancelled("The mosaic job was cancelled.")


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


@dataclass(frozen=True, slots=True)
class _Panel:
    source: FitsTileSource
    geometry: PanelGeometry
    weight: float


def _export_header(
    target: WCS, panels: Sequence[_Panel], declared_filter: str | None, assume_brightness: bool
) -> fits.Header:
    descriptors = [panel.source.descriptor for panel in panels]
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
        len(units) != len(panels)
        or not any(units[0].is_equivalent(candidate) for candidate in brightness_units)
    ):
        raise ValueError("Expected a surface-brightness BUNIT or --assume-surface-brightness.")

    header = target.to_header()
    header["FILTER"] = band
    if labels:
        header["BUNIT"] = labels[0]
    header.add_history(f"AstroMosaic {version('astromosaic')}: CPU ICRS TAN reprojection.")
    header.add_history("Bilinear valid support; normalized panel weights; linear float32.")
    if assume_brightness:
        header.add_history("User declared a common surface-brightness scale for all panels.")
    if declared_filter:
        header.add_history("User provided FILTER for panels with missing filter metadata.")
    for index, panel in enumerate(panels, start=1):
        fingerprint = panel.source.descriptor.fingerprint
        header.add_history(
            f"Input {index}: {fingerprint.size_bytes} bytes; weight {panel.weight:g}"
        )
        header.add_history(f"Input {index}: mtime_ns {fingerprint.modified_ns}; primary WCS")
    return header


@dataclass(frozen=True, slots=True)
class _RenderedTile:
    tile: Tile
    rejected_coordinates: int


@dataclass(slots=True)
class _WorkingBudget:
    limit: int
    peak: int = 0

    def reserve(self, size: int) -> bool:
        if size > self.limit:
            return False
        self.peak = max(self.peak, size)
        return True


def _try_tile(
    region: Region,
    target: PanelGeometry,
    panels: Sequence[_Panel],
    budget: _WorkingBudget,
    context: JobContext,
) -> _RenderedTile | None:
    count = region.width * region.height
    output_bytes = _TILE_FIXED_BYTES + count * _OUTPUT_BYTES_PER_PIXEL
    if not budget.reserve(output_bytes):
        return None

    rejected = 0
    sky = TileSky.from_output(target, region)
    numerator = np.zeros(count, dtype=np.float64)
    denominator = np.zeros_like(numerator)
    weight_scale = np.zeros_like(numerator)
    for panel in panels:
        context.check_cancelled()
        px, py, usable = sky.in_panel(panel.geometry)
        rejected += count - int(np.count_nonzero(usable))
        descriptor = panel.source.descriptor
        window = source_window(px, py, usable, descriptor.width, descriptor.height)
        if window is None:
            continue
        reserved_bytes = output_bytes + fits_tile_bytes(window.region)
        if not budget.reserve(reserved_bytes):
            return None
        indices, values = sample(panel.source.read_tile(window.region), window)

        # Scale at each pixel so both very large and very small finite weights remain usable.
        scale = np.maximum(weight_scale[indices], panel.weight)
        previous = weight_scale[indices] / scale
        current = panel.weight / scale
        numerator[indices] = numerator[indices] * previous + values * current
        denominator[indices] = denominator[indices] * previous + current
        weight_scale[indices] = scale

    valid = denominator > 0
    pixels = np.full(count, np.nan, dtype=np.float32)
    np.divide(numerator, denominator, out=pixels, where=valid)
    shape = (region.height, region.width)
    return _RenderedTile(Tile(region, pixels.reshape(shape), valid.reshape(shape)), rejected)


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


def _fit_tile(
    region: Region,
    target: PanelGeometry,
    panels: Sequence[_Panel],
    budget: _WorkingBudget,
    context: JobContext,
) -> Iterator[_RenderedTile]:
    context.check_cancelled()
    rendered = _try_tile(region, target, panels, budget, context)
    if rendered is not None:
        yield rendered
        return
    for smaller in _split(region):
        yield from _fit_tile(smaller, target, panels, budget, context)


def render_mosaic(
    paths: Sequence[Path],
    destination: Path,
    spec: RenderSpec,
    *,
    weights: Sequence[float] | None = None,
    filter_name: str | None = None,
    assume_surface_brightness: bool = False,
    context: JobContext = JobContext(),
) -> MosaicResult:
    """Reproject original FITS samples and publish the finished mosaic on success."""
    if not paths:
        raise ValueError("Supply at least one FITS panel.")
    weights = [1.0] * len(paths) if weights is None else weights
    if len(weights) != len(paths) or any(not isfinite(w) or w <= 0 for w in weights):
        raise ValueError("Supply one positive finite weight per input panel.")

    crop = spec.output_region()
    output = tan_output_wcs(spec.center, spec.size, spec.scale_arcsec, spec.rotation_deg, crop)
    target = PanelGeometry(output, ICRS())
    budget = _WorkingBudget(spec.max_working_bytes)
    width, height = crop.width, crop.height
    total = width * height
    covered = completed = tiles = rejected = 0
    with ExitStack() as inputs:
        panels = []
        for index, (path, weight) in enumerate(zip(paths, weights, strict=True), start=1):
            context.check_cancelled()
            try:
                source = inputs.enter_context(
                    open_fits_panel(path, max_tile_bytes=spec.max_working_bytes, memmap=False)
                )
                panel = source.descriptor
                geometry = read_panel_geometry(source.header, panel.width, panel.height)
            except ValueError as error:
                raise ValueError(f"Input panel {index}: {error}") from error
            panels.append(_Panel(source, geometry, weight))

        header = _export_header(output, panels, filter_name, assume_surface_brightness)
        with open_fits_mosaic(destination, width, height, header, spec.max_output_bytes) as writer:
            step = spec.tile_size
            for y in range(0, height, step):
                for x in range(0, width, step):
                    region = Region(x, y, min(step, width - x), min(step, height - y))
                    for rendered in _fit_tile(region, target, panels, budget, context):
                        writer.write(rendered.tile)
                        covered += int(np.count_nonzero(rendered.tile.valid))
                        completed += rendered.tile.region.width * rendered.tile.region.height
                        rejected += rendered.rejected_coordinates
                        tiles += 1
                        del rendered
                        if context.on_progress is not None:
                            context.on_progress(completed, total)
            context.check_cancelled()
            if not covered:
                raise ValueError("The requested output grid has no valid input coverage.")

    return MosaicResult(width, height, covered, len(panels), tiles, budget.peak, rejected)
