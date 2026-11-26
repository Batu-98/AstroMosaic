"""Render an ICRS sky mosaic with a bounded, synchronous tile loop."""

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from functools import partial
from importlib.metadata import version
from math import isfinite, isqrt
from pathlib import Path
from typing import Literal, Protocol

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
from astromosaic.core.masks import SKY, SourceMask
from astromosaic.geometry import (
    PanelGeometry,
    SkyProjection,
    TileSky,
    raster_pixels,
    read_panel_geometry,
    sky_output_wcs,
)
from astromosaic.geometry.footprint import PixelBounds, raster_bounds, tan_footprint, zea_footprint
from astromosaic.io import TIFF_SUFFIXES, XISF_SUFFIX, PanelSource, SkyMask, open_panel
from astromosaic.io.fits_export import open_fits_mosaic, validate_fits_output_suffix
from astromosaic.photometry import PanelCorrection
from astromosaic.photometry.photo import PhotoTone, encode_photo_tile, preview_levels
from astromosaic.pipeline.framing import FRAME_LOCKS, FrameLock, fit_preview_grid
from astromosaic.pipeline.photo_fit import PhotoPanel, PhotoReport
from astromosaic.pipeline.photo_preparation import PhotoInputs as PhotoInputs
from astromosaic.pipeline.photo_preparation import PhotoPreparation, SkyRenderIntent
from astromosaic.pipeline.refinement import (
    RefinementReport,
    RefinementSpec,
    refine_panels,
    validate_refinement_inputs,
)
from astromosaic.resampling import PreviewInterpolator, sample, sample_source_points, source_window

MIB = 1024**2
DEFAULT_WORKING_BYTES = 64 * MIB
DEFAULT_OUTPUT_BYTES = 2048 * MIB
DEFAULT_TILE_SIZE = 128
DEFAULT_SKY_BAND = "Unspecified"
# Include live WCS/frame and inverse-iteration arrays, blend buffers, and endian conversion.
_OUTPUT_BYTES_PER_PIXEL = 1024
_TILE_FIXED_BYTES = 64 * 1024
_FOOTPRINT_BYTES_PER_PANEL = 256
_PROXY_EDGE = 160
_PREVIEW_EDGE = 512
MAX_OVERVIEW_EDGE = 1536
_OVERVIEW_SAMPLES = 1024**2
MAX_DETAIL_PIXELS = 1024**2


type SkyCalibrationRequirement = Literal["filter", "brightness"]


class SkyCalibrationError(ValueError):
    """Identify a sky metadata problem that can be addressed in project settings."""

    def __init__(self, requirement: SkyCalibrationRequirement, message: str) -> None:
        super().__init__(message)
        self.requirement = requirement


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
    projection: SkyProjection = "TAN"

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

    def output_wcs(self) -> WCS:
        return sky_output_wcs(
            self.center,
            self.size,
            self.scale_arcsec,
            self.rotation_deg,
            self.output_region(),
            projection=self.projection,
        )


@dataclass(frozen=True, slots=True)
class SkyPreflight:
    panels: int
    width: int
    height: int
    channels: int


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
    photo: PhotoReport | None = None


@dataclass(frozen=True, slots=True)
class PhotoExport:
    tone: PhotoTone | None
    auto_frame: bool = False
    frame_locks: frozenset[FrameLock] = frozenset()


@dataclass(frozen=True, slots=True, eq=False)
class PreviewFrame:
    """Read-only linear raster over the preview grid."""

    tile: Tile
    output_size: tuple[int, int]
    output_wcs: WCS | None
    peak_reserved_bytes: int
    common_coverage: NDArray[np.bool_] | None = None
    seam_width: float | None = None
    fitted_grid: RenderSpec | None = None
    visual_only: bool = False
    suggested_crop: Region | None = None
    suggested_rotation: float | None = None
    tone_levels: tuple[float, float] | None = None
    photo: PhotoReport | None = None


class _RasterPanel(Protocol):
    @property
    def name(self) -> str: ...
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
    name: str
    source: PanelSource
    geometry: PanelGeometry
    weight: float
    wcs_origin: str = "primary WCS"
    correction: PanelCorrection | None = None
    footprint: PixelBounds | None = None
    rms_arcsec: float | None = None


def _footprint_reservation(panels: int, working_bytes: int) -> int:
    reserved = panels * _FOOTPRINT_BYTES_PER_PANEL
    # Preserve the sampling budget on small jobs. Footprint selection is optional.
    return reserved if panels > 1 and reserved <= working_bytes // 32 else 0


