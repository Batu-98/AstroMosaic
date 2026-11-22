"""Read linear panels through a common bounded tile interface."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import numpy as np
from astropy.io.fits import Header

from astromosaic.core import PanelDescriptor, Region, SourceFingerprint, Tile
from astromosaic.core.masks import FOREGROUND, SKY, SourceMask
from astromosaic.io.fits import open_fits_panel

if TYPE_CHECKING:
    from astromosaic.io.tiff_metadata import TiffPhotoMetadata

TIFF_SUFFIXES = {".tif", ".tiff"}
XISF_SUFFIX = ".xisf"
SkyMask = Path | SourceMask


class PanelSource(Protocol):
    @property
    def descriptor(self) -> PanelDescriptor: ...
    @property
    def header(self) -> Header: ...
    @property
    def sky_mask_fingerprint(self) -> SourceFingerprint | str | None: ...
    @property
    def photo_metadata(self) -> "TiffPhotoMetadata | None": ...
    def tile_bytes(self, region: Region) -> int: ...
    def read_tile(self, region: Region, *, halo: int = 0) -> Tile: ...


class _ContentSelectedSource:
    def __init__(
        self, source: PanelSource, mask: SourceMask, label: int, max_tile_bytes: int
    ) -> None:
        panel = source.descriptor
        if mask.source_size != (panel.width, panel.height):
            raise ValueError("The saved content mask does not match the source dimensions.")
        provenance = "project-sky-mask" if label == SKY else "project-foreground-mask"
        self.descriptor = replace(panel, mask_provenance=panel.mask_provenance + (provenance,))
        self.sky_mask_fingerprint = mask.sky_fingerprint if label == SKY else None
        self.photo_metadata = source.photo_metadata
        self._source = source
        self._mask = mask
        self._label = label
        self._max_tile_bytes = max_tile_bytes

    @property
    def header(self) -> Header:
        return self._source.header

    def tile_bytes(self, region: Region) -> int:
        mask_bytes = 2 * region.width * region.height + 32 * (region.width + region.height)
        return self._source.tile_bytes(region) + mask_bytes

    def read_tile(self, region: Region, *, halo: int = 0) -> Tile:
        actual = region.with_halo(self.descriptor.width, self.descriptor.height, halo)
        if self.tile_bytes(actual) > self._max_tile_bytes:
            raise ValueError("The content-selected tile exceeds the configured byte budget.")
        tile = self._source.read_tile(actual)
        np.logical_and(tile.valid, self._mask.read_labels(actual) == self._label, out=tile.valid)
        tile.pixels[~tile.valid] = np.nan
        return tile


@contextmanager
def open_panel(
    path: Path,
    *,
    max_tile_bytes: int = 32 * 1024**2,
    sky_mask: SkyMask | None = None,
    foreground_mask: SourceMask | None = None,
    keep_icc: bool = False,
) -> Iterator[PanelSource]:
    if sky_mask is not None and foreground_mask is not None:
        raise ValueError("Choose one content selection per source reader.")
    supplied = sky_mask if isinstance(sky_mask, Path) else None
    opened: AbstractContextManager[PanelSource]
    suffix = path.suffix.lower()
    if suffix in TIFF_SUFFIXES:
        from astromosaic.io.tiff import open_tiff_panel

        opened = open_tiff_panel(
            path, max_tile_bytes=max_tile_bytes, sky_mask=supplied, keep_icc=keep_icc
        )
    elif suffix == XISF_SUFFIX:
        from astromosaic.io.xisf import open_xisf_panel

        opened = open_xisf_panel(path, max_tile_bytes=max_tile_bytes, sky_mask=supplied)
    else:
        opened = open_fits_panel(
            path, max_tile_bytes=max_tile_bytes, memmap=False, sky_mask=supplied
        )
    with opened as source:
        if isinstance(sky_mask, SourceMask):
            yield _ContentSelectedSource(source, sky_mask, SKY, max_tile_bytes)
        elif foreground_mask is not None:
            yield _ContentSelectedSource(source, foreground_mask, FOREGROUND, max_tile_bytes)
        else:
            yield source
