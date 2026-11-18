"""Write linear XISF tiles with embedded FITS keywords and separate mask images."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from shutil import disk_usage
from typing import IO
from xml.etree import ElementTree as ET

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray

from astromosaic.core import Tile
from astromosaic.io import XISF_SUFFIX
from astromosaic.io.atomic import atomic_binary_file
from astromosaic.io.raster import RasterMosaicWriter
from astromosaic.io.xisf import (
    COVERAGE_ID,
    LAYERS_ID,
    MAX_HEADER_BYTES,
    NAMESPACE,
    PREAMBLE,
    SIGNATURE,
)

_BLOCK_ALIGNMENT = 4096


class _XisfMosaicWriter(RasterMosaicWriter):
    def __init__(
        self, stream: IO[bytes], width: int, pixels: int, coverage: int, layers: int | None
    ) -> None:
        super().__init__(stream, width, pixels, coverage, "<f4", layers)
        self.lower = 0.0
        self.upper = 1.0

    def write(self, tile: Tile, contributions: NDArray[np.uint8] | None = None) -> None:
        super().write(tile, contributions)
        valid = tile.valid if tile.pixels.ndim == 2 else tile.valid[..., None]
        self.lower = float(np.min(tile.pixels, where=valid, initial=self.lower))
        self.upper = float(np.max(tile.pixels, where=valid, initial=self.upper))


def _keywords(image: ET.Element, header: fits.Header) -> None:
    for card in header.cards:
        name, value, comment = card.keyword, card.value, card.comment
        if name in ("HISTORY", "COMMENT"):
            value, comment = "", str(value)
        elif isinstance(value, str):
            value = "'" + value.replace("'", "''") + "'"
        else:
            value = fits.Card("VALUE", value).image[10:].strip()
        if name:
            ET.SubElement(image, "FITSKeyword", name=name, value=value, comment=comment)


def _aligned(position: int) -> int:
    return (position + _BLOCK_ALIGNMENT - 1) // _BLOCK_ALIGNMENT * _BLOCK_ALIGNMENT


@contextmanager
def open_xisf_mosaic(
    path: Path,
    width: int,
    height: int,
    channels: int,
    header: fits.Header,
    max_output_bytes: int,
    *,
    layers: bool = False,
    publish_check: Callable[[], None] | None = None,
) -> Iterator[RasterMosaicWriter]:
    path = path.absolute()
    if path.suffix.lower() != XISF_SUFFIX:
        raise ValueError("The XISF output path must end in .xisf.")
    if min(width, height) < 1 or channels not in (1, 3):
        raise ValueError("Expected a nonempty mono or RGB XISF mosaic.")
    root = ET.Element("xisf", {"xmlns": NAMESPACE, "version": "1.0"})
    science = ET.SubElement(
        root,
        "Image",
        geometry=f"{width}:{height}:{channels}",
        sampleFormat="Float32",
        colorSpace="Gray" if channels == 1 else "RGB",
        pixelStorage="Normal",
        bounds="0:1",
    )
    _keywords(science, header)
    pixel_count = width * height
    blocks = [(science, 4 * channels * pixel_count)]
    for name in (COVERAGE_ID, LAYERS_ID) if layers else (COVERAGE_ID,):
        image = ET.SubElement(
            root,
            "Image",
            id=name,
            geometry=f"{width}:{height}:1",
            sampleFormat="UInt8",
            colorSpace="Gray",
        )
        blocks.append((image, pixel_count))
    metadata = ET.SubElement(root, "Metadata")
    ET.SubElement(
        metadata,
        "Property",
        id="XISF:CreationTime",
        type="TimePoint",
        value=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    ET.SubElement(
        metadata, "Property", id="XISF:CreatorApplication", type="String"
    ).text = f"AstroMosaic {version('astromosaic')}"
    ET.SubElement(
        metadata,
        "Property",
        id="XISF:BlockAlignmentSize",
        type="UInt16",
        value=str(_BLOCK_ALIGNMENT),
    )
    for image, size in blocks:
        image.set("location", f"attachment:0:{size}")
    header_size = len(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    # Reserve room for offsets and float bounds before assigning the block locations.
    position = PREAMBLE.size + header_size + 128
    offsets = []
    for image, size in blocks:
        offset = _aligned(position)
        offsets.append(offset)
        image.set("location", f"attachment:{offset}:{size}")
        position = offset + size
    if position > max_output_bytes:
        raise ValueError("The XISF mosaic exceeds the configured output byte limit.")
    if position > disk_usage(path.parent).free:
        raise OSError("There is insufficient disk space for the XISF mosaic.")

    with atomic_binary_file(path, publish_check=publish_check) as stream:
        stream.truncate(position)
        writer = _XisfMosaicWriter(
            stream, width, offsets[0], offsets[1], offsets[2] if layers else None
        )
        yield writer
        science.set("bounds", f"{writer.lower:.17g}:{writer.upper:.17g}")
        xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        if len(xml) > MAX_HEADER_BYTES or PREAMBLE.size + len(xml) > offsets[0]:
            raise ValueError("The XISF mosaic metadata exceeds its size limit.")
        stream.seek(0)
        stream.write(PREAMBLE.pack(SIGNATURE, len(xml), 0))
        stream.write(xml)