def sky_band_label(panel_filter: str | None, common_filter: str | None) -> str:
    """Resolve the grouping label for a sky panel."""
    return panel_filter or (common_filter or "").strip() or DEFAULT_SKY_BAND


def _common_band(
    sources: Sequence[PanelSource],
    declared_filter: str | None,
    filter_overrides: Mapping[int, str] | None = None,
) -> tuple[str, bool]:
    declared_filter = (declared_filter or "").strip() or None
    overrides = filter_overrides or {}
    filters = [
        overrides.get(index, source.descriptor.filter_name) for index, source in enumerate(sources)
    ]
    bands = [sky_band_label(label, declared_filter) for label in filters]
    band = declared_filter or bands[0]
    if any(label != band for label in bands):
        raise SkyCalibrationError("filter", "Expected a common FILTER across the selected panels.")
    return band, not all(filters)


def _set_calibration(
    header: fits.Header,
    sources: Sequence[PanelSource],
    declared_filter: str | None,
    assume_brightness: bool,
    filter_overrides: Mapping[int, str] | None = None,
    *,
    paths: Sequence[Path] | None = None,
) -> None:
    descriptors = [source.descriptor for source in sources]
    band, missing_filters = _common_band(sources, declared_filter, filter_overrides)
    for index, panel in enumerate(descriptors):
        name = paths[index].name if paths is not None else f"Input panel {index + 1}"
        metadata = sources[index].photo_metadata
        if panel.icc_encoding == "srgb" or (
            panel.icc_encoding is None and metadata is not None
            and metadata.uint16_rgb and metadata.exif_srgb
        ):
            raise ValueError(
                f"{name} uses sRGB-encoded samples. Scientific rendering requires linear "
                "panels with a common brightness scale."
            )
        if panel.icc_encoding == "unsupported":
            raise ValueError(
                f"{name} has an unsupported TIFF ICC profile. Supply a linear, "
                "color-managed copy with compatible brightness units."
            )
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
        raise SkyCalibrationError(
            "brightness", "Expected a surface-brightness BUNIT or --assume-surface-brightness."
        )

    header["FILTER"] = band
    if labels:
        header["BUNIT"] = labels[0]
    if assume_brightness:
        header.add_history("User declared a common surface-brightness scale for all panels.")
    if missing_filters:
        header.add_history(f"Used {band} for panels with missing filter metadata.")


