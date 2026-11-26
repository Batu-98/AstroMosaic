"""Prepare shared working colors and corrections for the sky photo workflow."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from astromosaic.core.job import JobContext
from astromosaic.geometry import PanelGeometry
from astromosaic.io import PanelSource
from astromosaic.photometry import PanelCorrection
from astromosaic.photometry.photo_settings import PhotoProfile, PhotoSettings, validate_photo_ev
from astromosaic.pipeline.photo_color import PhotoTileSource, resolve_photo_profile
from astromosaic.pipeline.photo_fit import PhotoPanel, PhotoReport, prepare_photo_fit

if TYPE_CHECKING:
    from astromosaic.pipeline.mosaic import RenderSpec

type SkyRenderIntent = Literal["scientific", "preview", "photo"]


@dataclass(frozen=True, slots=True)
class PhotoInputs:
    settings: PhotoSettings = PhotoSettings()
    profiles: Mapping[int, PhotoProfile] = field(default_factory=dict)
    exposure_ev: Mapping[int, float] = field(default_factory=dict)


class PhotoPreparation:
    """Track profiles for one job and prepare corrections after framing."""

    def __init__(
        self,
        inputs: PhotoInputs | None,
        *,
        panel_count: int,
        intent: SkyRenderIntent,
        max_working_bytes: int,
    ) -> None:
        self._inputs = inputs if inputs is not None else PhotoInputs()
        if any(
            index not in range(panel_count)
            for index in (*self._inputs.profiles, *self._inputs.exposure_ev)
        ):
            raise ValueError("Photo settings indices must refer to input panels.")
        self._intent = intent
        self._max_working_bytes = max_working_bytes
        self._profile_bytes = 0

    @property
    def visual_allowed(self) -> bool:
        return self._intent != "scientific"

    @property
    def profile_bytes(self) -> int:
        return self._profile_bytes

    def _reserve_profile(self, profile: bytes, origin: Literal["embedded", "assigned"]) -> None:
        self._profile_bytes += len(profile)
        if self._profile_bytes > self._max_working_bytes // 4:
            raise ValueError(f"The {origin} ICC profiles exceed the working byte budget.")

    def reserve_embedded_profile(self, source: PanelSource) -> None:
        metadata = source.photo_metadata
        if metadata is not None and metadata.embedded_icc is not None:
            self._reserve_profile(metadata.embedded_icc, "embedded")

    def prepare_panels(
        self,
        panels: Iterable[tuple[Path, PanelSource, PanelGeometry]],
        context: JobContext,
        *,
        refinement_requested: bool,
    ) -> list[PhotoPanel]:
        """Return the photo inputs in source order when visual processing applies."""
        if not self.visual_allowed:
            return []
        opened = tuple(panels)
        settings = self._inputs.settings
        if self._intent == "preview" and not (
            settings.profile.mode != "auto"
            or self._inputs.profiles
            or any(
                source.descriptor.icc_encoding is not None
                or (source.photo_metadata is not None and source.photo_metadata.exif_srgb)
                for _, source, _ in opened
            )
        ):
            return []

        prepared = []
        for index, (path, source, geometry) in enumerate(opened):
            context.check_cancelled()
            assignment = self._inputs.profiles.get(index)
            ev = self._inputs.exposure_ev.get(index, 0.0)
            try:
                validate_photo_ev(ev)
                color = resolve_photo_profile(source, assignment, settings.profile)
                metadata = source.photo_metadata
                if color.matrix_profile is not None and (
                    metadata is None or color.matrix_profile is not metadata.embedded_icc
                ):
                    self._reserve_profile(color.matrix_profile, "assigned")
            except (OSError, ValueError) as error:
                raise ValueError(f"{path.name} {error}") from error
            working_source = PhotoTileSource(source, color, self._max_working_bytes)
            prepared.append(PhotoPanel(path, working_source, geometry, color, ev))
        if refinement_requested:
            activity = "photo export" if self._intent == "photo" else "preview"
            raise ValueError(f"Disable relative refinement in Mosaic Settings for sRGB {activity}.")
        return prepared

    def fit(
        self,
        panels: Sequence[PhotoPanel],
        spec: RenderSpec,
        target: PanelGeometry,
        context: JobContext,
    ) -> tuple[list[PanelCorrection | None], PhotoReport]:
        settings = self._inputs.settings
        if spec.crop is not None and settings.brightness != "off":
            target = PanelGeometry(replace(spec, crop=None).output_wcs(), target.frame)
        return prepare_photo_fit(
            panels, settings, target, spec.size, self._max_working_bytes - self._profile_bytes, context
        )
