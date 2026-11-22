"""Translate standard TIFF EXIF/XMP optical hints without changing the file.

FocalPlaneResolutionUnit 2/3 means inches/centimeters in the CIPA Exif/XMP
mapping. Ordinary TIFF print resolution and 35 mm equivalent focal length
are deliberately excluded. These values remain approximate solver hints.
"""

from dataclasses import dataclass
from math import isclose, isfinite
from typing import cast
from xml.etree import ElementTree

from astropy.io import fits
from tifffile import TiffPage

from astromosaic.astrometry.hints import positive_header_number
from astromosaic.io.fits import optional_header_text

_XMP_LIMIT = 128 * 1024
_EXIF_NAMESPACE = "http://ns.adobe.com/exif/1.0/"
_TIFF_NAMESPACE = "http://ns.adobe.com/tiff/1.0/"
_EXIF_TAGS = {
    "ColorSpace": 40961,
    "ExposureTime": 33434,
    "FNumber": 33437,
    "ISOSpeedRatings": 34855,
    "FocalLength": 37386,
    "FocalPlaneXResolution": 41486,
    "FocalPlaneYResolution": 41487,
    "FocalPlaneResolutionUnit": 41488,
    "PixelXDimension": 40962,
    "PixelYDimension": 40963,
    "DigitalZoomRatio": 41988,
}


@dataclass(frozen=True, slots=True)
class CameraExposure:
    seconds: float | None = None
    f_number: float | None = None
    iso: float | None = None
    camera: str | None = None
    make: str | None = None
    conflicting: bool = False


@dataclass(frozen=True, slots=True)
class TiffPhotoMetadata:
    embedded_icc: bytes | None
    uint16_rgb: bool
    exif_srgb: bool
    color_conflict: bool
    exposure: CameraExposure


def _positive_rational(value: object, *, allow_zero: bool = False) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and "/" in value:
        value = tuple(value.strip().split("/"))
    try:
        if isinstance(value, tuple) and len(value) == 2:
            numerator, denominator = value
            if isinstance(numerator, bool) or isinstance(denominator, bool):
                return None
            number = float(numerator) / float(denominator)
        elif isinstance(value, int | float | str):
            number = float(value)
        else:
            return None
    except (ValueError, TypeError, ZeroDivisionError, OverflowError):
        return None
    return number if isfinite(number) and (number > 0 or (allow_zero and number == 0)) else None


def _xmp_fields(page: TiffPage) -> dict[str, object]:
    tag = page.tags.get(700)
    if tag is None or tag.count > _XMP_LIMIT:
        return {}
    value = tag.value
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if not isinstance(value, str) or len(value) > _XMP_LIMIT or "<!DOCTYPE" in value.upper():
        return {}
    try:
        root = ElementTree.fromstring(value.rstrip("\0"))
    except ElementTree.ParseError:
        return {}
    fields: dict[str, object] = {}
    allowed = {f"{{{_EXIF_NAMESPACE}}}{key}": key for key in _EXIF_TAGS}
    allowed.update({f"{{{_TIFF_NAMESPACE}}}{key}": key for key in ("Make", "Model")})
    for element in root.iter():
        if element.tag in allowed and element.text is not None:
            fields[allowed[element.tag]] = element.text.strip()
        for key, text in element.attrib.items():
            if key in allowed:
                fields[allowed[key]] = text.strip()
    return fields


