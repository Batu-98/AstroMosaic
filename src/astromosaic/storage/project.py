"""Versioned project manifests and verified local file references."""

import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from importlib.metadata import version
from math import isfinite
from pathlib import Path
from stat import S_ISREG
from typing import Any, TypedDict

from astromosaic.core import Region, SourceFingerprint
from astromosaic.core.job import JobContext
from astromosaic.geometry import tan_output_wcs
from astromosaic.io.atomic import atomic_binary_file
from astromosaic.pipeline.mosaic import (
    MosaicResult,
    PreviewFrame,
    RenderSpec,
    preview_mosaic,
    render_mosaic,
)
from astromosaic.pipeline.refinement import RefinementSpec

_SCHEMA_VERSION = 1
_MAX_MANIFEST_BYTES = 4 * 1024**2


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

    def references(self) -> tuple[tuple[str, FileReference], ...]:
        references = [("Source", self.source)]
        if self.wcs_sidecar is not None:
            references.append(("WCS sidecar", self.wcs_sidecar))
        if self.sky_mask is not None:
            references.append(("Sky mask", self.sky_mask))
        return tuple(references)


@dataclass(frozen=True, slots=True)
class MosaicProject:
    panels: tuple[ProjectPanel, ...] = ()
    render: RenderSpec = RenderSpec((0.0, 0.0), (1024, 1024), 2.0)
    filter_name: str | None = None
    assume_surface_brightness: bool = False
    refinement: RefinementSpec | None = None

    def validate(self) -> None:
        spec = self.render
        tan_output_wcs(
            spec.center, spec.size, spec.scale_arcsec, spec.rotation_deg, spec.output_region()
        )
        if any(not isfinite(panel.weight) or panel.weight <= 0 for panel in self.panels):
            raise ValueError("Panel weights must be positive and finite.")

    def relink_panel(self, index: int, path: Path) -> "MosaicProject":
        panel = self.panels[index]
        updated = replace(panel, source=panel.source.relink(path))
        return replace(self, panels=self.panels[:index] + (updated,) + self.panels[index + 1 :])


class _PanelInputs(TypedDict):
    paths: list[Path]
    weights: list[float]
    filter_name: str | None
    assume_surface_brightness: bool
    sky_masks: dict[int, Path]
    wcs_sidecars: dict[int, Path]
    refinement: RefinementSpec | None


def _verified_inputs(project: MosaicProject, context: JobContext) -> _PanelInputs:
    for panel in project.panels:
        for role, reference in panel.references():
            context.check_cancelled()
            status = reference.status()
            if status != "Ready":
                raise ValueError(f"{role} file is {status.lower()}: {reference.path.name}")
    return {
        "paths": [panel.source.path for panel in project.panels],
        "weights": [panel.weight for panel in project.panels],
        "filter_name": project.filter_name,
        "assume_surface_brightness": project.assume_surface_brightness,
        "sky_masks": {i: p.sky_mask.path for i, p in enumerate(project.panels) if p.sky_mask},
        "wcs_sidecars": {
            i: p.wcs_sidecar.path for i, p in enumerate(project.panels) if p.wcs_sidecar
        },
        "refinement": project.refinement,
    }


def render_project(project: MosaicProject, destination: Path, context: JobContext) -> MosaicResult:
    return render_mosaic(
        destination=destination,
        spec=project.render,
        context=context,
        **_verified_inputs(project, context),
    )


def preview_project(
    project: MosaicProject,
    context: JobContext,
    on_proxy: Callable[[PreviewFrame], None] | None = None,
) -> PreviewFrame:
    return preview_mosaic(
        spec=project.render,
        context=context,
        on_proxy=on_proxy,
        **_verified_inputs(project, context),
    )


def _encode_reference(reference: FileReference | None, directory: Path) -> dict[str, object] | None:
    if reference is None:
        return None
    try:
        path = Path(os.path.relpath(reference.path, directory)).as_posix()
    except ValueError:
        # Windows cannot express a relative path across drives.
        path = reference.path.as_posix()
    return {"path": path, "fingerprint": asdict(reference.fingerprint)}


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
    data = {
        "version": _SCHEMA_VERSION,
        "application_version": version("astromosaic"),
        "render": asdict(project.render),
        "filter_name": project.filter_name,
        "assume_surface_brightness": project.assume_surface_brightness,
        "refinement": asdict(project.refinement) if project.refinement else None,
        "panels": [
            {
                "source": _encode_reference(panel.source, directory),
                "weight": panel.weight,
                "sky_mask": _encode_reference(panel.sky_mask, directory),
                "wcs_sidecar": _encode_reference(panel.wcs_sidecar, directory),
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


def _decode_render(value: object) -> RenderSpec:
    render = _object(value)
    ra, dec = _pair(render["center"])
    width, height = _pair(render["size"])
    crop = None
    if render["crop"] is not None:
        fields = _object(render["crop"])
        crop = Region(*(_integer(fields[key]) for key in ("x", "y", "width", "height")))
    return RenderSpec(
        (_number(ra), _number(dec)),
        (_integer(width), _integer(height)),
        _number(render["scale_arcsec"]),
        _number(render["rotation_deg"]),
        crop,
        _integer(render["tile_size"]),
        _integer(render["max_working_bytes"]),
        _integer(render["max_output_bytes"]),
    )


def _decode_refinement(value: object) -> RefinementSpec | None:
    if value is None:
        return None
    record = _object(value)
    background = record["background"]
    if background not in ("none", "offset", "plane"):
        raise ValueError("Unknown refinement background model.")
    return RefinementSpec(_number(record["max_shift_px"]), background)


def _decode_panel(value: object, directory: Path) -> ProjectPanel:
    record = _object(value)
    mask, wcs = record["sky_mask"], record["wcs_sidecar"]
    return ProjectPanel(
        _decode_reference(record["source"], directory),
        _number(record["weight"]),
        _decode_reference(mask, directory) if mask is not None else None,
        _decode_reference(wcs, directory) if wcs is not None else None,
    )


def load_project(path: Path) -> MosaicProject:
    with path.open("rb") as stream:
        payload = stream.read(_MAX_MANIFEST_BYTES + 1)
    if len(payload) > _MAX_MANIFEST_BYTES:
        raise ValueError("The project manifest exceeds its size limit.")
    try:
        data = _object(json.loads(payload.decode("utf-8")))
        if _integer(data["version"]) != _SCHEMA_VERSION:
            raise ValueError("Unsupported project manifest version.")
        if not isinstance(data["panels"], list):
            raise ValueError("Expected an ordered panel list.")
        filter_name, assume = data["filter_name"], data["assume_surface_brightness"]
        if (filter_name is not None and not isinstance(filter_name, str)) or not isinstance(
            assume, bool
        ):
            raise ValueError("Invalid filter or surface brightness declaration.")
        project = MosaicProject(
            tuple(_decode_panel(record, path.absolute().parent) for record in data["panels"]),
            _decode_render(data["render"]),
            filter_name,
            assume,
            _decode_refinement(data["refinement"]),
        )
        project.validate()
        return project
    except (KeyError, ValueError, OverflowError, RecursionError) as error:
        raise ValueError(f"Invalid project manifest: {error}") from error
