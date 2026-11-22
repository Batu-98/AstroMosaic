"""Saved settings for the sky photo workflow."""

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path
from string import hexdigits
from typing import Literal

from astromosaic.io.icc import MAX_ICC_BYTES, is_matrix_profile, is_srgb_profile

type ProfileMode = Literal[
    "auto", "assume-srgb", "srgb", "linear-srgb", "display-p3", "adobe-rgb", "icc"
]
type ExposureMode = Literal["off", "manual", "metadata"]
type BrightnessMode = Literal["off", "sky-offset", "standard"]

PROFILE_LABELS: dict[ProfileMode, str] = {
    "auto": "Auto (embedded or EXIF)",
    "assume-srgb": "Assume sRGB when untagged",
    "srgb": "Assign sRGB",
    "linear-srgb": "Assign linear sRGB",
    "display-p3": "Assign Display P3",
    "adobe-rgb": "Assign Adobe RGB",
    "icc": "Assign ICC file",
}
EXPOSURE_LABELS: dict[ExposureMode, str] = {
    "off": "Off",
    "manual": "Manual EV",
    "metadata": "Exposure metadata",
}
BRIGHTNESS_LABELS: dict[BrightnessMode, str] = {
    "off": "Off",
    "sky-offset": "Sky Offset",
    "standard": "Standard",
}


def _read_icc(path: Path) -> bytes:
    try:
        with path.open("rb") as stream:
            profile = stream.read(MAX_ICC_BYTES + 1)
    except OSError as error:
        raise ValueError(
            f"Cannot read ICC file {path.name}: {error.strerror or 'I/O error'}."
        ) from error
    if len(profile) > MAX_ICC_BYTES:
        raise ValueError("The ICC file exceeds the 1 MiB profile limit.")
    return profile


@dataclass(frozen=True, slots=True)
class PhotoProfile:
    mode: ProfileMode = "auto"
    path: Path | None = None
    digest: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in PROFILE_LABELS:
            raise ValueError("Unknown photo profile mode.")
        if self.mode == "icc":
            if (
                self.path is None
                or self.digest is None
                or len(self.digest) != 64
                or any(digit not in hexdigits for digit in self.digest)
            ):
                raise ValueError("An assigned ICC file needs a path and a SHA-256 fingerprint.")
        elif self.path is not None or self.digest is not None:
            raise ValueError("Only the ICC file assignment accepts a profile path.")

    @classmethod
    def capture(cls, path: Path) -> "PhotoProfile":
        path = path.absolute()
        profile = _read_icc(path)
        if not (is_srgb_profile(profile) or is_matrix_profile(profile)):
            raise ValueError("Choose a supported RGB matrix ICC v2 or v4 profile.")
        return cls("icc", path, sha256(profile).hexdigest())

    def read(self) -> bytes:
        if self.path is None:
            raise ValueError("Choose an ICC file.")
        profile = _read_icc(self.path)
        if sha256(profile).hexdigest() != self.digest:
            raise ValueError("The assigned ICC file changed. Reassign the profile.")
        return profile


def validate_photo_ev(ev: float) -> None:
    if isinstance(ev, bool) or not isfinite(ev) or not -16 <= ev <= 16:
        raise ValueError("Enter a finite photo exposure between -16 and +16 EV.")


@dataclass(frozen=True, slots=True)
class PhotoSettings:
    profile: PhotoProfile = PhotoProfile()
    exposure: ExposureMode = "off"
    brightness: BrightnessMode = "off"

    def __post_init__(self) -> None:
        if self.exposure not in EXPOSURE_LABELS or self.brightness not in BRIGHTNESS_LABELS:
            raise ValueError("Unknown photo exposure or brightness method.")
