"""Check the matrix ICC candidate against independent linear-light references."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Literal

import imagecodecs
import numpy as np
from numpy.typing import NDArray

type FloatRGB = NDArray[np.float64]
type Codes = NDArray[np.uint16]
type Primaries = tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
type ProfileName = Literal["srgb", "displayp3", "adobergb"]

_DEFAULT_SRGB = Path(__file__).resolve().parents[1] / "src/astromosaic/io/sRGB2014.icc"
_SRGB_SHA256 = "384b832de3412066743b52a75ee906b6fb9fb8d9e09e936fc2c43223815c6e0a"
_PRIMARIES: dict[ProfileName, Primaries] = {
    "srgb": ((0.64, 0.33), (0.30, 0.60), (0.15, 0.06)),
    "displayp3": ((0.68, 0.32), (0.265, 0.69), (0.15, 0.06)),
    "adobergb": ((0.64, 0.33), (0.21, 0.71), (0.15, 0.06)),
}
_WHITE = (0.3127, 0.3290)
_MAX_MATRIX_ERROR = 1.5e-4
_MAX_INPUT_PRECISION_DIFFERENCE = 2e-7
_PATCHES = {
    "black": (0, 0, 0),
    "one_code": (1, 1, 1),
    "below_toe": (2650, 2650, 2650),
    "above_toe": (2652, 2652, 2652),
    "dark_mixed": (1200, 4900, 12455),
    "mid_gray": (32768, 32768, 32768),
    "warm": (54512, 23801, 30003),
    "red": (65535, 0, 0),
    "green": (0, 65535, 0),
    "blue": (0, 0, 65535),
    "white": (65535, 65535, 65535),
}


def decode_srgb(codes: Codes) -> FloatRGB:
    encoded = codes.astype(np.float64) / 65535
    return np.where(encoded <= 0.04045, encoded / 12.92, ((encoded + 0.055) / 1.055) ** 2.4)


def _rgb_to_xyz(primaries: Primaries) -> FloatRGB:
    xy = np.array(primaries)
    xyz = np.column_stack((xy, 1 - xy.sum(axis=1))).T / xy[:, 1]
    xw, yw = _WHITE
    white = np.array([xw, yw, 1 - xw - yw]) / yw
    return np.asarray(xyz * np.linalg.solve(xyz, white), dtype=np.float64)


def _analytic(samples: Codes, profile: ProfileName) -> FloatRGB:
    values = (
        (samples.astype(np.float64) / 65535) ** (563 / 256)
        if profile == "adobergb"
        else decode_srgb(samples)
    )
    transform = np.linalg.solve(_rgb_to_xyz(_PRIMARIES["srgb"]), _rgb_to_xyz(_PRIMARIES[profile]))
    return values @ transform.T


def _transform(
    pixels: Codes | NDArray[np.float32], profile: bytes, working: bytes
) -> NDArray[np.float32]:
    return imagecodecs.cms_transform(
        pixels,
        profile,
        working,
        colorspace="rgb",
        outcolorspace="rgb",
        outdtype=np.float32,
        intent=imagecodecs.CMS.INTENT.RELATIVE_COLORIMETRIC,
        flags=imagecodecs.CMS.FLAGS.NOOPTIMIZE,
    )


def measure(srgb_path: Path = _DEFAULT_SRGB) -> dict[str, object]:
    if not imagecodecs.CMS.available:
        raise ValueError("The imagecodecs runtime lacks Little CMS.")
    srgb = srgb_path.read_bytes()
    if sha256(srgb).hexdigest() != _SRGB_SHA256:
        raise ValueError("Use the frozen sRGB2014 profile from the project.")
    working = imagecodecs.cms_profile("linearrgb")
    gray = np.repeat(np.arange(65536, dtype=np.uint16)[None, :, None], 3, axis=2)
    patches = np.array([list(_PATCHES.values())], dtype=np.uint16)
    pixels = np.concatenate((gray, patches), axis=1)
    normalized = (pixels.astype(np.float64) / 65535).astype(np.float32)

    results = {}
    for name in _PRIMARIES:
        profile = srgb if name == "srgb" else imagecodecs.cms_profile(name)
        expected = _analytic(pixels, name)
        transformed = _transform(pixels, profile, working)
        floated = _transform(normalized, profile, working)
        if transformed.dtype != np.float32 or not np.isfinite(transformed).all():
            raise ValueError(f"{name} returned an invalid linear RGB buffer.")
        ramp = np.diff(transformed[0, :65536], axis=0)
        error = float(np.abs(transformed - expected).max())
        input_difference = float(np.abs(transformed - floated).max())
        # Known sRGB uses the existing analytic transfer. Measure its sampled ICC as a control.
        qualified = (
            error <= _MAX_MATRIX_ERROR
            and input_difference <= _MAX_INPUT_PRECISION_DIFFERENCE
            and bool(np.all(ramp > 0))
            and float(transformed.min()) < 0
            and float(transformed.max()) > 1
        )
        results[name] = {
            "profile_sha256": sha256(profile).hexdigest(),
            "icc_version": imagecodecs.cms_info(profile)["version"],
            "maximum_linear_error": error,
            "uint16_vs_float32_input_maximum_error": input_difference,
            "neutral_ramp_repeated_steps": np.count_nonzero(ramp == 0, axis=0).tolist(),
            "neutral_ramp_decreasing_steps": np.count_nonzero(ramp < 0, axis=0).tolist(),
            "linear_range": [float(transformed.min()), float(transformed.max())],
            "matrix_candidate_qualified": qualified,
            "reference_patches_linear_srgb": dict(
                zip(_PATCHES, expected[0, 65536:].tolist(), strict=True)
            ),
        }
    return {
        "imagecodecs": imagecodecs.__version__,
        "color_engine": imagecodecs.cms_version(),
        "working_profile_sha256": sha256(working).hexdigest(),
        "rendering_intent": "relative_colorimetric",
        "black_point_compensation": False,
        "maximum_linear_error_limit": _MAX_MATRIX_ERROR,
        "neutral_ramp_codes": 65536,
        "input_rgb_codes": _PATCHES,
        "profiles": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--srgb-profile", type=Path, default=_DEFAULT_SRGB)
    options = parser.parse_args()
    try:
        report = measure(options.srgb_profile)
    except (OSError, ValueError, imagecodecs.CmsError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