def _export_header(
    target: WCS,
    panels: Sequence[_Panel],
    declared_filter: str | None,
    assume_brightness: bool,
    filter_overrides: Mapping[int, str],
    paths: Sequence[Path],
    *,
    photo: PhotoReport | None = None,
) -> fits.Header:
    header = target.to_header()
    sources = [panel.source for panel in panels]
    if photo:
        header["FILTER"], _ = _common_band(sources, declared_filter, filter_overrides)
        header["AMINTENT"] = ("PHOTO", "sRGB photo export")
    else:
        _set_calibration(
            header, sources, declared_filter, assume_brightness, filter_overrides, paths=paths
        )
    projection = target.wcs.ctype[0][5:]
    header.add_history(f"AstroMosaic {version('astromosaic')}: CPU ICRS {projection} reprojection.")
    if photo:
        header.add_history("Linear sRGB working space; bilinear valid support; normalized weights.")
        header.add_history("Encoded sRGB2014 RGB UInt16 with binary associated alpha.")
        header.add_history(
            f"Photo exposure {photo.requested_exposure}; brightness {photo.requested_brightness}."
        )
        if photo.reference_panel is not None:
            header.add_history(f"Photo reference: input {photo.reference_panel}.")
    else:
        header.add_history("Bilinear valid support; normalized panel weights; linear float32.")
    for index, panel in enumerate(panels, start=1):
        fingerprint = panel.source.descriptor.fingerprint
        header.add_history(
            f"Input {index}: {fingerprint.size_bytes} bytes; weight {panel.weight:g}"
        )
        header.add_history(f"Input {index}: mtime_ns {fingerprint.modified_ns}; {panel.wcs_origin}")
        if photo is not None:
            effective = photo.panels[index - 1]
            header.add_history(f"Input {index}: {effective.color_method}; {effective.color_origin}")
            if effective.profile_preset is not None:
                header.add_history(f"Input {index}: {effective.profile_preset} preset.")
            if (profile := effective.profile_sha256) is not None:
                header.add_history(f"Input {index}: effective ICC SHA-256")
                header.add_history(profile)
            header.add_history(
                f"Input {index}: exposure {effective.exposure_method}; gain {effective.exposure_gain:.9g}"
            )
            if effective.exposure_detail:
                header.add_history(effective.exposure_detail)
            if photo.requested_brightness != "off":
                fit = effective.brightness
                header.add_history(f"Input {index}: brightness {fit.method}; peer {effective.overlap_reference}")
                header.add_history(f"Gain {fit.gain:.9g}; affine offset {fit.offset:.9g}.")
                header.add_history(f"Fit samples {fit.training_samples}; held out {fit.held_out_samples}.")
                if fit.before_p95 is not None and fit.after_p95 is not None:
                    header.add_history(f"Held-out RGB P95 {fit.before_p95:.8g} to {fit.after_p95:.8g}.")
                if fit.detail:
                    header.add_history(fit.detail)
        if index - 1 in filter_overrides:
            original = panel.source.descriptor.filter_name or "(missing)"
            header.add_history(
                f"Input {index}: FILTER {original} assigned as {filter_overrides[index - 1]}."
            )
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
            header.add_history(f"Input {index}: {projection} shift ({dx:.8g}, {dy:.8g}) px")
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
    interpolate: PreviewInterpolator | None = None,
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
        try:
            sampled = (
                sample_source_points(panel.source, window, interpolate)
                if interpolate is not None else None
            )
            if sampled is None:
                reserved_bytes = output_bytes + panel.source.tile_bytes(window.region)
                if not budget.reserve(reserved_bytes):
                    return None
                tile = panel.source.read_tile(window.region)
                sampled = sample(tile, window, interpolate=interpolate)
                del tile
        except (OSError, ValueError) as error:
            raise ValueError(f"{panel.name}: {error}") from error
        indices, values = sampled
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
    profile_bytes: int = 0
    photo: PhotoReport | None = None

    def peak_reserved_bytes(self, raster_peak: int) -> int:
        if self.photo is not None:
            return max(raster_peak, self.profile_bytes + self.photo.peak_fit_bytes)
        return raster_peak

    def tiles(
        self, width: int, height: int, budget: _WorkingBudget, context: JobContext,
        *, window: Region | None = None,
    ) -> Iterator[_RenderedTile]:
        fixed_bytes = self.footprint_bytes + self.profile_bytes
        if not budget.reserve(fixed_bytes):
            raise ValueError("The working byte budget cannot fit the panel footprints and profiles.")
        tile_budget = _WorkingBudget(budget.limit - fixed_bytes)
        bounds = Region(0, 0, width, height) if window is None else window
        scale = (self.size[0] / width, self.size[1] / height) if window is None else (1.0, 1.0)
        step = self.spec.tile_size
        right, bottom = bounds.x + bounds.width, bounds.y + bounds.height
        try:
            for y in range(bounds.y, bottom, step):
                for x in range(bounds.x, right, step):
                    region = Region(x, y, min(step, right - x), min(step, bottom - y))
                    yield from _fit_tile(region, self.render_tile, tile_budget, context, scale)
        finally:
            budget.reserve(fixed_bytes + tile_budget.peak)


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
    visual_only: bool = False
    suggested_crop: Region | None = None
    suggested_rotation: float | None = None
    profile_bytes: int = 0
    photo: PhotoReport | None = None

    def try_tile(
        self,
        region: Region,
        scale: _Scale,
        budget: _WorkingBudget,
        context: JobContext,
        *,
        origin: tuple[int, int] = (0, 0),
        sky_height: int | None = None,
        interpolate: PreviewInterpolator | None = None,
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

        return _try_tile(region, candidates, make_mapper, budget, context, self.channels, interpolate)

    def raster(self, interpolate: PreviewInterpolator | None = None) -> _RasterPlan:
        render_tile = self.try_tile if interpolate is None else partial(
            self.try_tile, interpolate=interpolate
        )
        return _RasterPlan(
            render_tile,
            len(self.panels),
            self.channels,
            self.header,
            self.size,
            self.spec,
            self.target.wcs,
            self.refinement,
            footprint_bytes=self.footprint_bytes,
            profile_bytes=self.profile_bytes,
            photo=self.photo,
        )


def _output_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TIFF_SUFFIXES:
        return "TIFF"
    if suffix == XISF_SUFFIX:
        return "XISF"
    validate_fits_output_suffix(path)
    return "FITS"


@dataclass(frozen=True, slots=True)
class _OpenedSky:
    panels: list[_Panel]
    crop: Region
    channels: int
    photo_preparation: PhotoPreparation
    photo_panels: list[PhotoPanel]


@contextmanager
def _open_sky_mosaic(
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
    filter_overrides: Mapping[int, str] | None = None,
    auto_frame: bool = False,
    intent: SkyRenderIntent = "scientific",
    photo_inputs: PhotoInputs | None = None,
) -> Iterator[_OpenedSky]:
    if not paths:
        raise ValueError("Supply at least one FITS, TIFF, or XISF panel.")
    weights = [1.0] * len(paths) if weights is None else weights
    if len(weights) != len(paths) or any(not isfinite(w) or w <= 0 for w in weights):
        raise ValueError("Supply one positive finite weight per input panel.")
    sky_masks = {} if sky_masks is None else sky_masks
    wcs_sidecars = {} if wcs_sidecars is None else wcs_sidecars
    filter_overrides = {} if filter_overrides is None else filter_overrides
    if any(index not in range(len(paths)) for index in (*sky_masks, *wcs_sidecars)):
        raise ValueError("Sky mask and WCS sidecar indices must refer to input panels.")
    if any(index not in range(len(paths)) for index in filter_overrides):
        raise ValueError("Filter override indices must refer to input panels.")

    crop = spec.output_region()
    photo = intent == "photo"
    photo_preparation = PhotoPreparation(
        photo_inputs, panel_count=len(paths), intent=intent, max_working_bytes=spec.max_working_bytes
    )
    visual_allowed = photo_preparation.visual_allowed
    format_name = None
    if destination is not None:
        if photo and destination.suffix.lower() not in TIFF_SUFFIXES:
            raise ValueError("Photo mosaic output requires a .tif or .tiff destination.")
        format_name = _output_format(destination)
        if not photo and crop.width * crop.height * 5 > spec.max_output_bytes:
            raise ValueError(f"The {format_name} mosaic exceeds the configured output byte limit.")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"The output file already exists: {destination}")
    with ExitStack() as inputs:
        panels = []
        for index, (path, weight) in enumerate(zip(paths, weights, strict=True)):
            context.check_cancelled()
            detail = ""
            rms_arcsec = None
            try:
                source = inputs.enter_context(
                    open_panel(
                        path,
                        max_tile_bytes=spec.max_working_bytes,
                        sky_mask=sky_masks.get(index),
                        keep_icc=visual_allowed,
                    )
                )
                descriptor = source.descriptor
                photo_preparation.reserve_embedded_profile(source)
                provenance = {
                    "tiff-description": "TIFF description WCS",
                    "xisf-fits-keywords": "XISF FITS keywords",
                    None: "primary WCS",
                    "primary-header": "primary WCS",
                }[descriptor.wcs_provenance]
                if visual_allowed:
                    detail = " Run Plate Solve for this panel."
                if index in wcs_sidecars:
                    from astromosaic.astrometry.solve import load_solution, read_solution_quality

                    sidecar = wcs_sidecars[index]
                    geometry, provenance = load_solution(sidecar, source)
                    if refinement is not None and refinement.max_shift_px is None:
                        quality = read_solution_quality(sidecar)
                        rms = quality.get("rms_arcsec")
                        if (
                            quality.get("grade") == "catalog-validated"
                            and isinstance(rms, int | float) and not isinstance(rms, bool)
                            and isfinite(rms) and rms >= 0
                        ):
                            rms_arcsec = float(rms)
                else:
                    geometry = read_panel_geometry(
                        source.header, descriptor.width, descriptor.height
                    )
            except ValueError as error:
                name = f" ({path.name})" if visual_allowed or auto_frame else ""
                raise ValueError(f"Input panel {index + 1}{name}: {error}{detail}") from error
            panels.append(
                _Panel(path.name, source, geometry, weight, provenance, rms_arcsec=rms_arcsec)
            )

        photo_panels = photo_preparation.prepare_panels(
            ((path, panel.source, panel.geometry) for path, panel in zip(paths, panels, strict=True)),
            context,
            refinement_requested=refinement is not None,
        )
        layout = panels[0].source.descriptor.channel_layout
        if any(panel.source.descriptor.channel_layout != layout for panel in panels):
            raise ValueError("Supply either all mono or all RGB panels.")
        channels = 3 if layout == "rgb" else 1
        if destination is not None and not photo:
            if channels == 3 and format_name == "FITS":
                raise ValueError("RGB mosaics require TIFF or XISF output.")
            if crop.width * crop.height * (4 * channels + 1) > spec.max_output_bytes:
                raise ValueError(
                    f"The {format_name} mosaic exceeds the configured output byte limit."
                )
        yield _OpenedSky(panels, crop, channels, photo_preparation, photo_panels)


