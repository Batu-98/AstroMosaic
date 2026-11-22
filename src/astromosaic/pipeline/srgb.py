"""Decode known sRGB panels for diagnostics and reference tools."""

from astromosaic.io import PanelSource
from astromosaic.pipeline.photo_color import PhotoColor, PhotoTileSource


class SrgbTileSource(PhotoTileSource):
    def __init__(self, source: PanelSource, max_tile_bytes: int) -> None:
        super().__init__(source, PhotoColor("srgb", "embedded"), max_tile_bytes)
