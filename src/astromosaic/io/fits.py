"""Read bounded sections of uncompressed monochrome FITS images."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from math import isfinite
from pathlib import Path
from typing import cast

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray

from astromosaic.core import PanelDescriptor, Region, SourceFingerprint, Tile

_DEFAULT_TILE_BUDGET = 32 * 1024**2
# Allow for the raw section and its assembly, float64 scaling, pixels, and mask temporaries.
_TILE_BYTES_PER_PIXEL = 64
# Astropy assembles strided rectangles from a list of row arrays.
_TILE_BYTES_PER_ROW = 512


def fits_tile_bytes(region: Region) -> int:
    """Estimate the working memory for one decoded window and its validity."""
    return region.height * (region.width * _TILE_BYTES_PER_PIXEL + _TILE_BYTES_PER_ROW)


class FitsTileSource:
    def __init__(
        self,
        hdu: fits.PrimaryHDU,
        descriptor: PanelDescriptor,
        max_tile_bytes: int,
        coverage: fits.ImageHDU | None = None,
        sky_mask: FitsTileSource | None = None,
    ) -> None:
        self._hdu = hdu
        self.descriptor = descriptor
        self._max_tile_bytes = max_tile_bytes
        self._coverage = coverage
        self._sky_mask = sky_mask

    @property
    def sky_mask_fingerprint(self) -> SourceFingerprint | None:
        return self._sky_mask.descriptor.fingerprint if self._sky_mask is not None else None

    @property
    def header(self) -> fits.Header:
        return self._hdu.header.copy()

    @staticmethod
    def tile_bytes(region: Region) -> int:
        return fits_tile_bytes(region)

    def read_binary_mask(self, region: Region) -> NDArray[np.bool_]:
        return _binary_pixels(self._hdu.section[region.slices], "sky mask")

    def read_tile(self, region: Region, *, halo: int = 0) -> Tile:
        """Read an in-bounds region with a halo clipped to the image edges."""
        panel = self.descriptor
        actual = region.with_halo(panel.width, panel.height, halo)
        if fits_tile_bytes(actual) > self._max_tile_bytes:
            raise ValueError("The FITS tile exceeds the configured byte budget.")

        raw = self._hdu.section[actual.slices]
        valid = np.isfinite(raw)
        if panel.blank is not None:
            valid &= raw != panel.blank
        if self._coverage is not None:
            valid &= _binary_pixels(self._coverage.section[actual.slices], "COVERAGE image")
        if self._sky_mask is not None:
            valid &= self._sky_mask.read_binary_mask(actual)
        with np.errstate(over="ignore", invalid="ignore"):
            if panel.bscale != 1.0 or panel.bzero != 0.0:
                scaled = np.multiply(raw, panel.bscale, dtype=np.float64)
                scaled += panel.bzero
                pixels = scaled.astype(np.float32)
            else:
                pixels = np.array(raw, dtype=np.float32, copy=True)
        if np.any(valid & ~np.isfinite(pixels)):
            raise ValueError(
                "A valid FITS sample exceeds the supported float32 range after scaling."
            )
        pixels[~valid] = np.nan
        return Tile(actual, pixels, valid)


def _binary_pixels(values: NDArray[np.uint8], label: str) -> NDArray[np.bool_]:
    if np.any(values > 1):
        raise ValueError(f"Expected binary values in the FITS {label}.")
    return cast(NDArray[np.bool_], values == 1)


def optional_header_text(header: fits.Header, keyword: str) -> str | None:
    value = header.get(keyword)
    return value.strip() or None if isinstance(value, str) else None


def _coverage_hdu(hdus: fits.HDUList, shape: tuple[int, int], size: int) -> fits.ImageHDU | None:
    composition = hdus[0].header.get("LAYERS") is True
    names = ("COVERAGE", "LAYERS") if composition else ("COVERAGE",)
    extensions = hdus[1 : len(names) + 2]
    if not extensions and not composition:
        return None
    if len(extensions) != len(names):
        raise ValueError("Expected the FITS COVERAGE and any declared LAYERS image.")
    for image, name in zip(extensions, names, strict=True):
        if not isinstance(image, fits.ImageHDU) or image.name != name:
            raise ValueError(f"Unexpected FITS extensions. Expected the {name} image.")
        _check_byte_extension(image, shape, size)
    return cast(fits.ImageHDU, extensions[0])


def _check_byte_extension(image: fits.ImageHDU, shape: tuple[int, int], size: int) -> None:
    header = image.header
    height, width = shape
    if (
        image.shape != shape
        or header["BITPIX"] != 8
        or header.get("BSCALE", 1) != 1
        or header.get("BZERO", 0) != 0
        or "BLANK" in header
    ):
        raise ValueError(
            f"Expected an unscaled byte {image.name} image matching the primary shape."
        )
    if image.fileinfo()["datLoc"] + height * width > size:
        raise ValueError(f"The FITS {image.name} image is truncated.")


@contextmanager
def open_fits_panel(
    path: Path,
    *,
    max_tile_bytes: int = _DEFAULT_TILE_BUDGET,
    memmap: bool = True,
    sky_mask: Path | None = None,
) -> Iterator[FitsTileSource]:
    """Open a local input read-only and release its handle when the caller leaves the context."""
    if max_tile_bytes < 1:
        raise ValueError("The FITS tile byte budget must be positive.")

    with path.open("rb") as stream, ExitStack() as masks:
        if stream.read(9) != b"SIMPLE  =":
            raise ValueError("Expected an uncompressed FITS file with a standard primary header.")
        stream.seek(0)
        stat = os.fstat(stream.fileno())

        with fits.open(
            stream, mode="readonly", memmap=memmap, do_not_scale_image_data=True
        ) as hdus:
            hdu = hdus[0]
            if not isinstance(hdu, fits.PrimaryHDU) or len(hdu.shape) != 2 or min(hdu.shape) < 1:
                raise ValueError("Expected a two-dimensional monochrome image in the primary HDU.")

            header = hdu.header
            try:
                bscale = float(header.get("BSCALE", 1.0))
                bzero = float(header.get("BZERO", 0.0))
            except (TypeError, ValueError, OverflowError) as error:
                raise ValueError("Invalid FITS BSCALE or BZERO.") from error
            if not (isfinite(bscale) and bscale != 0.0 and isfinite(bzero)):
                raise ValueError("Invalid FITS BSCALE or BZERO.")

            bitpix = header["BITPIX"]
            if bitpix == 64 and (bscale != 1.0 or bzero != 0.0):
                raise ValueError("Scaled 64-bit FITS integers are unsupported.")
            blank = header.get("BLANK") if bitpix > 0 else None
            if blank is not None and not isinstance(blank, int):
                raise ValueError("Expected an integer FITS BLANK value.")
            height, width = hdu.shape
            data_end = hdu.fileinfo()["datLoc"] + width * height * (abs(bitpix) // 8)
            if data_end > stat.st_size:
                raise ValueError("The primary FITS image is truncated.")
            coverage = _coverage_hdu(hdus, (height, width), stat.st_size)

            mask_provenance: tuple[str, ...] = ("finite-raw-pixels",)
            if blank is not None:
                mask_provenance += ("primary-header-blank",)
            if coverage is not None:
                mask_provenance += ("coverage-extension",)
            mask = None
            if sky_mask is not None:
                mask = masks.enter_context(
                    open_fits_sky_mask(sky_mask, width, height, memmap=memmap)
                )
                mask_provenance += ("supplied-sky-mask",)
            descriptor = PanelDescriptor(
                fingerprint=SourceFingerprint(stat.st_size, stat.st_mtime_ns),
                width=width,
                height=height,
                channel_layout="mono",
                filter_name=optional_header_text(header, "FILTER"),
                unit=optional_header_text(header, "BUNIT"),
                bitpix=bitpix,
                bscale=bscale,
                bzero=bzero,
                wcs_provenance="primary-header"
                if optional_header_text(header, "CTYPE1") and optional_header_text(header, "CTYPE2")
                else None,
                blank=blank,
                mask_provenance=mask_provenance,
            )
            yield FitsTileSource(hdu, descriptor, max_tile_bytes, coverage, mask)


@contextmanager
def open_fits_sky_mask(
    path: Path, width: int, height: int, *, memmap: bool = False
) -> Iterator[FitsTileSource]:
    with open_fits_panel(path, memmap=memmap) as mask:
        descriptor = mask.descriptor
        if (
            (descriptor.width, descriptor.height) != (width, height)
            or (descriptor.bitpix, descriptor.bscale, descriptor.bzero) != (8, 1, 0)
            or descriptor.mask_provenance != ("finite-raw-pixels",)
        ):
            raise ValueError("Expected a single unscaled byte sky mask matching the panel shape.")
        yield mask