def preflight_sky_mosaic(
    paths: Sequence[Path],
    spec: RenderSpec,
    destination: Path | None = None,
    *,
    weights: Sequence[float] | None = None,
    filter_name: str | None = None,
    assume_surface_brightness: bool = False,
    sky_masks: Mapping[int, SkyMask] | None = None,
    wcs_sidecars: Mapping[int, Path] | None = None,
    refinement: RefinementSpec | None = None,
    context: JobContext = DEFAULT_JOB_CONTEXT,
    filter_overrides: Mapping[int, str] | None = None,
    photo_inputs: PhotoInputs | None = None,
) -> SkyPreflight:
    """Check scientific sky metadata and refinement eligibility without preparing tiles."""
    with _open_sky_mosaic(
        paths,
        spec,
        destination,
        weights=weights,
        filter_name=filter_name,
        assume_surface_brightness=assume_surface_brightness,
        sky_masks=sky_masks,
        wcs_sidecars=wcs_sidecars,
        refinement=None,
        context=context,
        filter_overrides=filter_overrides,
        photo_inputs=photo_inputs,
    ) as sky:
        # Check that the calibrated metadata can be represented in the export header.
        _export_header(
            spec.output_wcs(),
            sky.panels,
            filter_name,
            assume_surface_brightness,
            filter_overrides or {},
            paths,
        )
        if refinement is not None:
            validate_refinement_inputs([panel.source for panel in sky.panels])
        context.check_cancelled()
        return SkyPreflight(len(sky.panels), sky.crop.width, sky.crop.height, sky.channels)


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
    filter_overrides: Mapping[int, str] | None = None,
    auto_frame: bool = False,
    intent: SkyRenderIntent = "scientific",
    frame_locks: frozenset[FrameLock] = frozenset(),
    inspect_crop: bool = False,
    photo_inputs: PhotoInputs | None = None,
) -> Iterator[_PreparedMosaic]:
    photo = intent == "photo"
    filter_overrides = filter_overrides if filter_overrides is not None else {}
    sky_masks = sky_masks if sky_masks is not None else {}
    with _open_sky_mosaic(
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
        filter_overrides=filter_overrides,
        auto_frame=auto_frame,
        intent=intent,
        photo_inputs=photo_inputs,
    ) as sky:
        panels = sky.panels
        crop = sky.crop
        channels = sky.channels
        photo_preparation = sky.photo_preparation
        photo_panels = sky.photo_panels
        report = None
        photo_report = None
        framing = None
        if auto_frame or inspect_crop:
            regions = []
            for index, (path, panel) in enumerate(zip(paths, panels, strict=True)):
                context.check_cancelled()
                mask = sky_masks.get(index)
                descriptor = panel.source.descriptor
                region = (
                    mask.bounds(SKY)
                    if isinstance(mask, SourceMask)
                    else Region(0, 0, descriptor.width, descriptor.height)
                )
                if region is None:
                    raise ValueError(
                        f"{path.name} has no sky in its saved mask. Edit the sky mask."
                    )
                regions.append((path, panel.geometry, region))
            locks = FRAME_LOCKS - {"crop"} if inspect_crop else frame_locks
            framing = fit_preview_grid(spec, regions, context, locks=locks)
            if auto_frame:
                spec = framing.grid
            crop = spec.output_region()
        target = PanelGeometry(spec.output_wcs(), ICRS())

        if photo and crop.width * crop.height * 8 > spec.max_output_bytes:
            raise ValueError("The photo TIFF exceeds the configured output byte limit.")
        if photo_panels:
            corrections, photo_report = photo_preparation.fit(photo_panels, spec, target, context)
            panels = [
                replace(panel, source=item.source, correction=correction)
                for panel, item, correction in zip(panels, photo_panels, corrections, strict=True)
            ]
        if photo_panels and not photo:
            band, _ = _common_band(
                [panel.source for panel in panels], filter_name, filter_overrides
            )
            header = target.wcs.to_header()
            header["FILTER"] = band
        else:
            header = _export_header(
                target.wcs,
                panels,
                filter_name,
                assume_surface_brightness,
                filter_overrides,
                paths,
                photo=photo_report,
            )
        if refinement is not None:
            radius = refinement.resolve_radius(
                [panel.rms_arcsec for panel in panels], spec.scale_arcsec
            )
            report = refine_panels(
                [(panel.source, panel.geometry) for panel in panels],
                target,
                replace(refinement, max_shift_px=radius),
                spec.max_working_bytes,
                context,
            )
            panels = [
                replace(panel, correction=correction)
                for panel, correction in zip(panels, report.corrections, strict=True)
            ]
            header = _export_header(
                target.wcs, panels, filter_name, assume_surface_brightness, filter_overrides, paths
            )
            if report.background is not None:
                header.add_history(
                    f"Anchored relative refinement: {report.background.model} background."
                )
            if refinement.max_shift_px is None:
                header.add_history(f"Automatic stellar match radius {radius:.6g} output pixels.")
        size = crop.width, crop.height
        footprint_bytes = 0
        if _footprint_reservation(len(panels), spec.max_working_bytes):
            panel_footprint = tan_footprint if spec.projection == "TAN" else zea_footprint
            for index, panel in enumerate(panels):
                context.check_cancelled()
                descriptor = panel.source.descriptor
                shift = panel.correction.shift if panel.correction else (0.0, 0.0)
                footprint = panel_footprint(
                    panel.geometry, target, (descriptor.width, descriptor.height), size, shift
                )
                if footprint is not None:
                    footprint_bytes += _FOOTPRINT_BYTES_PER_PANEL
                    panels[index] = replace(panel, footprint=footprint)
        yield _PreparedMosaic(
            target, panels, channels, header, size, spec, report, footprint_bytes, bool(photo_panels),
            framing.suggested_crop if framing is not None else None,
            framing.suggested_rotation if framing is not None else None,
            photo_preparation.profile_bytes, photo_report,
        )


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
    filter_overrides: Mapping[int, str] | None = None,
    photo: PhotoExport | None = None,
    photo_inputs: PhotoInputs | None = None,
) -> MosaicResult:
    """Reproject original samples and publish the finished mosaic on success."""
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
        filter_overrides=filter_overrides,
        auto_frame=photo.auto_frame if photo is not None else False,
        intent="photo" if photo is not None else "scientific",
        frame_locks=photo.frame_locks if photo is not None else frozenset(),
        photo_inputs=photo_inputs,
    ) as mosaic:
        raster = mosaic.raster()
        if photo is not None:
            photo = _resolve_photo(raster, photo, context)
        return _write_raster(raster, destination, context, photo=photo)


