"""Read bounded windows from uncompressed monolithic XISF images."""

import os
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from struct import Struct
from typing import IO
from xml.etree import ElementTree as ET

import numpy as np
from astropy.io import fits
from astropy.io.fits.verify import VerifyError
from numpy.typing import NDArray

from astromosaic.astrometry.hints import (
    nina_writer_version,
    positive_header_number,
    positive_number,
)
from astromosaic.core import PanelDescriptor, Region, SourceFingerprint, Tile
from astromosaic.io.fits import FitsTileSource, open_fits_sky_mask, optional_header_text

NAMESPACE = "http://www.pixinsight.com/xisf"
SIGNATURE = b"XISF0100"
PREAMBLE = Struct("<8sII")
MAX_HEADER_BYTES = 1024**2
COVERAGE_ID = "AstroMosaicCoverage"
LAYERS_ID = "AstroMosaicLayers"
_NS = f"{{{NAMESPACE}}}"
_DTYPES = {"Float32": "f4", "UInt16": "u2", "UInt8": "u1"}
_REAL_PROPERTY_TYPES = {
    "Float32",
    "Float64",
    "Int8",
    "Int16",
    "Int32",
    "Int64",
    "UInt8",
    "UInt16",
    "UInt32",
    "UInt64",
}
_STRUCTURAL_KEYWORDS = {
    "SIMPLE",
    "XTENSION",
    "BITPIX",
    "NAXIS",
    "EXTEND",
    "PCOUNT",
    "GCOUNT",
    "BSCALE",
    "BZERO",
    "BLANK",
    "CHECKSUM",
    "DATASUM",
    "CONTINUE",
    "END",
}


@dataclass(frozen=True, slots=True)
class _Attachment:
    width: int
    height: int
    channels: int
    dtype: np.dtype[np.generic]
    offset: int
    size: int
    planar: bool

    def read_into(
        self, stream: IO[bytes], region: Region, out: NDArray[np.float32] | NDArray[np.uint8]
    ) -> None:
        planes = self.channels if self.planar else 1
        samples = self.channels // planes
        pixel_bytes = samples * self.dtype.itemsize
        row_bytes = region.width * pixel_bytes
        stride = self.width * pixel_bytes
        for plane in range(planes):
            destination = out[..., plane : plane + 1] if self.planar else out
            start = self.offset + (plane * self.height + region.y) * stride
            start += region.x * pixel_bytes
            for row in range(region.height):
                stream.seek(start + row * stride)
                data = stream.read(row_bytes)
                if len(data) != row_bytes:
                    raise ValueError("The XISF attachment was truncated during reading.")
                destination[row] = np.frombuffer(data, self.dtype).reshape(region.width, samples)


def _read_header(stream: IO[bytes], file_size: int) -> tuple[ET.Element, int]:
    preamble = stream.read(PREAMBLE.size)
    if len(preamble) != PREAMBLE.size:
        raise ValueError("The XISF file header is truncated.")
    signature, size, reserved = PREAMBLE.unpack(preamble)
    if signature != SIGNATURE or reserved != 0:
        raise ValueError("Expected a monolithic XISF 1.0 file.")
    end = PREAMBLE.size + size
    if not 0 < size <= MAX_HEADER_BYTES or end > file_size:
        raise ValueError("The XISF XML header is truncated or exceeds its size limit.")
    try:
        xml = stream.read(size).decode("utf-8")
        if "<!DOCTYPE" in xml:
            raise ValueError("XISF XML headers must omit document type declarations.")
        root = ET.fromstring(xml)
    except (UnicodeError, ET.ParseError) as error:
        raise ValueError("The XISF XML header is invalid.") from error
    if root.tag != f"{_NS}xisf" or root.get("version") != "1.0":
        raise ValueError("Expected an XISF 1.0 XML header.")
    return root, end


