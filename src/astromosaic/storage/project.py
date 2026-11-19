"""Versioned project manifests and verified local file references."""

import json
import os
from base64 import b64decode, b64encode
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from importlib.metadata import version
from math import isfinite
from pathlib import Path
from stat import S_ISREG
from typing import Any, Literal, TypedDict
from uuid import uuid4

from astromosaic.astrometry.hints import PanelOptics, positive_header_number, read_optics
from astromosaic.astrometry.solve import (
    SolveOptions,
    SolverAttempt,
    Stage,
    load_solution,
    panel_budget,
    solve_panel,
    write_solution,
)
from astromosaic.astrometry.solve_budget import SolveBudget, SolveBudgetExceeded
from astromosaic.core import PanelDescriptor, Region, SourceFingerprint
from astromosaic.core.job import JobContext
from astromosaic.core.masks import (
    FOREGROUND,
    MASK_EDGE,
    SKY,
    ForegroundSuggestion,
    ForegroundTag,
    SourceMask,
    bounded_grid,
)
from astromosaic.geometry import read_panel_geometry
from astromosaic.geometry.image import CompositionSpec, LayerPlacement
from astromosaic.io import PanelSource, SkyMask, open_panel
from astromosaic.io.atomic import atomic_binary_file
from astromosaic.io.fits import optional_header_text
from astromosaic.pipeline.foreground import (
    ForegroundAlignment,
    ForegroundPairDiagnostic,
    GroundOverlap,
    GroundPanel,
    align_foreground,
)
from astromosaic.pipeline.layers import (
    ForegroundLayer,
    ForegroundSource,
    composition_raster,
    propose_composition,
)
from astromosaic.pipeline.mosaic import (
    MosaicResult,
    PreviewFrame,
    RenderSpec,
    _prepare_mosaic,
    _preview_raster,
    _RasterPlan,
    _write_raster,
    preview_mosaic,
    render_mosaic,
)
from astromosaic.pipeline.refinement import RefinementSpec, validate_refinement_inputs

_TAN_SCHEMA_VERSION = 4
_PROJECTION_SCHEMA_VERSION = 5
_BAND_SCHEMA_VERSION = 6
_MAX_MANIFEST_BYTES = 4 * 1024**2
type Layer = Literal["sky", "foreground", "composition"]
type _GroundInputs = tuple[tuple[int, SourceMask], ...]


@dataclass(frozen=True, slots=True)
class FileReference:
    path: Path
    fingerprint: SourceFingerprint

    @classmethod
    def capture(cls, path: Path) -> "FileReference":
        path = Path(os.path.abspath(path))
        stat = path.stat()
        if not S_ISREG(stat.st_mode):
            raise ValueError(f"Expected a regular file: {path}")
        return cls(path, SourceFingerprint(stat.st_size, stat.st_mtime_ns))

    def status(self) -> str:
        try:
            fingerprint = self.capture(self.path).fingerprint
        except FileNotFoundError:
            return "Missing"
        except (OSError, ValueError):
            return "Unavailable"
        return "Ready" if fingerprint == self.fingerprint else "Changed"

    def relink(self, path: Path) -> "FileReference":
        target = self.capture(path)
        if target.fingerprint != self.fingerprint:
            raise ValueError("The file size or modification time differs from the saved reference.")
        return target