def _resolve_photo(raster: _RasterPlan, photo: PhotoExport, context: JobContext) -> PhotoExport:
    tone = photo.tone
    if tone is not None:
        levels = tone.levels
        if levels is None:
            quiet = replace(context, on_progress=None)
            preview = _preview_raster(raster, quiet, None).tile
            if not preview.valid.any():
                raise ValueError(
                    "The preview grid has no covered samples for the photo tone. "
                    "Adjust the sky grid or use Preserve Tone."
                )
            levels = preview_levels(preview.pixels[preview.valid].astype(np.float64))
            photo = replace(photo, tone=replace(tone, levels=levels))
        raster.header["PHOTOTON"] = "preview"
        raster.header["PHOTOBLK"], raster.header["PHOTOWHT"] = levels
        raster.header["PHOTOMID"] = tone.midtones
    else:
        raster.header["PHOTOTON"] = "preserve"
    return photo


def _write_raster(
    mosaic: _RasterPlan,
    destination: Path,
    context: JobContext,
    *,
    photo: PhotoExport | None = None,
) -> MosaicResult:
    width, height = mosaic.size
    total = width * height
    layers = mosaic.seam_width is not None
    max_bytes = mosaic.spec.max_output_bytes
    budget = _WorkingBudget(mosaic.spec.max_working_bytes)
    covered = completed = tiles = rejected = common = 0
    context.check_cancelled()
    format_name = _output_format(destination)
    if format_name == "TIFF":
        from astromosaic.io.tiff_export import open_tiff_mosaic

        writer_context = open_tiff_mosaic(
            destination,
            width,
            height,
            mosaic.channels,
            mosaic.header,
            max_bytes,
            layers=layers,
            photo=photo is not None,
            publish_check=context.check_cancelled,
        )
    elif format_name == "FITS":
        if mosaic.channels != 1:
            raise ValueError("RGB mosaics require TIFF or XISF output.")
        writer_context = open_fits_mosaic(
            destination,
            width,
            height,
            mosaic.header,
            max_bytes,
            layers=layers,
            publish_check=context.check_cancelled,
        )
    else:
        from astromosaic.io.xisf_export import open_xisf_mosaic

        writer_context = open_xisf_mosaic(
            destination,
            width,
            height,
            mosaic.channels,
            mosaic.header,
            max_bytes,
            layers=layers,
            publish_check=context.check_cancelled,
        )
    with writer_context as writer:
        for rendered in mosaic.tiles(width, height, budget, context):
            if photo is not None:
                encode_photo_tile(rendered.tile, photo.tone)
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
        mosaic.peak_reserved_bytes(budget.peak),
        rejected,
        refinement=mosaic.refinement,
        common_pixels=common if layers else None,
        photo=mosaic.photo,
    )


