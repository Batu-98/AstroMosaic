"""Read bounded windows from mono and RGB TIFF panels without color conversion."""

import os
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import IO, Literal

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray
from tifffile import (
    COMPRESSION,
    PHOTOMETRIC,
    PLANARCONFIG,
    PREDICTOR,
    TiffFile,
    TiffFrame,
    TiffPage,
)

from astromosaic.core import PanelDescriptor, Region, SourceFingerprint, Tile
from astromosaic.io.fits import FitsTileSource, open_fits_sky_mask, optional_header_text
from astromosaic.io.icc import MAX_ICC_BYTES, is_srgb_profile
from astromosaic.io.tiff_metadata import add_tiff_optical_metadata

DESCRIPTION_PREFIX = "AstroMosaic TIFF "
DESCRIPTION_VERSION = DESCRIPTION_PREFIX + "1\n"
COMPOSITION_VERSION = DESCRIPTION_PREFIX + "2\n"
DESCRIPTION_LIMIT = 128 * 1024
_LOSSLESS_CODECS = {
    COMPRESSION.NONE,
    COMPRESSION.LZW,
    COMPRESSION.ADOBE_DEFLATE,
    COMPRESSION.DEFLATE,
    COMPRESSION.PACKBITS,
}
_SCIENCE_DTYPES = (np.dtype("uint16"), np.dtype("int16"), np.dtype("float32"))