@dataclass(frozen=True, slots=True)
class ProjectPanel:
    source: FileReference
    weight: float = 1.0
    sky_mask: FileReference | None = None
    wcs_sidecar: FileReference | None = None
    foreground_suggestion: ForegroundSuggestion | None = None
    foreground_override: ForegroundTag | None = None
    source_mask: SourceMask | None = None
    include_sky: bool = True
    optics: PanelOptics = PanelOptics()
    band_override: str | None = None

    def __post_init__(self) -> None:
        if self.sky_mask is not None and self.source_mask is not None:
            raise ValueError("Choose either an attached FITS mask or an edited sky mask.")
        label = self.band_override
        if label is not None and (
            not isinstance(label, str)
            or not label.isascii()
            or not label.isprintable()
            or label.strip() != label
        ):
            raise ValueError("Supply a nonempty band override using printable FITS characters.")

    def sky_band(self, embedded: str | None, fallback: str | None) -> str | None:
        return self.band_override or embedded or ((fallback or "").strip() or None)

    @property
    def foreground_tag(self) -> ForegroundSuggestion | None:
        if self.foreground_override is not None:
            return self.foreground_override
        return "mixed" if self.source_mask is not None else self.foreground_suggestion

    def sky_input(self) -> SkyMask | None:
        if self.source_mask is not None:
            return self.source_mask
        if self.sky_mask is not None:
            return self.sky_mask.path
        if self.foreground_tag in ("mixed", "uncertain"):
            raise ValueError(
                f"{self.source.path.name}: Apply a sky mask or mark the panel Sky only."
            )
        return None

    def references(self) -> tuple[tuple[str, FileReference], ...]:
        references = [("Source", self.source)]
        if self.wcs_sidecar is not None:
            references.append(("WCS sidecar", self.wcs_sidecar))
        if self.sky_mask is not None:
            references.append(("Sky mask", self.sky_mask))
        return tuple(references)


@dataclass(frozen=True, slots=True)
class SavedForeground:
    input_key: str
    alignment: ForegroundAlignment

    def __post_init__(self) -> None:
        if len(self.input_key) != 64 or any(c not in "0123456789abcdef" for c in self.input_key):
            raise ValueError("Invalid foreground input fingerprint.")


@dataclass(frozen=True, slots=True)
class MosaicProject:
    panels: tuple[ProjectPanel, ...] = ()
    render: RenderSpec = RenderSpec((0.0, 0.0), (1024, 1024), 2.0)
    filter_name: str | None = None
    assume_surface_brightness: bool = False
    refinement: RefinementSpec | None = None
    foreground: SavedForeground | None = None
    composition: CompositionSpec | None = None

    def validate(self) -> None:
        spec = self.render
        region = spec.output_region()
        spec.output_wcs()
        if any(not isfinite(panel.weight) or panel.weight <= 0 for panel in self.panels):
            raise ValueError("Panel weights must be positive and finite.")
        if self.composition is not None and self.composition.sky_crop_bottom >= region.height:
            raise ValueError("The composition crop must retain at least one row of sky.")

    def foreground_inputs(self) -> _GroundInputs:
        return tuple(
            (i, panel.source_mask)
            for i, panel in enumerate(self.panels)
            if panel.source_mask is not None
            and panel.foreground_tag != "sky-only"
            and FOREGROUND in panel.source_mask.labels
        )

    def foreground_key(self, inputs: _GroundInputs) -> str:
        digest = sha256(b"astromosaic-foreground-translation-v1\n")
        for index, mask in inputs:
            fp = self.panels[index].source.fingerprint
            digest.update(
                f"{index}:{fp.size_bytes}:{fp.modified_ns}:{mask.source_size}\n".encode("ascii")
            )
            digest.update(mask.labels.translate(bytes.maketrans(bytes((SKY,)), b"\x00")))
        return digest.hexdigest()

    def current_foreground(self) -> ForegroundAlignment | None:
        if self.foreground is not None:
            inputs = self.foreground_inputs()
            if self.foreground.input_key == self.foreground_key(inputs) and tuple(
                panel.index for panel in self.foreground.alignment.panels
            ) == tuple(i for i, _ in inputs):
                return self.foreground.alignment
        return None

    def sky_indices(self) -> tuple[int, ...]:
        return tuple(
            i
            for i, panel in enumerate(self.panels)
            if panel.include_sky and (panel.source_mask is None or SKY in panel.source_mask.labels)
        )

    def relink_panel(self, index: int, path: Path) -> "MosaicProject":
        panel = self.panels[index]
        updated = replace(panel, source=panel.source.relink(path))
        return replace(self, panels=self.panels[:index] + (updated,) + self.panels[index + 1 :])


class _PanelInputs(TypedDict):
    paths: list[Path]
    weights: list[float]
    filter_name: str | None
    assume_surface_brightness: bool
    sky_masks: dict[int, SkyMask]
    wcs_sidecars: dict[int, Path]
    filter_overrides: dict[int, str]
    refinement: RefinementSpec | None


