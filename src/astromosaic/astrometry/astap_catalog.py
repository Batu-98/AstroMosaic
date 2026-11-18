"""Read bounded cones from installed Gaia DR3 ASTAP D-series catalogs.

The documented HNSKY 1476/5 format stores little-endian 24-bit RA and
sectioned 24-bit declination, with 0.1-magnitude section markers. This is an
original read-only decoder, not a copy of the native solver implementation.
The format and provenance are recorded in docs/phase-36a.md.
"""

import re
from dataclasses import dataclass
from math import asin, cos, degrees, isfinite, radians, sin
from pathlib import Path

from astromosaic.core.job import DEFAULT_JOB_CONTEXT, JobContext

_HEADER_BYTES = 110
_RECORD_BYTES = 5
_BLOCK_RECORDS = 4096
_DATABASE_DENSITIES = {"d05": 500, "d20": 2000, "d50": 5000, "d80": 8000}
# Fixed sky partition in the 1476 format, from south pole to equator, then mirrored.
_SOUTH_COUNTS = (1, 3, 9, 15, 21, 27, 33, 38, 43, 48, 52, 56, 60, 63, 65, 67, 68, 69)
_COUNTS = _SOUTH_COUNTS + _SOUTH_COUNTS[::-1]
_DECLINATION_EDGES = (-90.0, *(180 * (index - 0.5) / 35 - 90 for index in range(1, 36)), 90.0)
ASTAP_DATABASES = tuple(_DATABASE_DENSITIES)
TILE_SUFFIXES = tuple(
    f"{band:02d}{cell:02d}.1476"
    for band, count in enumerate(_COUNTS, 1)
    for cell in range(1, count + 1)
)


@dataclass(frozen=True, slots=True)
class CatalogStar:
    identifier: str
    ra_deg: float
    dec_deg: float
    magnitude: float


@dataclass(frozen=True, slots=True)
class CatalogCone:
    stars: tuple[CatalogStar, ...]
    epoch_year: float
    tiles: tuple[str, ...]
    read_bytes: int


def _cone_tiles(center: tuple[float, float], radius_deg: float) -> tuple[str, ...]:
    ra, dec = center
    south, north = max(-90, dec - radius_deg), min(90, dec + radius_deg)
    intervals: tuple[tuple[float, float], ...]
    if south == -90 or north == 90:
        intervals = ((0.0, 360.0),)
    else:
        half_ra = degrees(asin(min(1.0, sin(radians(radius_deg)) / cos(radians(dec)))))
        left, right = ra - half_ra, ra + half_ra
        if left < 0:
            intervals = ((0.0, right), (left + 360, 360.0))
        elif right >= 360:
            intervals = ((left, 360.0), (0.0, right - 360))
        else:
            intervals = ((left, right),)
    selected: list[str] = []
    for band, count in enumerate(_COUNTS, 1):
        if _DECLINATION_EDGES[band] < south or _DECLINATION_EDGES[band - 1] > north:
            continue
        for cell in range(count):
            left, right = 360 * cell / count, 360 * (cell + 1) / count
            if any(right >= lo and left <= hi for lo, hi in intervals):
                selected.append(f"{band:02d}{cell + 1:02d}.1476")
    return tuple(selected)


