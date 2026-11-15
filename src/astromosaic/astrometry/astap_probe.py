"""Test the ASTAP CLI with a local D05 catalog and a disposable copy of a FITS image."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from math import isclose, isfinite
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS


def _read_solution(workdir: Path) -> dict[str, float]:
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
    if not executable.is_file():
        raise ValueError("Provide the local ASTAP CLI executable.")
    if not any(catalog.glob("d05_*.1476")):
        raise ValueError("The supplied directory does not contain ASTAP D05 catalog tiles.")
    if not (0 <= ra_deg < 360 and -90 <= dec_deg <= 90 and 0 < field_height_deg <= 180):
        raise ValueError("Expected valid sky coordinates and image height in degrees.")
    if not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("The solver timeout must be positive and finite.")

    with TemporaryDirectory(prefix="astromosaic-astap-") as directory:
        scratch = Path(directory)
        shutil.copyfile(image, scratch / "input.fits")
        # Use an ASCII scratch name to give ASTAP a portable path to the copied input.
        command = [
            str(executable.resolve()),
            "-f",
            "input.fits",
            "-d",
            str(catalog.resolve()),
            "-D",
            "d05",
            "-ra",
            str(ra_deg / 15),
            "-spd",
            str(dec_deg + 90),
            "-fov",
            str(field_height_deg),
            "-r",
            "3",
            "-z",
            "0",
            "-threads",
            "1",
            "-o",
            "result",
            "-wcs",
        ]
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
                output, _ = process.communicate(timeout=timeout_seconds)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                process.kill()
                process.communicate()
                raise
            if process.returncode:
                detail = output.strip().splitlines()[-1] if output.strip() else "No solver details."
                raise ValueError(f"ASTAP exited with code {process.returncode}. {detail}")
        return _read_solution(scratch)


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