def _bounded_size(size: tuple[int, int], edge: int) -> tuple[int, int]:
    width, height = size
    longest = max(width, height, edge)
    return max(1, width * edge // longest), max(1, height * edge // longest)


def _preview_frame(
    mosaic: _RasterPlan, size: tuple[int, int], context: JobContext, completed: int, total: int,
    *, samples: int = 1, window: Region | None = None,
) -> PreviewFrame:
    width, height = size
    has_layers = mosaic.seam_width is not None
    frame_bytes = width * height * (4 * mosaic.channels + 1 + int(has_layers) + int(samples > 1))
    budget = _WorkingBudget(mosaic.spec.max_working_bytes - frame_bytes)
    if budget.limit < _TILE_FIXED_BYTES:
        raise ValueError("The working byte budget cannot fit the preview and its render tiles.")
    context.check_cancelled()
    shape = (height, width)
    pixel_shape = shape if mosaic.channels == 1 else (*shape, mosaic.channels)
    pixels = np.zeros(pixel_shape, np.float32) if samples > 1 else np.empty(pixel_shape, np.float32)
    counts = np.zeros(shape, np.uint8) if samples > 1 else None
    valid = np.empty(shape, np.bool_)
    common = np.zeros(shape, np.bool_) if has_layers else None
    origin = window or Region(0, 0, width, height)
    for rendered in mosaic.tiles(width * samples, height * samples, budget, context, window=window):
        tile = rendered.tile
        region = tile.region
        if counts is None:
            where = Region(region.x - origin.x, region.y - origin.y, region.width, region.height)
            pixels[where.slices] = tile.pixels
            valid[where.slices] = tile.valid
            if common is not None and rendered.common_coverage is not None:
                common[where.slices] = rendered.common_coverage
        else:
            y, x = np.nonzero(tile.valid)
            bins = ((y + region.y) // samples, (x + region.x) // samples)
            np.add.at(counts, bins, 1)
            np.add.at(pixels, bins, tile.pixels[y, x])
            if common is not None and rendered.common_coverage is not None:
                np.logical_or.at(common, bins, rendered.common_coverage[y, x])
            del y, x, bins
        completed += tile.region.width * tile.region.height
        del rendered, tile
        if context.on_progress is not None:
            context.on_progress(completed, total)
    context.check_cancelled()
    if counts is not None:
        np.greater(counts, 0, out=valid)
        divisor = counts if mosaic.channels == 1 else counts[..., None]
        where_valid = valid if mosaic.channels == 1 else valid[..., None]
        np.divide(pixels, divisor, out=pixels, where=where_valid)
        pixels[~valid] = np.nan
    pixels.setflags(write=False)
    valid.setflags(write=False)
    if common is not None:
        common.setflags(write=False)
    return PreviewFrame(
        Tile(origin, pixels, valid),
        mosaic.size,
        mosaic.output_wcs.deepcopy() if mosaic.output_wcs is not None else None,
        mosaic.peak_reserved_bytes(frame_bytes + budget.peak),
        common,
        mosaic.seam_width,
        photo=mosaic.photo,
    )


def _preview_raster(
    mosaic: _RasterPlan,
    context: JobContext,
    on_proxy: Callable[[PreviewFrame], None] | None,
    *,
    fitted_grid: RenderSpec | None = None,
    visual_only: bool = False,
    adaptive_edge: int | None = None,
) -> PreviewFrame:
    coarse = _bounded_size(mosaic.size, _PROXY_EDGE)
    reference = _bounded_size(mosaic.size, _PREVIEW_EDGE)
    size, samples = (
        (reference, 1) if adaptive_edge is None
        else _overview_sampling(mosaic.size, adaptive_edge, mosaic.spec.max_working_bytes)
    )
    separate_reference = size != reference or samples != 1
    completed = coarse[0] * coarse[1] if on_proxy is not None and coarse != size else 0
    total = completed + size[0] * size[1] * samples**2
    if separate_reference:
        total += reference[0] * reference[1]
    if on_proxy is not None and completed:
        proxy = _preview_frame(mosaic, coarse, context, 0, total)
        if proxy.tile.valid.any():
            on_proxy(replace(proxy, fitted_grid=fitted_grid, visual_only=visual_only))
        del proxy
    levels = None
    if separate_reference:
        baseline = _preview_frame(mosaic, reference, context, completed, total)
        tile = baseline.tile
        if tile.valid.any():
            levels = preview_levels(tile.pixels[tile.valid].astype(np.float64))
            if on_proxy is not None and reference != coarse:
                on_proxy(replace(
                    baseline, fitted_grid=fitted_grid, visual_only=visual_only, tone_levels=levels
                ))
        del baseline, tile
        completed += reference[0] * reference[1]
    return replace(
        _preview_frame(mosaic, size, context, completed, total, samples=samples),
        fitted_grid=fitted_grid,
        visual_only=visual_only,
        tone_levels=levels,
    )


def _overview_sampling(
    size: tuple[int, int], edge: int, working_bytes: int
) -> tuple[tuple[int, int], int]:
    edge = max(_PREVIEW_EDGE, min(edge, MAX_OVERVIEW_EDGE))
    width, height = _bounded_size(size, edge)
    if width * height <= _OVERVIEW_SAMPLES and (width, height) == size:
        return (width, height), 1
    # Reserve at most a quarter of the job's bytes for the overview raster.
    sample_budget = min(4 * _OVERVIEW_SAMPLES, max(_OVERVIEW_SAMPLES, 2 * edge**2))
    capacity = max(1, min(sample_budget // 4, working_bytes // 60))
    if width * height > capacity:
        edge = max(1, int(max(width, height) * (capacity / (width * height)) ** 0.5))
        width, height = _bounded_size(size, edge)
    factor = min(4, isqrt(sample_budget // (width * height)))
    factor = min(factor, max(2, round(max(size[0] / width, size[1] / height))))
    return (width, height), factor


def _preview_detail(raster: _RasterPlan, window: Region, context: JobContext) -> PreviewFrame:
    if not Region(0, 0, *raster.size).contains(window):
        raise ValueError("The detail window must be inside the preview grid.")
    if window.width * window.height > MAX_DETAIL_PIXELS:
        raise ValueError("Zoom closer to render full-resolution detail.")
    return _preview_frame(
        raster, (window.width, window.height), context, 0, window.width * window.height,
        window=window,
    )


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
    filter_overrides: Mapping[int, str] | None = None,
    auto_frame: bool = False,
    allow_visual: bool = False,
    frame_locks: frozenset[FrameLock] = frozenset(),
    adaptive_edge: int | None = None,
    window: Region | None = None,
    inspect_crop: bool = False,
    photo_inputs: PhotoInputs | None = None,
    interpolate: PreviewInterpolator | None = None,
) -> PreviewFrame:
    """Sample the saved or fitted sky grid without opening an output file."""
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
        filter_overrides=filter_overrides,
        auto_frame=auto_frame,
        intent="preview" if allow_visual else "scientific",
        frame_locks=frame_locks,
        inspect_crop=inspect_crop,
        photo_inputs=photo_inputs,
    ) as mosaic:
        raster = mosaic.raster(interpolate)
        if window is not None:
            return replace(_preview_detail(raster, window, context), visual_only=mosaic.visual_only)
        return replace(_preview_raster(
            raster,
            context,
            on_proxy,
            fitted_grid=mosaic.spec if auto_frame else None,
            visual_only=mosaic.visual_only,
            adaptive_edge=adaptive_edge,
        ), suggested_crop=mosaic.suggested_crop, suggested_rotation=mosaic.suggested_rotation)
