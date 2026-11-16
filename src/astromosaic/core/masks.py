"""Source-coordinate content masks with a separate unclassified state."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from astromosaic.core import Region

UNCLASSIFIED = 0
SKY = 1
FOREGROUND = 2
MASK_EDGE = 384
ForegroundTag = Literal["sky-only", "mixed"]
ForegroundSuggestion = Literal["sky-only", "uncertain", "mixed"]


def bounded_grid(size: tuple[int, int], edge: int) -> tuple[int, int]:
    width, height = size
    if min(width, height, edge) < 1:
        raise ValueError("Expected positive image and preview dimensions.")
    longest = max(width, height)
    if longest <= edge:
        return size
    return (
        max(1, (width * edge + longest // 2) // longest),
        max(1, (height * edge + longest // 2) // longest),
    )


def grid_cells(start: int, end: int, source_span: int, cells: int) -> NDArray[np.int64]:
    """Map source pixels to cells with edges at floor(i * source_span / cells)."""
    pixels = np.arange(start + 1, end + 1, dtype=np.int64)
    return (pixels * cells - 1) // source_span


@dataclass(frozen=True, slots=True)
class SourceMask:
    """Immutable mask raster whose cells partition the original source pixel grid."""

    source_size: tuple[int, int]
    labels: bytes

    def __post_init__(self) -> None:
        width, height = self.size
        if len(self.labels) != width * height or max(self.labels, default=0) > FOREGROUND:
            raise ValueError("Expected a source mask with one valid label per grid cell.")

    @property
    def size(self) -> tuple[int, int]:
        return bounded_grid(self.source_size, MASK_EDGE)

    @property
    def sky_fingerprint(self) -> str:
        width, height = self.source_size
        digest = sha256(f"source-sky-grid-v1:{width}:{height}:".encode("ascii"))
        digest.update(
            self.labels.translate(bytes.maketrans(bytes((FOREGROUND,)), bytes((UNCLASSIFIED,))))
        )
        return digest.hexdigest()

    def grid(self) -> NDArray[np.uint8]:
        width, height = self.size
        return np.frombuffer(self.labels, dtype=np.uint8).reshape(height, width)

    def read_labels(self, region: Region) -> NDArray[np.uint8]:
        source_width, source_height = self.source_size
        region.with_halo(source_width, source_height, 0)
        width, height = self.size
        columns = grid_cells(region.x, region.x + region.width, source_width, width)
        rows = grid_cells(region.y, region.y + region.height, source_height, height)
        return self.grid()[rows[:, None], columns]


def paint_stroke(
    grid: NDArray[np.uint8],
    start: tuple[int, int],
    end: tuple[int, int],
    label: int | None,
    radius: int,
) -> None:
    """Paint a circular brush or split the crossed columns at a hand-drawn horizon."""
    x0, y0 = start
    x1, y1 = end
    height, width = grid.shape
    steps = max(abs(x1 - x0), abs(y1 - y0)) + 1
    columns = np.rint(np.linspace(x0, x1, steps)).astype(np.intp)
    rows = np.rint(np.linspace(y0, y1, steps)).astype(np.intp)
    for x, y in zip(columns, rows, strict=True):
        if label is None:
            grid[:y, x] = SKY
            grid[y:, x] = FOREGROUND
        else:
            left, right = max(0, x - radius), min(width, x + radius + 1)
            top, bottom = max(0, y - radius), min(height, y + radius + 1)
            yy, xx = np.ogrid[top:bottom, left:right]
            np.copyto(
                grid[top:bottom, left:right],
                label,
                where=(xx - x) ** 2 + (yy - y) ** 2 <= radius**2,
            )
