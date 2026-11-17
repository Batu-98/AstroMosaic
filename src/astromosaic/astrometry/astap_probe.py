"""Use the ASTAP CLI with local catalogs and disposable FITS copies."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from math import isclose, isfinite
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from astromosaic.core.job import DEFAULT_JOB_CONTEXT, JobContext

ASTAP_DATABASES = ("d05", "d20", "d50", "d80")
_TILE_HEADER_BYTES = 110
_D_SERIES_RECORD_BYTES = 5


def _read_solution_header(workdir: Path) -> fits.Header:
    status_file = workdir / "result.ini"
    if not status_file.is_file():
        raise ValueError("ASTAP did not write a status file.")
    status = dict(
        line.split("=", 1) for line in status_file.read_text("ascii").splitlines() if "=" in line
    )
    if status.get("PLTSOLVD") != "T":
        raise ValueError("ASTAP did not report a solved field.")

    wcs_file = workdir / "result.wcs"
    if not wcs_file.is_file():
        raise ValueError("ASTAP reported success without a WCS sidecar.")
    full_header = fits.Header.fromstring(wcs_file.read_bytes().decode("ascii"))
    # The sidecar can retain legacy source plate geometry, such as the DSS plate model.
    numeric = ("CRPIX1", "CRPIX2", "CRVAL1", "CRVAL2", "CD1_1", "CD1_2", "CD2_1", "CD2_2")
    axes = ("CTYPE1", "CTYPE2", "CUNIT1", "CUNIT2", "RADESYS", "EQUINOX")
    header = fits.Header()
    for card in full_header.cards:
        if card.keyword in (*numeric, *axes) or re.fullmatch(
            r"[AB]P?_(ORDER|\d+_\d+)", card.keyword
        ):
            header[card.keyword] = card.value
    if any(
        keyword not in header
        or keyword not in status
        or not isclose(float(header[keyword]), float(status[keyword]), rel_tol=1e-10, abs_tol=1e-12)
        for keyword in numeric
    ):
        raise ValueError("ASTAP's status and WCS files disagree about the solved geometry.")
    wcs = WCS(header).celestial
    if not wcs.has_celestial:
        raise ValueError("ASTAP returned a solution without celestial axes.")
    longitude, latitude = wcs.wcs.crval
    x_fits, y_fits = wcs.wcs.crpix
    matrix = wcs.pixel_scale_matrix
    determinant = float(np.linalg.det(matrix))
    if (
        not all(map(isfinite, (longitude, latitude, x_fits, y_fits, determinant)))
        or determinant == 0
    ):
        raise ValueError("ASTAP returned a nonfinite or singular WCS geometry.")
    return header


def _read_solution(workdir: Path) -> dict[str, float]:
    return _summarize_header(_read_solution_header(workdir))


def _summarize_header(header: fits.Header) -> dict[str, float]:
    wcs = WCS(header).celestial
    longitude, latitude = wcs.wcs.crval
    x_fits, y_fits = wcs.wcs.crpix
    return {
        "ra_deg": float(longitude) % 360.0,
        "dec_deg": float(latitude),
        "reference_x_fits": float(x_fits),
        "reference_y_fits": float(y_fits),
    }


def solve_d05(
    executable: Path,
    catalog: Path,
    image: Path,
    *,
    ra_deg: float,
    dec_deg: float,
    field_height_deg: float,
    timeout_seconds: float = 30.0,
) -> dict[str, float]:
    """Run one one-threaded, hinted solve and read its WCS from scratch storage."""
    header, _ = solve_astap(
        executable,
        catalog,
        image,
        position=(ra_deg, dec_deg),
        field_height_deg=field_height_deg,
        timeout_seconds=timeout_seconds,
    )
    return _summarize_header(header)


def _astap_catalog_tile(executable: Path, catalog: Path, database: str) -> Path:
    if not executable.is_file():
        raise ValueError("The ASTAP executable is missing. Choose the local ASTAP CLI executable.")
    if database not in ASTAP_DATABASES:
        raise ValueError("Expected an ASTAP D05, D20, D50, or D80 database name.")
    if not catalog.is_dir():
        raise ValueError("The ASTAP catalog folder is missing. Choose its current location.")
    for tile in catalog.glob(f"{database}_*.1476"):
        if tile.is_file():
            return tile
    raise ValueError(
        f"No ASTAP {database.upper()} catalog tiles found. "
        "Choose the folder containing the tiles or select the database installed there."
    )


def check_astap_setup(
    executable: Path, catalog: Path, database: str, context: JobContext = DEFAULT_JOB_CONTEXT
) -> str:
    """Check the selected CLI and the format of one catalog tile without an image."""
    context.check_cancelled()
    tile = _astap_catalog_tile(executable, catalog, database)
    with tile.open("rb") as stream:
        header = stream.read(_TILE_HEADER_BYTES)
        first_record = stream.read(_D_SERIES_RECORD_BYTES)
    if (
        len(header) != _TILE_HEADER_BYTES
        or header[-1] != _D_SERIES_RECORD_BYTES
        or len(first_record) != _D_SERIES_RECORD_BYTES
        or not first_record.startswith(b"\xff\xff\xff")
        or (tile.stat().st_size - _TILE_HEADER_BYTES) % _D_SERIES_RECORD_BYTES
    ):
        raise ValueError(
            f"The sampled {database.upper()} tile ({tile.name}) has an invalid .1476 layout. "
            "Choose an unpacked ASTAP catalog."
        )
    with TemporaryDirectory(prefix="astromosaic-astap-check-") as directory:
        output = _run_astap([str(executable.resolve()), "-h"], Path(directory), 8, context)
    match = re.search(r"^ASTAP astrometric solver version ([\w.-]+)", output, re.I | re.M)
    if match is None:
        raise ValueError(
            "The selected program did not report an ASTAP solver version. Select the ASTAP CLI."
        )
    return match[1]


def solve_astap(
    executable: Path,
    catalog: Path,
    image: Path | Callable[[Path], None],
    *,
    position: tuple[float, float] | None = None,
    field_height_deg: float = 0,
    timeout_seconds: float = 60,
    database: str = "d05",
    context: JobContext = DEFAULT_JOB_CONTEXT,
) -> tuple[fits.Header, str | None]:
    """Run a hinted or blind ASTAP attempt with an explicit local database."""
    context.check_cancelled()
    _astap_catalog_tile(executable, catalog, database)
    if not 0 <= field_height_deg <= 180:
        raise ValueError("Expected an ASTAP field height between 0 and 180 degrees.")
    if not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("The solver timeout must be positive and finite.")

    with TemporaryDirectory(prefix="astromosaic-astap-") as directory:
        scratch = Path(directory)
        staged = scratch / "input.fits"
        if isinstance(image, Path):
            shutil.copyfile(image, staged)
        else:
            image(staged)
        # Use an ASCII scratch name to give ASTAP a portable path to the copied input.
        command = [
            str(executable.resolve()),
            "-f",
            "input.fits",
            "-d",
            str(catalog.resolve()),
            "-D",
            database,
            "-fov",
            str(field_height_deg),
            "-r",
            "3" if position is not None else "180",
            "-z",
            "0",
            "-threads",
            "1",
            "-o",
            "result",
            "-wcs",
        ]
        if position is not None:
            ra_deg, dec_deg = position
            if not (0 <= ra_deg < 360 and -90 <= dec_deg <= 90):
                raise ValueError("Expected valid ASTAP sky coordinates in degrees.")
            command.extend(("-ra", str(ra_deg / 15), "-spd", str(dec_deg + 90)))
        output = _run_astap(command, scratch, timeout_seconds, context)
        context.check_cancelled()
        version = re.search(r"solver version ([A-Za-z0-9.-]+)", output, flags=re.IGNORECASE)
        return _read_solution_header(scratch), version[1] if version else None


def _run_astap(
    command: list[str], scratch: Path, timeout_seconds: float, context: JobContext
) -> str:
    context.check_cancelled()
    with subprocess.Popen(
        command,
        cwd=scratch,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    ) as process:
        try:
            output = _wait_for_astap(process, timeout_seconds, context)
        except BaseException:
            process.kill()
            process.communicate()
            raise
        if process.returncode:
            detail = output.strip().splitlines()[-1] if output.strip() else "No solver details."
            raise ValueError(f"ASTAP exited with code {process.returncode}. {detail}")
        return output


def _wait_for_astap(
    process: subprocess.Popen[str], timeout_seconds: float, context: JobContext
) -> str:
    if context.is_cancelled is None:
        return process.communicate(timeout=timeout_seconds)[0]
    deadline = monotonic() + timeout_seconds
    while True:
        context.check_cancelled()
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, timeout_seconds)
        try:
            return process.communicate(timeout=min(remaining, 0.2))[0]
        except subprocess.TimeoutExpired:
            continue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("image", type=Path)
    parser.add_argument(
        "--ra", required=True, type=float, help="Approximate right ascension in degrees."
    )
    parser.add_argument(
        "--dec", required=True, type=float, help="Approximate declination in degrees."
    )
    parser.add_argument(
        "--height", required=True, type=float, help="Image field height in degrees."
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="Solver deadline in seconds.")
    args = parser.parse_args(argv)

    try:
        result = solve_d05(
            args.executable,
            args.catalog,
            args.image,
            ra_deg=args.ra,
            dec_deg=args.dec,
            field_height_deg=args.height,
            timeout_seconds=args.timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"astap-probe: solver timed out after {args.timeout:g}s.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("astap-probe: cancelled.", file=sys.stderr)
        return 130
    except (OSError, ValueError) as error:
        print(f"astap-probe: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
