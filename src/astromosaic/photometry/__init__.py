"""Relative photometric corrections in source coordinates."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


def normalized_pixel(values: NDArray[np.float64], length: int) -> NDArray[np.float64]:
    return 2 * np.clip(values, 0, length - 1) / max(length - 1, 1) - 1


@dataclass(frozen=True, slots=True)
class PanelCorrection:
    shift: tuple[float, float] = (0.0, 0.0)
    gain: float = 1.0
    background: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def apply(
        self,
        values: NDArray[np.float64],
        x: NDArray[np.float64],
        y: NDArray[np.float64],
        width: int,
        height: int,
    ) -> None:
        offset, gradient_x, gradient_y = self.background
        values *= self.gain
        values += offset
        if gradient_x:
            values += gradient_x * normalized_pixel(x, width)
        if gradient_y:
            values += gradient_y * normalized_pixel(y, height)