def _check_reference(role: str, reference: FileReference, context: JobContext) -> None:
    context.check_cancelled()
    status = reference.status()
    if status != "Ready":
        raise ValueError(f"{role} file is {status.lower()}: {reference.path.name}")


@contextmanager
def open_project_sky_panel(
    panel: ProjectPanel, max_working_bytes: int, context: JobContext
) -> Iterator[PanelSource]:
    """Use the saved sky selection when solving one project panel."""
    _check_reference("Source", panel.source, context)
    if panel.sky_mask is not None:
        _check_reference("Sky mask", panel.sky_mask, context)
    with open_panel(
        panel.source.path, max_tile_bytes=max_working_bytes, sky_mask=panel.sky_input()
    ) as source:
        yield source


@dataclass(frozen=True, slots=True)
class PanelInspection:
    wcs_status: Literal["Embedded", "Sidecar", "Missing", "Invalid", "Unavailable"]
    detail: str
    embedded_optics: PanelOptics = PanelOptics()
    camera_model: str | None = None
    filter_name: str | None = None
    descriptor: PanelDescriptor | None = None
    telescope_model: str | None = None
    embedded_scale_arcsec: float | None = None


def inspect_project_panel(panel: ProjectPanel, context: JobContext) -> PanelInspection:
    """Inspect source headers and validate the WCS selected by the project."""
    try:
        _check_reference("Source", panel.source, context)
        with open_panel(panel.source.path) as source:
            header = source.header
            descriptor = source.descriptor
    except (OSError, ValueError, OverflowError) as error:
        return PanelInspection("Unavailable", str(error))

    info = PanelInspection(
        "Missing",
        "The input has no embedded celestial WCS.",
        read_optics(header),
        optional_header_text(header, "INSTRUME"),
        descriptor.filter_name,
        descriptor,
        optional_header_text(header, "TELESCOP"),
        positive_header_number(header.get("PIXSCALE")),
    )
    if panel.wcs_sidecar is not None:
        try:
            _check_reference("WCS sidecar", panel.wcs_sidecar, context)
            with open_project_sky_panel(panel, 32 * 1024**2, context) as source:
                _, provenance = load_solution(panel.wcs_sidecar.path, source)
        except (OSError, ValueError, OverflowError) as error:
            return replace(info, wcs_status="Invalid", detail=str(error))
        return replace(info, wcs_status="Sidecar", detail=provenance)

    if not any(key in header for key in ("CTYPE1", "CTYPE2", "CRVAL1", "CRVAL2")):
        return info
    try:
        read_panel_geometry(header, descriptor.width, descriptor.height)
    except (ValueError, OverflowError) as error:
        return replace(info, wcs_status="Invalid", detail=str(error))
    return replace(
        info, wcs_status="Embedded", detail="Validated the image's embedded celestial WCS."
    )


def panels_needing_wcs(project: MosaicProject, context: JobContext) -> tuple[int, ...]:
    return tuple(
        index
        for index in project.sky_indices()
        if inspect_project_panel(project.panels[index], context).wcs_status
        not in {"Embedded", "Sidecar"}
    )


@dataclass(frozen=True, slots=True)
class PanelSolveOutcome:
    index: int
    stage: Stage | None = None
    sidecar: FileReference | None = None
    attempts: tuple[SolverAttempt, ...] = ()
    error: str | None = None
    status: str = "unsolved"
    budget: dict[str, object] | None = None
    quality: dict[str, object] | None = None