def query_astap_cone(
    directory: Path,
    database: str,
    center: tuple[float, float],
    radius_deg: float,
    *,
    max_stars: int = 20_000,
    max_read_bytes: int = 64 * 1024**2,
    context: JobContext = DEFAULT_JOB_CONTEXT,
) -> CatalogCone:
    """Read actual catalog positions, refusing missing tiles and truncated results.

    This query supports local validation cones of at most ten degrees, not a
    whole-sky search. The retained-star and I/O bounds are explicit; record
    decoding uses one 20 KiB block at a time. No proper-motion data are present,
    so the returned epoch must travel with any validation metrics.
    """
    ra, dec = center
    if not (isfinite(ra) and 0 <= ra < 360 and isfinite(dec) and -90 <= dec <= 90):
        raise ValueError("Expected a finite ICRS cone center in degrees.")
    if not isfinite(radius_deg) or not 0 < radius_deg <= 10:
        raise ValueError(
            "Expected a catalog validation radius greater than zero and at most 10 degrees."
        )
    if max_stars <= 0 or max_read_bytes <= 0:
        raise ValueError("Catalog star and read budgets must be positive.")
    if database not in _DATABASE_DENSITIES:
        raise ValueError("Expected an ASTAP D05, D20, D50, or D80 catalog.")
    paths = tuple(directory / f"{database}_{tile}" for tile in _cone_tiles(center, radius_deg))
    context.check_cancelled()
    for path in paths:
        if not path.is_file():
            raise ValueError(
                f"Missing ASTAP catalog tile required by the validation field: {path.name}"
            )
    stars: list[CatalogStar] = []
    read_bytes = 0
    epoch: float | None = None
    center_dec = radians(dec)
    cone_limit = sin(radians(radius_deg) / 2) ** 2
    for path in paths:
        context.check_cancelled()
        stamp_before = path.stat()
        length = stamp_before.st_size
        if length < _HEADER_BYTES or (length - _HEADER_BYTES) % _RECORD_BYTES:
            raise ValueError(f"Invalid ASTAP tile length: {path.name}")
        if read_bytes + length > max_read_bytes:
            raise ValueError("The ASTAP catalog query exceeds its read byte budget.")
        with path.open("rb") as stream:
            header = stream.read(_HEADER_BYTES)
            if len(header) != _HEADER_BYTES:
                raise ValueError(f"Truncated ASTAP tile header: {path.name}")
            description = header[:109].decode("ascii", errors="strict")
            if not description.startswith("GAIA DR3") or header[-1] != _RECORD_BYTES:
                raise ValueError("Expected a Gaia DR3 ASTAP 1476 catalog with five-byte records.")
            density = re.search(r"density<=(\d+)", description)
            stamp = re.search(r"Epoch=(\d+(?:\.\d+)?)", description)
            if density is None or int(density[1]) != _DATABASE_DENSITIES[database] or stamp is None:
                raise ValueError(
                    "ASTAP catalog density or epoch metadata does not match the selection."
                )
            tile_epoch = float(stamp[1])
            if epoch is not None and tile_epoch != epoch:
                raise ValueError("The ASTAP query tiles have inconsistent catalog epochs.")
            epoch = tile_epoch
            high_dec: int | None = None
            magnitude = 0.0
            offset = _HEADER_BYTES
            remaining = length - _HEADER_BYTES
            while remaining:
                context.check_cancelled()
                requested = min(remaining, _BLOCK_RECORDS * _RECORD_BYTES)
                block = stream.read(requested)
                if len(block) != requested:
                    raise ValueError(f"Truncated ASTAP tile while reading: {path.name}")
                for index in range(0, len(block), _RECORD_BYTES):
                    a, b, c, d, e = block[index : index + _RECORD_BYTES]
                    raw_ra = a + (b << 8) + (c << 16)
                    if raw_ra == 0xFFFFFF:
                        high_dec, magnitude = d - 128, (e - 16) / 10
                        continue
                    if high_dec is None:
                        raise ValueError(
                            "An ASTAP star record precedes its declination/magnitude marker."
                        )
                    star_ra = raw_ra * (360 / 0xFFFFFF)
                    star_dec = (d + (e << 8) + (high_dec << 16)) * (90 / 0x7FFFFF)
                    if not -90 <= star_dec <= 90:
                        raise ValueError("The ASTAP catalog contains an invalid declination.")
                    if abs(star_dec - dec) > radius_deg:
                        continue
                    distance = (
                        sin(radians(star_dec - dec) / 2) ** 2
                        + cos(center_dec)
                        * cos(radians(star_dec))
                        * sin(radians(star_ra - ra) / 2) ** 2
                    )
                    if distance <= cone_limit:
                        if len(stars) == max_stars:
                            raise ValueError(
                                "The ASTAP catalog query exceeds its retained star budget."
                            )
                        stars.append(
                            CatalogStar(
                                f"{path.name}:{offset + index}", star_ra, star_dec, magnitude
                            )
                        )
                offset += len(block)
                remaining -= len(block)
            stamp_after = path.stat()
            if stamp_after.st_size != length or stamp_after.st_mtime_ns != stamp_before.st_mtime_ns:
                raise ValueError(f"The ASTAP catalog tile changed during the query: {path.name}")
        read_bytes += length
    context.check_cancelled()
    assert epoch is not None
    return CatalogCone(tuple(stars), epoch, tuple(path.name for path in paths), read_bytes)
