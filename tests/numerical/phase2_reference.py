"""Generated sky, source errors, and ground mask for the Phase 2 reference."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray

SIZE = (360, 144)
WIDTH = 176
X0 = (0, 86, 184)
CENTER = (359.999, 24.0)
ARCSEC = 2.0
SHIFTS = ((0.0, 0.0), (1.45, -0.85), (-1.20, 0.70))
GAINS = (1.0, 1.18, 0.87)
PLANES = ((0.0, 0.0, 0.0), (1.2, 0.90, -0.65), (-0.65, -0.45, 0.72))
STAR_CENTER = (331.3, 45.6)
EMISSION_CENTER = (144.0, 94.0)


@dataclass(frozen=True, slots=True)
class Reference:
    paths: tuple[Path, ...]
    mask: Path
    truth: NDArray[np.float64]
    emission: NDArray[np.float64]


def write_panels(directory: Path, *, injected: bool = True, planes: bool = True) -> Reference:
    rng = np.random.default_rng(23772)
    image_y, image_x = np.indices((SIZE[1], SIZE[0]), dtype=np.float64)
    image = 5 + 0.003 * (image_x - 170) - 0.004 * (image_y - 70)
    for y in range(20, 130, 21):
        for x in range(20, SIZE[0] - 24, 21):
            sx, sy = x + rng.uniform(-2, 2), y + rng.uniform(-2, 2)
            if np.hypot(sx - STAR_CENTER[0], sy - STAR_CENTER[1]) < 22:
                continue
            image += rng.uniform(32, 105) * np.exp(
                -((image_x - sx) ** 2 + (image_y - sy) ** 2) / (2 * 1.55**2)
            )
    sx, sy = STAR_CENTER
    image += 65 * np.exp(-((image_x - sx) ** 2 + (image_y - sy) ** 2) / (2 * 1.65**2))
    ex, ey = EMISSION_CENTER
    emission = 0.65 * np.exp(-0.5 * (((image_x - ex) / 19) ** 2 + ((image_y - ey) / 14) ** 2))
    truth = image + emission if injected else image

    paths = []
    mask_path = directory / "sky-mask.fits"
    for index, x0 in enumerate(X0):
        dx, dy = SHIFTS[index]
        offset, gx, gy = PLANES[index]
        normalized_x = 2 * np.arange(WIDTH) / (WIDTH - 1) - 1
        normalized_y = 2 * np.arange(SIZE[1]).reshape(-1, 1) / (SIZE[1] - 1) - 1
        correction = offset + gx * normalized_x + gy * normalized_y if planes else offset
        noise = rng.normal(0, 0.035, (SIZE[1], WIDTH))
        pixels = (truth[:, x0 : x0 + WIDTH] - correction) / GAINS[index] + noise
        if index == 1:
            mask = image_y[:, :WIDTH] < 108 + 2 * np.cos(image_x[:, :WIDTH] / 9)
            pixels[~mask] = (500 + 200 * np.sin(0.24 * image_x[:, :WIDTH]))[~mask]
            fits.writeto(mask_path, mask.astype(np.uint8))
        header = fits.Header(
            {
                "CTYPE1": "RA---TAN",
                "CTYPE2": "DEC--TAN",
                "RADESYS": "ICRS",
                "CRVAL1": CENTER[0],
                "CRVAL2": CENTER[1],
                "CRPIX1": (SIZE[0] + 1) / 2 - x0 - dx,
                "CRPIX2": (SIZE[1] + 1) / 2 - dy,
                "CDELT1": -ARCSEC / 3600,
                "CDELT2": ARCSEC / 3600,
                "BUNIT": "MJy/sr",
                "FILTER": "L",
                "SATURATE": 220.0,
            }
        )
        path = directory / f"reference-{index + 1}.fits"
        fits.writeto(path, pixels.astype(np.float32), header=header)
        paths.append(path)
    return Reference(tuple(paths), mask_path, truth, emission)