def _read_attachment(image: ET.Element, header_end: int, file_size: int) -> _Attachment:
    try:
        width, height, channels = map(int, image.get("geometry", "").split(":"))
    except ValueError as error:
        raise ValueError("Expected two-dimensional XISF image geometry.") from error
    color_space = image.get("colorSpace", "Gray")
    if min(width, height) < 1 or (channels, color_space) not in ((1, "Gray"), (3, "RGB")):
        raise ValueError("Expected a nonempty grayscale or RGB XISF image.")

    sample_format = image.get("sampleFormat", "")
    storage = image.get("pixelStorage", "Planar")
    byte_order = image.get("byteOrder", "little")
    if sample_format not in _DTYPES or storage not in ("Planar", "Normal"):
        raise ValueError("Unsupported XISF sample format or pixel storage.")
    if byte_order not in ("little", "big"):
        raise ValueError("Unsupported XISF byte order.")
    if "compression" in image.attrib or "subblocks" in image.attrib:
        raise ValueError("Save the XISF image without compression or use linear FITS or TIFF.")
    dtype = np.dtype(("<" if byte_order == "little" else ">") + _DTYPES[sample_format])
    location = image.get("location", "").split(":")
    if len(location) != 3 or location[0] != "attachment":
        raise ValueError("Expected a local XISF image attachment.")
    try:
        offset, size = map(int, location[1:])
    except ValueError as error:
        raise ValueError("The XISF attachment position or length is invalid.") from error
    if offset < header_end or size != width * height * channels * dtype.itemsize:
        raise ValueError("The XISF attachment position or length does not match its image.")
    if offset + size > file_size:
        raise ValueError("The XISF image attachment is truncated.")
    return _Attachment(width, height, channels, dtype, offset, size, storage == "Planar")


def _fits_keywords(image: ET.Element) -> fits.Header:
    header = fits.Header()
    for keyword in image.findall(f"{_NS}FITSKeyword"):
        name = keyword.get("name", "").strip().upper()
        if name in _STRUCTURAL_KEYWORDS or (name.startswith("NAXIS") and name[5:].isdigit()):
            continue
        value = keyword.get("value", "").strip()
        comment = keyword.get("comment", "")
        try:
            if name in ("COMMENT", "HISTORY"):
                header.append((name, comment or value))
            elif name:
                if value.startswith("'") and value.endswith("'") and len(value) >= 2:
                    parsed = value[1:-1].replace("''", "'")
                else:
                    parsed = fits.Card.fromstring(f"VALUE   = {value}").value
                header.append((name, parsed, comment))
        except (TypeError, ValueError, VerifyError) as error:
            raise ValueError(f"Invalid XISF FITS keyword {name}.") from error
    return header


def _add_image_properties(image: ET.Element, header: fits.Header) -> None:
    properties = {element.get("id", ""): element for element in image.findall(f"{_NS}Property")}

    def number(element: ET.Element) -> float | None:
        if element.get("type") in _REAL_PROPERTY_TYPES:
            return positive_header_number(element.get("value"))
        return None

    focal = properties.get("Instrument:Telescope:FocalLength")
    nina = nina_writer_version(header)
    # Older N.I.N.A. versions wrote the value in millimeters instead of meters.
    if (
        focal is not None
        and positive_header_number(header.get("FOCALLEN")) is None
        and (nina is None or nina >= (1, 10))
        and (meters := number(focal)) is not None
        and (millimeters := positive_number(meters * 1000)) is not None
    ):
        header["FOCALLEN"] = (millimeters, "XISF telescope focal length [mm]")

    for axis in ("X", "Y"):
        binning = properties.get(f"Instrument:Camera:{axis}Binning")
        key = f"{axis}BINNING"
        if binning is not None and positive_header_number(header.get(key)) is None:
            factor = number(binning)
            header[key] = (factor if factor is not None else 0, "XISF camera binning")
        pixel = properties.get(f"Instrument:Sensor:{axis}PixelSize")
        key = f"{axis}PIXSZ"
        if (
            pixel is not None
            and positive_header_number(header.get(key)) is None
            and (pitch := number(pixel)) is not None
        ):
            note = pixel.get("comment", "").strip()
            if not note.isascii() or not note.isprintable():
                note = ""
            header[key] = (pitch, f"XISF pixel pitch [um] {note[:96]}".strip())

    for property_id, key in (
        ("Instrument:Camera:Name", "INSTRUME"),
        ("Instrument:Telescope:Name", "TELESCOP"),
        ("Instrument:Filter:Name", "FILTER"),
    ):
        element = properties.get(property_id)
        if element is None or element.get("type") != "String" or optional_header_text(header, key):
            continue
        value = (element.text or element.get("value") or "").strip()
        if value and value.isascii() and value.isprintable():
            header[key] = (value, f"XISF {property_id}")


