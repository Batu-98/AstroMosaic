"""Read linear panels through a common bounded tile interface."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

from astropy.io.fits import Header

from astromosaic.core import PanelDescriptor, Region, SourceFingerprint, Tile
from astromosaic.io.fits import open_fits_panel

TIFF_SUFFIXES = {".tif", ".tiff"}


class PanelSource(Protocol):
    @property
    def descriptor(self) -> PanelDescriptor: ...
    @property
    def header(self) -> Header: ...
    @property
    def sky_mask_fingerprint(self) -> SourceFingerprint | None: ...
    def tile_bytes(self, region: Region) -> int: ...
    def read_tile(self, region: Region, *, halo: int = 0) -> Tile: ...


@contextmanager
def open_panel(
    path: Path, *, max_tile_bytes: int = 32 * 1024**2, sky_mask: Path | None = None
) -> Iterator[PanelSource]:
    if path.suffix.lower() in TIFF_SUFFIXES:
        from astromosaic.io.tiff import open_tiff_panel

        with open_tiff_panel(path, max_tile_bytes=max_tile_bytes, sky_mask=sky_mask) as source:
            yield source
    else:
        with open_fits_panel(
            path, max_tile_bytes=max_tile_bytes, memmap=False, sky_mask=sky_mask
        ) as source:
            yield source