def solve_project_panel(
    index: int,
    panel: ProjectPanel,
    options: SolveOptions,
    directory: Path,
    context: JobContext,
    *,
    job_budget: SolveBudget | None = None,
) -> PanelSolveOutcome:
    """Resolve one candidate and publish a new sidecar with its input identity."""
    budget = panel_budget(options, job_budget)
    context = budget.context(context)
    attempts: tuple[SolverAttempt, ...] = ()
    try:
        with open_project_sky_panel(panel, options.max_working_bytes, context) as source:
            existing = (
                panel.wcs_sidecar.path
                if panel.wcs_sidecar is not None and panel.wcs_sidecar.status() == "Ready"
                else None
            )
            result = solve_panel(
                source,
                replace(options, optics=panel.optics),
                context,
                budget=budget,
                existing_sidecar=existing,
            )
            attempts = result.attempts
            if result.geometry is None:
                return PanelSolveOutcome(
                    index,
                    attempts=attempts,
                    error=result.reason or "No solver produced a valid WCS.",
                    status=result.outcome,
                    budget=budget.report(),
                )
            _check_reference("Source", panel.source, context)
            if panel.sky_mask is not None:
                _check_reference("Sky mask", panel.sky_mask, context)
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"panel-{index + 1}-{uuid4().hex}.wcs.json"
            context.check_cancelled()
            write_solution(path, source, result, context)
            return PanelSolveOutcome(
                index,
                result.stage,
                FileReference.capture(path),
                attempts,
                status="solved",
                budget=budget.report(),
                quality=result.quality,
            )
    except SolveBudgetExceeded as error:
        return PanelSolveOutcome(
            index,
            attempts=attempts,
            error=str(error),
            status="budget-exhausted",
            budget=budget.report(),
        )
    except (OSError, ValueError, OverflowError) as error:
        return PanelSolveOutcome(index, attempts=attempts, error=str(error), budget=budget.report())


def project_sky_bands(project: MosaicProject, context: JobContext) -> dict[str, list[int]]:
    """Read verified sky membership in saved panel order without opening pixel windows."""
    bands: dict[str, list[int]] = {}
    for index in project.sky_indices():
        panel = project.panels[index]
        try:
            _check_reference("Source", panel.source, context)
            with open_panel(
                panel.source.path, max_tile_bytes=project.render.max_working_bytes
            ) as source:
                if source.descriptor.fingerprint != panel.source.fingerprint:
                    raise ValueError("The source changed during band discovery.")
                label = panel.sky_band(source.descriptor.filter_name, project.filter_name)
            if label is None:
                raise ValueError("Assign a sky band or supply an embedded FILTER.")
        except (OSError, ValueError, OverflowError) as error:
            raise ValueError(f"Panel {index + 1} ({panel.source.path.name}): {error}") from error
        bands.setdefault(label, []).append(index)
    if not bands:
        raise ValueError("Include at least one panel with sky samples in the sky layer.")
    return bands


def _verified_inputs(
    project: MosaicProject, context: JobContext, band: str | None = None
) -> _PanelInputs:
    sky_masks = {}
    filter_name = project.filter_name
    if band is None:
        indices = project.sky_indices()
    else:
        band = band.strip()
        bands = project_sky_bands(project, context)
        if band not in bands:
            choices = ", ".join(bands)
            raise ValueError(f"Unknown sky band {band!r}. Available bands are {choices}.")
        indices = tuple(bands[band])
        filter_name = band
    panels = [project.panels[i] for i in indices]
    if not panels:
        raise ValueError("Include at least one panel with sky samples in the sky layer.")
    for index, panel in enumerate(panels):
        for role, reference in panel.references():
            _check_reference(role, reference, context)
        if (mask := panel.sky_input()) is not None:
            sky_masks[index] = mask
    return {
        "paths": [panel.source.path for panel in panels],
        "weights": [panel.weight for panel in panels],
        "filter_name": filter_name,
        "assume_surface_brightness": project.assume_surface_brightness,
        "sky_masks": sky_masks,
        "wcs_sidecars": {i: p.wcs_sidecar.path for i, p in enumerate(panels) if p.wcs_sidecar},
        "filter_overrides": {
            i: p.band_override for i, p in enumerate(panels) if p.band_override is not None
        },
        "refinement": project.refinement,
    }


@dataclass(frozen=True, slots=True)
class SkyPreflight:
    panels: int
    width: int
    height: int
    channels: int


