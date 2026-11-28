"""Bounded projections of detector edges onto the prepared preview grid."""

from dataclasses import dataclass
from pathlib import Path
from time import monotonic

import numpy as np
from numpy.typing import NDArray

from astromosaic.core.job import JobContext
from astromosaic.geometry import PanelGeometry
from astromosaic.geometry.footprint import MAX_FOOTPRINT_COORDINATE

_MAX_VERTICES = 1024
_MAX_BATCH_VERTICES = 32768
_MAX_BYTES = 8 * 1024**2
_TIME_LIMIT = 0.2
_ERROR_PX = 0.125


@dataclass(frozen=True, slots=True)
class DetectorOutline:
    source: Path
    vertices: NDArray[np.float64] | None = None
    reason: str = ""


class OutlineBudget:
    def __init__(self, working_bytes: int) -> None:
        self.deadline = monotonic() + _TIME_LIMIT
        self.vertices = _MAX_BATCH_VERTICES
        self.bytes = min(working_bytes, _MAX_BYTES)

    def prepare(
        self,
        path: Path,
        source: PanelGeometry,
        target: PanelGeometry,
        size: tuple[int, int],
        shift: tuple[float, float],
        context: JobContext,
    ) -> DetectorOutline:
        width, height = size
        for intervals in (32, 64, 128, 256):
            context.check_cancelled()
            if monotonic() >= self.deadline:
                return DetectorOutline(path, reason="Outline preparation reached its time limit.")
            count = 4 * intervals
            if count > self.vertices or count * 768 > self.bytes:
                return DetectorOutline(
                    path, reason="Outline preparation reached its resource limit."
                )
            t = np.linspace(0, 1, 2 * intervals + 1)
            zeros, ones = np.zeros_like(t), np.ones_like(t)
            x = np.concatenate((t, ones, 1 - t, zeros)) * width - 0.5
            y = np.concatenate((zeros, t, ones, 1 - t)) * height - 0.5
            projected = target.inverse(source.forward(x, y)).reshape(4, t.size, 2)
            projected += (shift[0] + 0.5, shift[1] + 0.5)
            if (
                not np.isfinite(projected).all()
                or np.abs(projected).max() > MAX_FOOTPRINT_COORDINATE
            ):
                return DetectorOutline(path, reason="A detector edge has an unsafe sky projection.")
            ends = projected[:, ::2]
            delta = ends[:, 1:] - ends[:, :-1]
            relative = projected[:, 1::2] - ends[:, :-1]
            squared = np.sum(delta * delta, axis=-1)
            if (squared == 0).any():
                return DetectorOutline(path, reason="A projected detector edge is degenerate.")
            fraction = np.clip(np.sum(relative * delta, axis=-1) / squared, 0, 1)
            error = np.linalg.norm(relative - fraction[..., None] * delta, axis=-1).max()
            if error <= _ERROR_PX:
                vertices = np.ascontiguousarray(ends[:, :-1].reshape(count, 2))
                vertices.setflags(write=False)
                self.vertices -= len(vertices)
                self.bytes -= vertices.nbytes
                return DetectorOutline(path, vertices)
        return DetectorOutline(
            path, reason=f"Detector curvature exceeds the {_MAX_VERTICES}-vertex limit."
        )