class XisfTileSource:
    def __init__(
        self,
        stream: IO[bytes],
        science: _Attachment,
        descriptor: PanelDescriptor,
        header: fits.Header,
        max_tile_bytes: int,
        coverage: _Attachment | None,
        sky_mask: FitsTileSource | None,
    ) -> None:
        self._stream = stream
        self._science = science
        self.descriptor = descriptor
        self._header = header
        self._max_tile_bytes = max_tile_bytes
        self._coverage = coverage
        self._sky_mask = sky_mask

    @property
    def header(self) -> fits.Header:
        return self._header.copy()

    @property
    def sky_mask_fingerprint(self) -> SourceFingerprint | None:
        return self._sky_mask.descriptor.fingerprint if self._sky_mask is not None else None

    def tile_bytes(self, region: Region) -> int:
        mask_bytes = self._sky_mask.tile_bytes(region) if self._sky_mask is not None else 0
        # Float32 pixels, finite flags, coverage, and two raw row fragments.
        return 32 * region.width * region.height + 24 * region.width + mask_bytes

    def read_tile(self, region: Region, *, halo: int = 0) -> Tile:
        panel = self.descriptor
        region = region.with_halo(panel.width, panel.height, halo)
        if self.tile_bytes(region) > self._max_tile_bytes:
            raise ValueError("The XISF tile exceeds the configured byte budget.")
        channels = self._science.channels
        pixels = np.empty((region.height, region.width, channels), dtype=np.float32)
        self._science.read_into(self._stream, region, pixels)
        valid = np.isfinite(pixels).all(axis=-1)
        if self._coverage is not None:
            coverage = np.empty((*valid.shape, 1), dtype=np.uint8)
            self._coverage.read_into(self._stream, region, coverage)
            if np.any(coverage > 1):
                raise ValueError("Expected binary values in the XISF coverage image.")
            valid &= coverage[..., 0] == 1
        if self._sky_mask is not None:
            valid &= self._sky_mask.read_binary_mask(region)
        pixels[~valid] = np.nan
        return Tile(region, pixels[..., 0] if channels == 1 else pixels, valid)


@contextmanager
def open_xisf_panel(
    path: Path, *, max_tile_bytes: int = 32 * 1024**2, sky_mask: Path | None = None
) -> Iterator[XisfTileSource]:
    if max_tile_bytes < 1:
        raise ValueError("The XISF tile byte budget must be positive.")
    with path.open("rb") as stream, ExitStack() as masks:
        stat = os.fstat(stream.fileno())
        root, end = _read_header(stream, stat.st_size)
        images = root.findall(f"{_NS}Image")
        if not images or images[0].get("sampleFormat") not in ("Float32", "UInt16"):
            raise ValueError("Expected a Float32 or UInt16 primary XISF image.")
        science = _read_attachment(images[0], end, stat.st_size)
        ancillary: dict[str, _Attachment] = {}
        for image in images[1:]:
            name = image.get("id", "")
            if name not in (COVERAGE_ID, LAYERS_ID) or name in ancillary:
                raise ValueError("Expected one XISF science image and any AstroMosaic masks.")
            attachment = _read_attachment(image, end, stat.st_size)
            if (attachment.width, attachment.height, attachment.channels) != (
                science.width,
                science.height,
                1,
            ) or attachment.dtype != np.dtype("uint8"):
                raise ValueError("Expected an XISF byte mask matching the science image.")
            ancillary[name] = attachment
        coverage = ancillary.get(COVERAGE_ID)
        if LAYERS_ID in ancillary and coverage is None:
            raise ValueError("The XISF contribution image requires a coverage image.")
        attachments = sorted((science, *ancillary.values()), key=lambda item: item.offset)
        if any(a.offset + a.size > b.offset for a, b in pairwise(attachments)):
            raise ValueError("The XISF image attachments overlap.")

        header = _fits_keywords(images[0])
        _add_image_properties(images[0], header)
        provenance: tuple[str, ...] = ("finite-raw-pixels",)
        if coverage is not None:
            provenance += ("xisf-coverage-image",)
        mask = None
        if sky_mask is not None:
            mask = masks.enter_context(open_fits_sky_mask(sky_mask, science.width, science.height))
            provenance += ("supplied-sky-mask",)
        descriptor = PanelDescriptor(
            fingerprint=SourceFingerprint(stat.st_size, stat.st_mtime_ns),
            width=science.width,
            height=science.height,
            channel_layout="rgb" if science.channels == 3 else "mono",
            filter_name=optional_header_text(header, "FILTER"),
            unit=optional_header_text(header, "BUNIT"),
            bitpix=-32 if science.dtype.kind == "f" else 16,
            bscale=1.0,
            bzero=0.0,
            wcs_provenance="xisf-fits-keywords"
            if optional_header_text(header, "CTYPE1") and optional_header_text(header, "CTYPE2")
            else None,
            blank=None,
            mask_provenance=provenance,
        )
        yield XisfTileSource(stream, science, descriptor, header, max_tile_bytes, coverage, mask)