def validate_project_sky(
    project: MosaicProject,
    context: JobContext,
    destination: Path | None = None,
    *,
    band: str | None = None,
) -> SkyPreflight:
    """Check the saved sky inputs and render settings without fitting or writing pixels."""
    project.validate()
    if destination is not None and not destination.parent.is_dir():
        raise FileNotFoundError(f"The output directory does not exist: {destination.parent}")
    inputs = _verified_inputs(project, context, band)
    inputs["refinement"] = None
    with _prepare_mosaic(
        spec=project.render, destination=destination, context=context, **inputs
    ) as sky:
        if project.refinement is not None:
            validate_refinement_inputs([panel.source for panel in sky.panels])
        width, height = sky.size
        return SkyPreflight(len(sky.panels), width, height, sky.channels)


def render_project(
    project: MosaicProject, destination: Path, context: JobContext, *, band: str | None = None
) -> MosaicResult:
    return render_mosaic(
        destination=destination,
        spec=project.render,
        context=context,
        **_verified_inputs(project, context, band),
    )


def preview_project(
    project: MosaicProject,
    context: JobContext,
    on_proxy: Callable[[PreviewFrame], None] | None = None,
    *,
    band: str | None = None,
) -> PreviewFrame:
    return preview_mosaic(
        spec=project.render,
        context=context,
        on_proxy=on_proxy,
        **_verified_inputs(project, context, band),
    )


def _open_ground_source(
    project: MosaicProject,
    index: int,
    mask: SourceMask,
    context: JobContext,
    stack: ExitStack,
) -> PanelSource:
    panel = project.panels[index]
    _check_reference("Source", panel.source, context)
    source = stack.enter_context(
        open_panel(
            panel.source.path,
            max_tile_bytes=project.render.max_working_bytes,
            foreground_mask=mask,
        )
    )
    if source.descriptor.fingerprint != panel.source.fingerprint:
        raise ValueError(f"Source file changed: {panel.source.path.name}")
    return source


def align_project_foreground(
    project: MosaicProject,
    context: JobContext,
    *,
    on_pair: Callable[[ForegroundPairDiagnostic], None] | None = None,
) -> MosaicProject:
    """Align the masked ground sources and optionally report each completed pair."""
    inputs = project.foreground_inputs()
    with ExitStack() as stack:
        candidates = []
        for index, mask in inputs:
            bounds = mask.bounds(FOREGROUND)
            assert bounds is not None
            source = _open_ground_source(project, index, mask, context, stack)
            candidates.append((index, source, bounds))
        aligned = align_foreground(
            candidates, project.render.max_working_bytes, context, on_pair=on_pair
        )
    keep_placement = project.foreground is not None and project.foreground.alignment == aligned
    return replace(
        project,
        foreground=SavedForeground(project.foreground_key(inputs), aligned),
        composition=project.composition if keep_placement else None,
    )


@contextmanager
def _project_foreground(project: MosaicProject, context: JobContext) -> Iterator[ForegroundLayer]:
    alignment = project.current_foreground()
    if alignment is None:
        raise ValueError("Align the current foreground panels first.")
    masks = dict(project.foreground_inputs())
    with ExitStack() as stack:
        panels = [
            ForegroundSource(
                _open_ground_source(project, item.index, masks[item.index], context, stack),
                project.panels[item.index].weight,
                masks[item.index],
                item,
            )
            for item in alignment.panels
        ]
        if any(
            (p.source.descriptor.width, p.source.descriptor.height) != alignment.source_size
            for p in panels
        ):
            raise ValueError("The saved foreground dimensions differ from the source panels.")
        yield ForegroundLayer(
            panels,
            alignment,
            project.render,
            project.filter_name,
            project.assume_surface_brightness,
        )


def default_composition(project: MosaicProject) -> CompositionSpec:
    if project.composition is not None:
        return project.composition
    y = float(project.render.output_region().height)
    return CompositionSpec(LayerPlacement((0.0, y)), seam_y=y - 0.5)


def propose_project_composition(project: MosaicProject, context: JobContext) -> CompositionSpec:
    with (
        _project_foreground(project, context) as ground,
        _prepare_mosaic(
            spec=project.render,
            destination=None,
            context=context,
            **_verified_inputs(project, context),
        ) as sky,
    ):
        return propose_composition(
            sky, project.sky_indices(), ground, default_composition(project), context
        )