def read_tiff_metadata(
    page: TiffPage, header: fits.Header, embedded_icc: bytes | None, uint16_rgb: bool
) -> tuple[fits.Header, TiffPhotoMetadata]:
    """Fill unusable FITS-style hints from EXIF, TIFF tags, and standard XMP.

    Embedded AstroMosaic fields keep precedence. Pixel pitch is nominal when
    no reference dimensions exist; reject an explicit dimension mismatch or
    digital zoom rather than guessing a crop/resampling factor.
    """
    result = header.copy()
    exif_value = page.tags.valueof("ExifTag", {})
    exif = cast(dict[str, object], exif_value) if isinstance(exif_value, dict) else {}
    direct = {
        name: tag.value
        for name, code in _EXIF_TAGS.items()
        if (tag := page.tags.get(code)) is not None
    }
    xmp = _xmp_fields(page)
    present = exif.keys() | direct.keys() | xmp.keys()

    def number(key: str, *, skip_invalid: bool = False) -> tuple[float | None, str]:
        for fields, provenance in ((exif, "EXIF"), (direct, "TIFF"), (xmp, "XMP")):
            if key in fields:
                value = _positive_rational(fields[key], allow_zero=key == "DigitalZoomRatio")
                if value is not None or not skip_invalid:
                    return value, provenance
        return None, ""

    focal, source = number("FocalLength", skip_invalid=True)
    if positive_header_number(result.get("FOCALLEN")) is None and focal is not None:
        result["FOCALLEN"] = (focal, f"{source} FocalLength [mm]; solver hint")
    xref, _ = number("PixelXDimension")
    yref, _ = number("PixelYDimension")
    zoom, _ = number("DigitalZoomRatio")
    dimensions_match = ("PixelXDimension" not in present or xref == page.imagewidth) and (
        "PixelYDimension" not in present or yref == page.imagelength
    )
    zoom_valid = "DigitalZoomRatio" not in present or (zoom is not None and zoom <= 1)
    unit, _ = number("FocalPlaneResolutionUnit")
    unit_um = {2.0: 25_400.0, 3.0: 10_000.0}.get(unit) if unit is not None else None
    if dimensions_match and zoom_valid and unit_um is not None:
        for key, target in (
            ("FocalPlaneXResolution", "XPIXSZ"),
            ("FocalPlaneYResolution", "YPIXSZ"),
        ):
            resolution, source = number(key)
            if positive_header_number(result.get(target)) is None and resolution is not None:
                pitch = unit_um / resolution
                if isfinite(pitch) and pitch > 0:
                    result[target] = (
                        pitch,
                        f"{source} nominal pixel pitch [um]; verify resampling",
                    )
    if optional_header_text(result, "INSTRUME") is None:
        for model in (page.tags.valueof("Model"), exif.get("Model"), xmp.get("Model")):
            if isinstance(model, str):
                model = model.strip()
                if model and model.isascii() and model.isprintable():
                    result["INSTRUME"] = (model[:68], "Embedded TIFF camera model")
                    break
    fields = (exif, direct, xmp)

    def numbers(*keys: str) -> list[float | None]:
        return [_positive_rational(items[key]) for items in fields for key in keys if key in items]

    def agreed(values: list[float | None]) -> tuple[float | None, bool]:
        if not values:
            return None, False
        first = values[0]
        if first is None or any(v is None or not isclose(v, first, rel_tol=1e-5) for v in values):
            return None, True
        return first, False

    def identifier(key: str) -> tuple[str | None, bool]:
        values = {
            value.strip().casefold() for value in (
                page.tags.valueof(key), exif.get(key), xmp.get(key)
            ) if isinstance(value, str) and value.strip()
        }
        return (next(iter(values)) if len(values) == 1 else None), len(values) > 1

    seconds, shutter_conflict = agreed(numbers("ExposureTime"))
    aperture, aperture_conflict = agreed(numbers("FNumber"))
    iso, iso_conflict = agreed(numbers("ISOSpeedRatings", "PhotographicSensitivity"))
    camera, camera_conflict = identifier("Model")
    make, make_conflict = identifier("Make")
    exposure = CameraExposure(
        seconds, aperture, iso, camera, make,
        shutter_conflict or aperture_conflict or iso_conflict or camera_conflict or make_conflict,
    )
    color_spaces = set(numbers("ColorSpace"))
    color_spaces.difference_update((None, 65535))
    return result, TiffPhotoMetadata(
        embedded_icc, uint16_rgb, 1 in color_spaces, len(color_spaces) > 1, exposure
    )
