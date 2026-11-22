"""Resolve photo color provenance and convert source windows into linear sRGB."""

from dataclasses import dataclass, replace
from functools import lru_cache
from hashlib import sha256
from struct import pack
from typing import Literal, cast

import numpy as np
from astropy.io.fits import Header
from numpy.typing import NDArray
from scipy.ndimage import maximum_filter

from astromosaic.core import Region, Tile
from astromosaic.io import PanelSource
from astromosaic.io.icc import is_matrix_profile, is_srgb_profile
from astromosaic.photometry.photo_settings import PhotoProfile

type _CmsProfile = Literal["displayp3", "adobergb", "linearrgb"]


@lru_cache(maxsize=3)
def _generated_profile(name: _CmsProfile) -> bytes:
    from imagecodecs import CMS, cms_profile

    if not CMS.available:
        raise ValueError("Little CMS is unavailable in this runtime.")
    profile = cms_profile(name)
    # The library stamps newly generated profiles with the current time.
    return profile[:24] + pack(">6H", 2000, 1, 1, 0, 0, 0) + profile[36:]


def _matrix_transform(pixels: NDArray[np.float32], profile: bytes) -> NDArray[np.float32]:
    from imagecodecs import CMS, CmsError, cms_transform

    try:
        return cast(
            NDArray[np.float32],
            cms_transform(
                pixels,
                profile,
                _generated_profile("linearrgb"),
                colorspace="rgb",
                outcolorspace="rgb",
                outdtype=np.float32,
                intent=CMS.INTENT.RELATIVE_COLORIMETRIC,
                flags=CMS.FLAGS.NOOPTIMIZE,
            ),
        )
    except CmsError as error:
        raise ValueError(f"Little CMS could not convert the RGB matrix profile: {error}") from error


@dataclass(frozen=True, slots=True)
class PhotoColor:
    method: Literal["srgb", "linear-srgb", "matrix-icc"]
    origin: str
    profile_sha256: str | None = None
    matrix_profile: bytes | None = None
    preset: str | None = None

    def decode(self, pixels: NDArray[np.float32]) -> NDArray[np.float32]:
        if self.method == "matrix-icc":
            assert self.matrix_profile is not None
            normalized = np.ascontiguousarray(pixels)
            normalized *= np.float32(1 / 65535)
            return _matrix_transform(normalized, self.matrix_profile)
        pixels *= np.float32(1 / 65535)
        if self.method == "srgb":
            high = pixels > np.float32(0.04045)
            np.add(pixels, np.float32(0.055), out=pixels, where=high)
            np.divide(pixels, np.float32(1.055), out=pixels, where=high)
            np.power(pixels, np.float32(2.4), out=pixels, where=high)
            np.logical_not(high, out=high)
            np.divide(pixels, np.float32(12.92), out=pixels, where=high)
        return pixels


def _matrix_color(profile: bytes, origin: str) -> PhotoColor:
    if is_srgb_profile(profile):
        return PhotoColor("srgb", origin, sha256(profile).hexdigest())
    if not is_matrix_profile(profile):
        raise ValueError("has an unsupported TIFF ICC profile. Assign a supported RGB profile.")
    ramp = np.linspace(0, 1, 257, dtype=np.float32)
    patches = np.concatenate((np.repeat(ramp[:, None], 3, axis=1), np.eye(3, dtype=np.float32)))
    transformed = _matrix_transform(patches[None, ...], profile)[0]
    if not np.isfinite(transformed).all() or not np.all(
        np.diff(transformed[: ramp.size], axis=0) > 0
    ):
        raise ValueError("has an RGB matrix ICC profile with an unusable neutral response.")
    return PhotoColor("matrix-icc", origin, sha256(profile).hexdigest(), profile)


def resolve_photo_profile(
    source: PanelSource, panel: PhotoProfile | None, default: PhotoProfile
) -> PhotoColor:
    descriptor = source.descriptor
    metadata = source.photo_metadata
    if metadata is None or not metadata.uint16_rgb:
        raise ValueError("requires RGB UInt16 TIFF for photo rendering.")
    assignment = default if panel is None else panel
    mode = assignment.mode
    origin = "project_assignment" if panel is None else "panel_assignment"
    if mode == "srgb" or mode == "linear-srgb":
        return PhotoColor(mode, origin)
    if mode == "display-p3" or mode == "adobe-rgb":
        return replace(
            _matrix_color(
                _generated_profile("displayp3" if mode == "display-p3" else "adobergb"), origin
            ),
            preset=mode,
        )
    if mode == "icc":
        return _matrix_color(assignment.read(), origin)
    if metadata.color_conflict or (
        metadata.exif_srgb
        and descriptor.icc_encoding == "unsupported"
        and metadata.embedded_icc is not None
        and is_matrix_profile(metadata.embedded_icc)
    ):
        raise ValueError("has conflicting ICC and EXIF/XMP color declarations. Assign a profile.")
    if descriptor.icc_encoding == "srgb":
        return PhotoColor("srgb", "embedded", descriptor.icc_profile_sha256)
    if descriptor.icc_encoding == "unsupported":
        if metadata.embedded_icc is not None:
            return _matrix_color(metadata.embedded_icc, "embedded")
        raise ValueError("has an unsupported TIFF ICC profile. Assign a supported RGB profile.")
    if metadata.exif_srgb:
        return PhotoColor("srgb", "exif_color_space")
    if mode == "assume-srgb":
        return PhotoColor("srgb", "assumption")
    raise ValueError(
        "does not declare a supported sRGB or matrix ICC profile. Assign a photo profile."
    )


class PhotoTileSource:
    def __init__(self, source: PanelSource, color: PhotoColor, max_tile_bytes: int) -> None:
        self._source = source
        self._color = color
        self._max_tile_bytes = max_tile_bytes
        self.descriptor = source.descriptor
        self.sky_mask_fingerprint = source.sky_mask_fingerprint
        self.photo_metadata = source.photo_metadata

    @property
    def header(self) -> Header:
        return self._source.header

    def tile_bytes(self, region: Region, *, photometry: bool = False) -> int:
        pixels = region.width * region.height
        buffers = 28 if self._color.method == "matrix-icc" else 3
        cms_bytes = (
            128 * 1024 + 12 * len(self._color.matrix_profile)
            if self._color.matrix_profile is not None
            else 0
        )
        return (
            self._source.tile_bytes(region)
            + cms_bytes
            + (buffers + (8 if photometry else 0)) * pixels
        )

    def read_tile(self, region: Region, *, halo: int = 0) -> Tile:
        actual = region.with_halo(self.descriptor.width, self.descriptor.height, halo)
        return self._read(actual, photometry=False)

    def read_photometry_tile(self, region: Region) -> Tile:
        return self._read(region, photometry=True)

    def _read(self, region: Region, *, photometry: bool) -> Tile:
        if self.tile_bytes(region, photometry=photometry) > self._max_tile_bytes:
            raise ValueError("The photo source tile exceeds the configured byte budget.")
        tile = self._source.read_tile(region)
        if photometry:
            saturated = np.any(tile.pixels == 65535, axis=-1) & tile.valid
            tile.valid[:] &= ~maximum_filter(saturated, size=11)
        if self._color.method == "matrix-icc":
            np.copyto(tile.pixels, 0, where=~tile.valid[..., None])
        pixels = self._color.decode(tile.pixels)
        if self._color.method == "matrix-icc":
            if np.any(~np.isfinite(pixels) & tile.valid[..., None]):
                raise ValueError("The ICC profile produced a non-finite working sample.")
            pixels[~tile.valid] = np.nan
        return Tile(region, pixels, tile.valid)