@contextmanager
def _project_layer(
    project: MosaicProject, layer: Layer, context: JobContext
) -> Iterator[_RasterPlan]:
    with _project_foreground(project, context) as ground:
        if layer == "foreground":
            yield ground.raster()
            return
        if project.composition is None:
            raise ValueError("Set the composition placement or use the shared horizon proposal.")
        with _prepare_mosaic(
            spec=project.render,
            destination=None,
            context=context,
            **_verified_inputs(project, context),
        ) as sky:
            yield composition_raster(sky, ground, project.composition)


def preview_project_layer(
    project: MosaicProject,
    layer: Layer,
    context: JobContext,
    on_proxy: Callable[[PreviewFrame], None] | None = None,
    *,
    band: str | None = None,
) -> PreviewFrame:
    if layer == "sky":
        return preview_project(project, context, on_proxy, band=band)
    if band is not None:
        raise ValueError("A band selection requires the sky layer.")
    with _project_layer(project, layer, context) as raster:
        return _preview_raster(raster, context, on_proxy)


def render_project_layer(
    project: MosaicProject,
    layer: Layer,
    destination: Path,
    context: JobContext,
    *,
    band: str | None = None,
) -> MosaicResult:
    if layer == "sky":
        return render_project(project, destination, context, band=band)
    if band is not None:
        raise ValueError("A band selection requires the sky layer.")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"The output file already exists: {destination}")
    with _project_layer(project, layer, context) as raster:
        return _write_raster(raster, destination, context)


def _encode_reference(reference: FileReference | None, directory: Path) -> dict[str, object] | None:
    if reference is None:
        return None
    try:
        path = Path(os.path.relpath(reference.path, directory)).as_posix()
    except ValueError:
        # Windows cannot express a relative path across drives.
        path = reference.path.as_posix()
    return {"path": path, "fingerprint": asdict(reference.fingerprint)}


def _encode_mask(mask: SourceMask | None) -> dict[str, object] | None:
    if mask is None:
        return None
    return {"source_size": mask.source_size, "labels": b64encode(mask.labels).decode("ascii")}


def save_project(path: Path, project: MosaicProject, *, replace_existing: bool = False) -> None:
    if path.suffix.lower() != ".astromosaic":
        raise ValueError("The project filename must end in .astromosaic.")
    if any(
        path.resolve() == reference.path.resolve()
        for panel in project.panels
        for _, reference in panel.references()
    ):
        raise ValueError("Choose a project filename separate from the panel files and attachments.")
    project.validate()
    directory = path.absolute().parent
    render = asdict(project.render)
    schema_version = _PROJECTION_SCHEMA_VERSION
    if project.render.projection == "TAN":
        schema_version = _TAN_SCHEMA_VERSION
    if any(panel.band_override is not None for panel in project.panels):
        schema_version = _BAND_SCHEMA_VERSION
    if schema_version == _TAN_SCHEMA_VERSION:
        del render["projection"]
    data = {
        "version": schema_version,
        "application_version": version("astromosaic"),
        "render": render,
        "filter_name": project.filter_name,
        "assume_surface_brightness": project.assume_surface_brightness,
        "refinement": asdict(project.refinement) if project.refinement else None,
        "foreground": asdict(project.foreground) if project.foreground else None,
        "composition": asdict(project.composition) if project.composition else None,
        "panels": [
            {
                "source": _encode_reference(panel.source, directory),
                "weight": panel.weight,
                "sky_mask": _encode_reference(panel.sky_mask, directory),
                "wcs_sidecar": _encode_reference(panel.wcs_sidecar, directory),
                "foreground_suggestion": panel.foreground_suggestion,
                "foreground_override": panel.foreground_override,
                "source_mask": _encode_mask(panel.source_mask),
                "include_sky": panel.include_sky,
                "optics": asdict(panel.optics),
                **(
                    {"band_override": panel.band_override}
                    if schema_version >= _BAND_SCHEMA_VERSION
                    else {}
                ),
            }
            for panel in project.panels
        ],
    }
    payload = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    if len(payload) > _MAX_MANIFEST_BYTES:
        raise ValueError("The project manifest exceeds its size limit.")
    with atomic_binary_file(path, replace_existing=replace_existing) as stream:
        stream.write(payload)


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Expected a project object.")
    return value


