"""Translate standard TIFF EXIF/XMP optical hints without changing the file.

FocalPlaneResolutionUnit 2/3 means inches/centimeters in the CIPA Exif/XMP
mapping. Ordinary TIFF print resolution and 35 mm equivalent focal length
are deliberately excluded. These values remain approximate solver hints.
"""

from math import isfinite
from typing import cast
from xml.etree import ElementTree

from astropy.io import fits
from tifffile import TiffPage

_XMP_LIMIT = 128 * 1024
_EXIF_NAMESPACE = "http://ns.adobe.com/exif/1.0/"
_TIFF_NAMESPACE = "http://ns.adobe.com/tiff/1.0/"
_KEYS = {
    "FocalLength",
    "FocalPlaneXResolution",
    "FocalPlaneYResolution",
    "FocalPlaneResolutionUnit",
    "PixelXDimension",
    "PixelYDimension",
    "DigitalZoomRatio",
}


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
        root = ElementTree.fromstring(value)
    except ElementTree.ParseError:
        return {}
    fields: dict[str, object] = {}
    allowed = {f"{{{_EXIF_NAMESPACE}}}{key}": key for key in _KEYS}
    allowed[f"{{{_TIFF_NAMESPACE}}}Model"] = "Model"
    for element in root.iter():
        if element.tag in allowed and element.text is not None:
            fields[allowed[element.tag]] = element.text.strip()
        for key, text in element.attrib.items():
            if key in allowed:
                fields[allowed[key]] = text.strip()
    return fields


def add_tiff_optical_metadata(page: TiffPage, header: fits.Header) -> fits.Header:
    """Fill absent FITS-style hints from EXIF, then standard XMP fallback.

    Embedded AstroMosaic fields keep precedence. Pixel pitch is nominal when
    no reference dimensions exist; reject an explicit dimension mismatch or
    digital zoom rather than guessing a crop/resampling factor.
    """
    result = header.copy()
    exif_value = page.tags.valueof("ExifTag", {})
    exif = cast(dict[str, object], exif_value) if isinstance(exif_value, dict) else {}
    xmp = _xmp_fields(page)

    def number(key: str) -> tuple[float | None, str]:
        if key in exif:
            return _positive_rational(exif[key], allow_zero=key == "DigitalZoomRatio"), "EXIF"
        return _positive_rational(xmp.get(key), allow_zero=key == "DigitalZoomRatio"), "XMP"

    focal, source = number("FocalLength")
    if "FOCALLEN" not in result and focal is not None:
        result["FOCALLEN"] = (focal, f"{source} FocalLength [mm]; solver hint")
    xref, _ = number("PixelXDimension")
    yref, _ = number("PixelYDimension")
    zoom, _ = number("DigitalZoomRatio")
    dimensions_match = (
        ("PixelXDimension" not in exif and "PixelXDimension" not in xmp) or xref == page.imagewidth
    ) and (
        ("PixelYDimension" not in exif and "PixelYDimension" not in xmp) or yref == page.imagelength
    )
    zoom_valid = ("DigitalZoomRatio" not in exif and "DigitalZoomRatio" not in xmp) or (
        zoom is not None and zoom <= 1
    )
    unit, _ = number("FocalPlaneResolutionUnit")
    unit_um = {2.0: 25_400.0, 3.0: 10_000.0}.get(unit) if unit is not None else None
    if dimensions_match and zoom_valid and unit_um is not None:
        for key, target in (
            ("FocalPlaneXResolution", "XPIXSZ"),
            ("FocalPlaneYResolution", "YPIXSZ"),
        ):
            resolution, source = number(key)
            if target not in result and resolution is not None:
                pitch = unit_um / resolution
                if isfinite(pitch) and pitch > 0:
                    result[target] = (
                        pitch,
                        f"{source} nominal pixel pitch [um]; verify resampling",
                    )
    model = page.tags.valueof("Model", xmp.get("Model"))
    if (
        "INSTRUME" not in result
        and isinstance(model, str)
        and model.strip()
        and model.isascii()
        and model.isprintable()
    ):
        result["INSTRUME"] = (model.strip()[:68], "TIFF/EXIF camera model")
    return result
