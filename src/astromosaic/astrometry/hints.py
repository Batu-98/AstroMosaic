"""Optical metadata used to estimate the image scale for plate solving."""

import re
from dataclasses import dataclass
from math import isfinite

from astropy.io.fits import Header


@dataclass(frozen=True, slots=True)
class PanelOptics:
    focal_length_mm: float | None = None
    pixel_size_x_um: float | None = None
    pixel_size_y_um: float | None = None

    def __post_init__(self) -> None:
        for value in (self.focal_length_mm, self.pixel_size_x_um, self.pixel_size_y_um):
            if value is not None and positive_number(value) is None:
                raise ValueError("Enter positive finite values for focal length and pixel size.")

    def with_overrides(self, overrides: "PanelOptics") -> "PanelOptics":
        return PanelOptics(
            overrides.focal_length_mm or self.focal_length_mm,
            overrides.pixel_size_x_um or self.pixel_size_x_um,
            overrides.pixel_size_y_um or self.pixel_size_y_um,
        )

    def scales_arcsec(self) -> tuple[float | None, float | None]:
        focal = self.focal_length_mm
        if focal is None:
            return None, None

        def scale(pitch: float | None) -> float | None:
            return positive_number(206.264806 * (pitch / focal)) if pitch is not None else None

        return scale(self.pixel_size_x_um), scale(self.pixel_size_y_um)


def positive_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        result = float(value)
    except OverflowError:
        return None
    return result if isfinite(result) and result > 0 else None


def _effective_pitch(header: Header, key: str, binning_key: str) -> float | None:
    pitch = positive_number(header.get(key))
    if pitch is None or binning_key not in header:
        return pitch
    binning = positive_number(header[binning_key])
    if binning is None or not binning.is_integer() or binning < 1:
        return None
    if binning == 1:
        return pitch
    comment = str(header.comments[key]).lower()
    native = re.search(r"\b(?:unbinned|native|before binning)\b", comment)
    effective = re.search(r"\b(?:binned|effective|after binning)\b", comment)
    if native and not effective:
        return positive_number(pitch * binning)
    if effective and not native:
        return pitch
    return None


def read_optics(header: Header) -> PanelOptics:
    """Read FITS-style hints with the documented mm and micrometer conventions."""
    return PanelOptics(
        positive_number(header.get("FOCALLEN")),
        _effective_pitch(header, "XPIXSZ", "XBINNING"),
        _effective_pitch(header, "YPIXSZ", "YBINNING"),
    )