def _integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("Expected an integer.")
    return value


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
        raise ValueError("Expected a finite number.")
    return float(value)


def _pair(value: object) -> tuple[object, object]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Expected a pair.")
    return value[0], value[1]


def _decode_reference(value: object, directory: Path) -> FileReference:
    record = _object(value)
    name = record["path"]
    if not isinstance(name, str) or not name.strip() or "\0" in name:
        raise ValueError("Expected a nonempty file path.")
    path = Path(name)
    if path.anchor and not path.is_absolute():
        raise ValueError("Expected a project-relative path or a fully qualified absolute path.")
    fingerprint = _object(record["fingerprint"])
    size = _integer(fingerprint["size_bytes"])
    if size < 0:
        raise ValueError("Expected a nonnegative file size.")
    return FileReference(
        Path(os.path.abspath(directory / path)),
        SourceFingerprint(size, _integer(fingerprint["modified_ns"])),
    )


def _decode_render(value: object, schema_version: int) -> RenderSpec:
    render = _object(value)
    projection = render.get("projection", "TAN")
    if schema_version >= _PROJECTION_SCHEMA_VERSION:
        projection = render["projection"]
    elif projection != "TAN":
        raise ValueError("A non-TAN grid requires project manifest version 5.")
    ra, dec = _pair(render["center"])
    width, height = _pair(render["size"])
    crop = None
    if render["crop"] is not None:
        crop = _decode_region(render["crop"])
    return RenderSpec(
        (_number(ra), _number(dec)),
        (_integer(width), _integer(height)),
        _number(render["scale_arcsec"]),
        _number(render["rotation_deg"]),
        crop,
        _integer(render["tile_size"]),
        _integer(render["max_working_bytes"]),
        _integer(render["max_output_bytes"]),
        projection=projection,
    )


def _decode_region(value: object) -> Region:
    fields = _object(value)
    return Region(*(_integer(fields[key]) for key in ("x", "y", "width", "height")))


def _decode_foreground(value: object) -> SavedForeground | None:
    if value is None:
        return None
    data = _object(value)
    alignment = _object(data["alignment"])
    input_key = data["input_key"]
    if (
        not isinstance(input_key, str)
        or not isinstance(alignment["panels"], list)
        or not isinstance(alignment["overlaps"], list)
    ):
        raise ValueError("Invalid foreground record.")
    panels, overlaps = [], []
    for record in alignment["panels"]:
        panel = _object(record)
        dx, dy = _pair(panel["shift"])
        panels.append(GroundPanel(_integer(panel["index"]), (_number(dx), _number(dy))))
    for record in alignment["overlaps"]:
        edge = _object(record)
        left, right = _pair(edge["panels"])
        overlaps.append(
            GroundOverlap(
                (_integer(left), _integer(right)),
                _number(edge["correlation"]),
                _integer(edge["support"]),
                _integer(edge["patches"]),
            )
        )
    width, height = _pair(alignment["source_size"])
    return SavedForeground(
        input_key,
        ForegroundAlignment(
            (_integer(width), _integer(height)),
            _decode_region(alignment["canvas"]),
            tuple(panels),
            tuple(overlaps),
        ),
    )


def _decode_composition(value: object) -> CompositionSpec | None:
    if value is None:
        return None
    record = _object(value)
    placement = _object(record["placement"])
    dx, dy = _pair(placement["offset"])
    reference, rms = record["reference_panel"], record["placement_rms_px"]
    return CompositionSpec(
        LayerPlacement(
            (_number(dx), _number(dy)),
            _number(placement["rotation_deg"]),
            _number(placement["scale"]),
        ),
        _number(record["seam_y"]),
        _number(record["overlap_percent"]),
        _integer(record["sky_crop_bottom"]),
        _integer(reference) if reference is not None else None,
        _number(rms) if rms is not None else None,
    )


