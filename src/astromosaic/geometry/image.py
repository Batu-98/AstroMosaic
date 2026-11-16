"""Image-space layer transforms and composition settings in zero-based pixels."""

from dataclasses import dataclass
from math import ceil, cos, floor, isfinite, radians, sin

import numpy as np
from numpy.typing import NDArray

from astromosaic.core import Region

type Points = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class LayerPlacement:
    """Map foreground pixels into the sky grid with a similarity transform."""

    offset: tuple[float, float] = (0.0, 0.0)
    rotation_deg: float = 0.0
    scale: float = 1.0

    def __post_init__(self) -> None:
        if not all(isfinite(value) for value in (*self.offset, self.rotation_deg, self.scale)):
            raise ValueError("Layer placement values must be finite.")
        if self.scale <= 0:
            raise ValueError("Layer scale must be positive.")

    def _matrix(self) -> Points:
        angle = radians(self.rotation_deg % 360)
        c, s = cos(angle), sin(angle)
        return self.scale * np.array([[c, -s], [s, c]], dtype=np.float64)

    def forward(self, xy: Points) -> Points:
        return xy @ self._matrix().T + self.offset

    def inverse(self, xy: Points) -> Points:
        angle = radians(self.rotation_deg % 360)
        c, s = cos(angle), sin(angle)
        return np.asarray(((xy - self.offset) / self.scale) @ np.array([[c, -s], [s, c]]))


@dataclass(frozen=True, slots=True)
class CompositionSpec:
    placement: LayerPlacement = LayerPlacement()
    seam_y: float = 0.0
    overlap_percent: float = 10.0
    sky_crop_bottom: int = 0
    reference_panel: int | None = None
    placement_rms_px: float | None = None

    def __post_init__(self) -> None:
        if not isfinite(self.seam_y) or not 0 <= self.overlap_percent <= 100:
            raise ValueError("Enter a finite seam row and an overlap from 0 to 100 percent.")
        if self.sky_crop_bottom < 0:
            raise ValueError("The composition sky crop must be nonnegative.")
        if self.reference_panel is not None and self.reference_panel < 0:
            raise ValueError("Expected a valid reference panel index.")
        if self.placement_rms_px is not None and (
            not isfinite(self.placement_rms_px) or self.placement_rms_px < 0
        ):
            raise ValueError("Expected a nonnegative placement residual.")

    def frame(
        self, sky_size: tuple[int, int], ground_size: tuple[int, int]
    ) -> tuple[Region, float]:
        sky_width, sky_height = sky_size
        sky_height -= self.sky_crop_bottom
        if sky_height < 1:
            raise ValueError("The composition crop must retain at least one row of sky.")
        width, height = ground_size
        edges = np.array(
            [[-0.5, -0.5], [width - 0.5, -0.5], [-0.5, height - 0.5], [width - 0.5, height - 0.5]]
        )
        with np.errstate(over="ignore", invalid="ignore"):
            transformed = self.placement.forward(edges)
        if not np.isfinite(transformed).all() or np.max(np.abs(transformed)) > 2**32:
            raise ValueError("The transformed foreground exceeds the supported canvas range.")
        halves = np.rint(transformed + 0.5) - 0.5
        np.copyto(transformed, halves, where=np.abs(transformed - halves) < 1e-7)
        (left, top), (right, bottom) = transformed.min(axis=0), transformed.max(axis=0)
        x, y = min(0, floor(left + 0.5)), min(0, floor(top + 0.5))
        end_x = max(sky_width, ceil(right + 0.5))
        end_y = max(sky_height, ceil(bottom + 0.5))
        seam_width = min(sky_height, bottom - top) * self.overlap_percent / 100.0
        return Region(x, y, end_x - x, end_y - y), float(seam_width)