class _Segments:
    """Address strips and tiles without decoding unrelated parts of the image."""

    def __init__(
        self, page: TiffPage, stream: IO[bytes], size: int, byteorder: Literal["<", ">"]
    ) -> None:
        dtype = page.dtype
        if dtype is None or page.bitspersample != 8 * dtype.itemsize:
            raise ValueError("Expected whole-byte TIFF samples.")
        self.page = page
        self.stream = stream
        self.dtype = dtype.newbyteorder(byteorder)
        self.separate = page.planarconfig == PLANARCONFIG.SEPARATE
        self.planes = page.samplesperpixel if self.separate else 1
        self.block_samples = 1 if self.separate else page.samplesperpixel
        self.width, self.height = page.imagewidth, page.imagelength
        self.block_width = page.tilewidth if page.is_tiled else self.width
        self.block_height = (
            page.tilelength if page.is_tiled else min(page.rowsperstrip, self.height)
        )
        if (
            min(self.width, self.height, self.block_width, self.block_height) < 1
            or page.imagedepth != 1
            or (page.is_tiled and page.tiledepth != 1)
            or page.planarconfig not in (PLANARCONFIG.CONTIG, PLANARCONFIG.SEPARATE)
            or page.fillorder != 1
        ):
            raise ValueError(
                "Expected a nonempty two-dimensional TIFF raster with standard layout."
            )
        if page.compression not in _LOSSLESS_CODECS:
            raise ValueError("Expected uncompressed, LZW, Deflate, or PackBits TIFF data.")
        self.uncompressed = page.compression == COMPRESSION.NONE
        if page.predictor != PREDICTOR.NONE and (
            page.compression
            not in (COMPRESSION.LZW, COMPRESSION.ADOBE_DEFLATE, COMPRESSION.DEFLATE)
            or page.predictor
            != (PREDICTOR.FLOATINGPOINT if dtype.kind == "f" else PREDICTOR.HORIZONTAL)
        ):
            raise ValueError("Unsupported TIFF predictor for the compression and sample type.")

        self.columns = (self.width + self.block_width - 1) // self.block_width
        self.rows = (self.height + self.block_height - 1) // self.block_height
        offsets, counts = page.dataoffsets, page.databytecounts
        if len(offsets) != self.planes * self.rows * self.columns or len(counts) != len(offsets):
            raise ValueError("Incorrect number of TIFF segment offsets or byte counts.")
        self.pixel_bytes = self.block_samples * dtype.itemsize
        for index, (offset, count) in enumerate(zip(offsets, counts, strict=True)):
            if offset <= 0 or count <= 0 or offset + count > size:
                raise ValueError("A TIFF segment is missing or truncated.")
            if self.uncompressed:
                block_y = ((index // self.columns) % self.rows) * self.block_height
                rows = (
                    self.block_height
                    if page.is_tiled
                    else min(self.block_height, self.height - block_y)
                )
                if count < self.block_width * rows * self.pixel_bytes:
                    raise ValueError("An uncompressed TIFF segment is truncated.")
        # One compressed segment is live at a time, including encoded, decoded,
        # and predictor scratch buffers. Uncompressed data only need a row fragment.
        self.decode_bytes = (
            0
            if self.uncompressed
            else 2 * max(counts)
            + 4 * self.block_height * self.block_width * self.pixel_bytes
            + 64 * 1024
        )

    def _read(self, start: int, size: int) -> bytes:
        self.stream.seek(start)
        payload = self.stream.read(size)
        if len(payload) != size:
            raise ValueError("A TIFF segment is truncated.")
        return payload

    def _copy(
        self,
        index: int,
        x: int,
        y: int,
        out: NDArray[np.float32] | NDArray[np.uint8],
    ) -> None:
        height, width, _ = out.shape
        offset = self.page.dataoffsets[index]
        if self.uncompressed:
            stride = self.block_width * self.pixel_bytes
            start = offset + y * stride + x * self.pixel_bytes
            for row in range(height):
                payload = self._read(start + row * stride, width * self.pixel_bytes)
                out[row] = np.frombuffer(payload, dtype=self.dtype).reshape(
                    width, self.block_samples
                )
            return

        payload = self._read(offset, self.page.databytecounts[index])
        try:
            decoded, _, _ = self.page.decode(payload, index)
        except (RuntimeError, ValueError) as error:
            raise ValueError(f"Could not decode TIFF segment {index}: {error}") from error
        if decoded is None or decoded.shape[1] < y + height or decoded.shape[2] < x + width:
            raise ValueError("A decoded TIFF segment is truncated.")
        out[:] = decoded[0, y : y + height, x : x + width]

    def read_into(self, region: Region, out: NDArray[np.float32] | NDArray[np.uint8]) -> None:
        right, bottom = region.x + region.width, region.y + region.height
        blocks_per_plane = self.rows * self.columns
        for plane in range(self.planes):
            raster = out[:, :, plane : plane + 1] if self.separate else out
            for row in range(region.y // self.block_height, (bottom - 1) // self.block_height + 1):
                block_y = row * self.block_height
                y0, y1 = max(region.y, block_y), min(bottom, block_y + self.block_height)
                for col in range(region.x // self.block_width, (right - 1) // self.block_width + 1):
                    block_x = col * self.block_width
                    x0, x1 = max(region.x, block_x), min(right, block_x + self.block_width)
                    destination = raster[
                        y0 - region.y : y1 - region.y, x0 - region.x : x1 - region.x
                    ]
                    self._copy(
                        plane * blocks_per_plane + row * self.columns + col,
                        x0 - block_x,
                        y0 - block_y,
                        destination,
                    )


class TiffTileSource:
    def __init__(
        self,
        science: _Segments,
        descriptor: PanelDescriptor,
        header: fits.Header,
        max_tile_bytes: int,
        coverage: _Segments | None,
        sky_mask: FitsTileSource | None,
    ) -> None:
        self.descriptor = descriptor
        self._science = science
        self._header = header
        self._max_tile_bytes = max_tile_bytes
        self._coverage = coverage
        self._sky_mask = sky_mask
        self._decode_bytes = max(science.decode_bytes, coverage.decode_bytes if coverage else 0)

    @property
    def header(self) -> fits.Header:
        return self._header.copy()

    @property
    def sky_mask_fingerprint(self) -> SourceFingerprint | None:
        return self._sky_mask.descriptor.fingerprint if self._sky_mask is not None else None

    def tile_bytes(self, region: Region) -> int:
        mask_bytes = self._sky_mask.tile_bytes(region) if self._sky_mask is not None else 0
        # Float32 RGB, coverage and finite flags, and a raw row fragment.
        raster_bytes = 32 * region.width * region.height + 24 * region.width
        return raster_bytes + max(self._decode_bytes, mask_bytes)

    def read_tile(self, region: Region, *, halo: int = 0) -> Tile:
        panel = self.descriptor
        region = region.with_halo(panel.width, panel.height, halo)
        if self.tile_bytes(region) > self._max_tile_bytes:
            raise ValueError(
                "The TIFF tile and its codec buffers exceed the configured byte budget."
            )
        channels = self._science.page.samplesperpixel
        pixels = np.empty((region.height, region.width, channels), dtype=np.float32)
        self._science.read_into(region, pixels)
        valid = np.isfinite(pixels).all(axis=-1)
        if self._coverage is not None:
            coverage = np.empty((region.height, region.width, 1), dtype=np.uint8)
            self._coverage.read_into(region, coverage)
            if np.any(coverage > 1):
                raise ValueError("Expected binary values in the TIFF coverage image.")
            valid &= coverage[..., 0] == 1
        if self._sky_mask is not None:
            valid &= self._sky_mask.read_binary_mask(region)
        pixels[~valid] = np.nan
        return Tile(region, pixels[..., 0] if channels == 1 else pixels, valid)


def _check_orientation(page: TiffPage) -> None:
    if page.tags.valueof("Orientation", 1) != 1:
        raise ValueError("Expected top-left TIFF orientation (Orientation 1).")


def _icc_encoding(page: TiffPage) -> Literal["srgb", "unsupported"] | None:
    tag = page.tags.get(34675)
    if tag is None:
        return None
    if page.dtype == np.dtype("uint16") and tag.valuebytecount <= MAX_ICC_BYTES:
        profile = tag.value
        if isinstance(profile, bytes) and is_srgb_profile(profile):
            return "srgb"
    return "unsupported"


def _read_metadata(page: TiffPage) -> tuple[fits.Header, TiffPage | None]:
    description = page.description
    if not description.startswith(DESCRIPTION_PREFIX):
        if page.subifds:
            raise ValueError("Unsupported TIFF subimages in a linear panel.")
        return fits.Header(), None
    composition = description.startswith(COMPOSITION_VERSION)
    prefix = COMPOSITION_VERSION if composition else DESCRIPTION_VERSION
    if not description.startswith(prefix) or len(description) > DESCRIPTION_LIMIT:
        raise ValueError("Unsupported AstroMosaic TIFF metadata version or size.")
    header = fits.Header.fromstring(description.removeprefix(prefix), sep="\n")
    if header.get("BSCALE", 1.0) != 1.0 or header.get("BZERO", 0.0) != 0.0 or "BLANK" in header:
        raise ValueError("TIFF metadata must describe unscaled samples without a BLANK value.")
    if not page.subifds and not composition:
        return header, None
    subimages = page.pages
    expected = 2 if composition else 1
    if subimages is None or not page.subifds or len(page.subifds) != expected:
        raise ValueError("Expected the TIFF coverage and any declared layer subimages.")
    coverage = _byte_subimage(page, subimages[0])
    if composition:
        _byte_subimage(page, subimages[1])
    return header, coverage


def _byte_subimage(page: TiffPage, coverage: TiffPage | TiffFrame) -> TiffPage:
    if (
        not isinstance(coverage, TiffPage)
        or coverage.dtype != np.dtype("uint8")
        or coverage.photometric != PHOTOMETRIC.MINISBLACK
        or coverage.samplesperpixel != 1
        or (coverage.imagewidth, coverage.imagelength) != (page.imagewidth, page.imagelength)
        or coverage.subifds
    ):
        raise ValueError("Expected a byte subimage matching the TIFF panel dimensions.")
    _check_orientation(coverage)
    return coverage


@contextmanager
def open_tiff_panel(
    path: Path, *, max_tile_bytes: int = 32 * 1024**2, sky_mask: Path | None = None
) -> Iterator[TiffTileSource]:
    if max_tile_bytes < 1:
        raise ValueError("The TIFF tile byte budget must be positive.")
    with path.open("rb") as stream, TiffFile(stream) as tiff, ExitStack() as masks:
        stat = os.fstat(stream.fileno())
        if len(tiff.pages) != 1:
            raise ValueError("Expected one primary TIFF image.")
        page = tiff.pages[0]
        assert isinstance(page, TiffPage)
        _check_orientation(page)
        rgb = page.photometric == PHOTOMETRIC.RGB and page.samplesperpixel == 3
        mono = page.photometric == PHOTOMETRIC.MINISBLACK and page.samplesperpixel == 1
        if not (mono or rgb) or page.extrasamples or page.dtype not in _SCIENCE_DTYPES:
            raise ValueError("Expected 16-bit integer or float32 TIFF with mono or RGB samples.")
        science = _Segments(page, stream, stat.st_size, tiff.byteorder)
        header, coverage_page = _read_metadata(page)
        header = add_tiff_optical_metadata(page, header)
        coverage = None
        mask = None
        provenance: tuple[str, ...] = ("finite-raw-pixels",)
        if coverage_page is not None:
            coverage = _Segments(coverage_page, stream, stat.st_size, tiff.byteorder)
            provenance += ("tiff-coverage-subifd",)
        if sky_mask is not None:
            mask = masks.enter_context(open_fits_sky_mask(sky_mask, science.width, science.height))
            provenance += ("supplied-sky-mask",)
        descriptor = PanelDescriptor(
            fingerprint=SourceFingerprint(stat.st_size, stat.st_mtime_ns),
            width=science.width,
            height=science.height,
            channel_layout="rgb" if rgb else "mono",
            filter_name=optional_header_text(header, "FILTER"),
            unit=optional_header_text(header, "BUNIT"),
            bitpix=-32 if science.dtype.kind == "f" else 16,
            bscale=1.0,
            bzero=0.0,
            wcs_provenance="tiff-description"
            if optional_header_text(header, "CTYPE1") and optional_header_text(header, "CTYPE2")
            else None,
            blank=None,
            mask_provenance=provenance,
            icc_encoding=_icc_encoding(page),
        )
        yield TiffTileSource(science, descriptor, header, max_tile_bytes, coverage, mask)