def _decode_refinement(value: object) -> RefinementSpec | None:
    if value is None:
        return None
    record = _object(value)
    background = record["background"]
    if background not in ("none", "offset", "plane"):
        raise ValueError("Unknown refinement background model.")
    return RefinementSpec(_number(record["max_shift_px"]), background)


def _decode_mask(value: object) -> SourceMask | None:
    if value is None:
        return None
    record = _object(value)
    width, height = _pair(record["source_size"])
    source_size = (_integer(width), _integer(height))
    columns, rows = bounded_grid(source_size, MASK_EDGE)
    labels = record["labels"]
    if not isinstance(labels, str) or len(labels) != 4 * ((columns * rows + 2) // 3):
        raise ValueError("Unexpected encoded source mask size.")
    return SourceMask(source_size, b64decode(labels, validate=True))


def _decode_panel(value: object, directory: Path, schema_version: int) -> ProjectPanel:
    record = _object(value)
    mask, wcs = record["sky_mask"], record["wcs_sidecar"]
    suggestion, override, source_mask = None, None, None
    if schema_version >= 2:
        suggestion = record["foreground_suggestion"]
        override = record["foreground_override"]
        source_mask = _decode_mask(record["source_mask"])
        if suggestion not in (None, "mixed", "sky-only", "uncertain"):
            raise ValueError("Unknown foreground suggestion.")
        if override not in (None, "mixed", "sky-only"):
            raise ValueError("Unknown foreground override.")
    include_sky = record["include_sky"] if schema_version >= 3 else True
    if not isinstance(include_sky, bool):
        raise ValueError("Invalid sky-layer selection.")
    optics = _object(record["optics"]) if schema_version >= 4 else {}
    band_override = record["band_override"] if schema_version >= _BAND_SCHEMA_VERSION else None
    if schema_version < _BAND_SCHEMA_VERSION and record.get("band_override") is not None:
        raise ValueError("Sky band overrides require project manifest version 6.")

    def optical_value(key: str) -> float | None:
        value = optics.get(key)
        return _number(value) if value is not None else None

    return ProjectPanel(
        _decode_reference(record["source"], directory),
        _number(record["weight"]),
        _decode_reference(mask, directory) if mask is not None else None,
        _decode_reference(wcs, directory) if wcs is not None else None,
        suggestion,
        override,
        source_mask,
        include_sky,
        PanelOptics(
            optical_value("focal_length_mm"),
            optical_value("pixel_size_x_um"),
            optical_value("pixel_size_y_um"),
        ),
        band_override,
    )


def load_project(path: Path) -> MosaicProject:
    with path.open("rb") as stream:
        payload = stream.read(_MAX_MANIFEST_BYTES + 1)
    if len(payload) > _MAX_MANIFEST_BYTES:
        raise ValueError("The project manifest exceeds its size limit.")
    try:
        data = _object(json.loads(payload.decode("utf-8")))
        schema_version = _integer(data["version"])
        if not 1 <= schema_version <= _BAND_SCHEMA_VERSION:
            raise ValueError("Unsupported project manifest version.")
        if not isinstance(data["panels"], list):
            raise ValueError("Expected an ordered panel list.")
        filter_name, assume = data["filter_name"], data["assume_surface_brightness"]
        if (filter_name is not None and not isinstance(filter_name, str)) or not isinstance(
            assume, bool
        ):
            raise ValueError("Invalid filter or surface brightness declaration.")
        project = MosaicProject(
            tuple(
                _decode_panel(record, path.absolute().parent, schema_version)
                for record in data["panels"]
            ),
            _decode_render(data["render"], schema_version),
            filter_name,
            assume,
            _decode_refinement(data["refinement"]),
            _decode_foreground(data["foreground"]) if schema_version >= 3 else None,
            _decode_composition(data["composition"]) if schema_version >= 3 else None,
        )
        project.validate()
        return project
    except (KeyError, ValueError, OverflowError, RecursionError) as error:
        raise ValueError(f"Invalid project manifest: {error}") from error
