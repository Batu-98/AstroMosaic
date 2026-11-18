"""Use the ASTAP CLI with local catalogs and disposable FITS copies."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from math import isclose, isfinite
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from astromosaic.astrometry.astap_catalog import ASTAP_DATABASES, TILE_SUFFIXES
from astromosaic.core.job import DEFAULT_JOB_CONTEXT, JobContext

ASTAP_DATABASE_CHOICES = ("auto", *ASTAP_DATABASES)
_VERIFIED_AUTO_VERSION = "CLI-2026.11.01"
_TILE_HEADER_BYTES = 110
_D_SERIES_RECORD_BYTES = 5
_OTHER_NATIVE_CATALOGS = (
    "w08_0101.001",
    "g05_0101.290",
    "v05_0101.290",
    "v17_0101.290",
    "v50_0101.1476",
)


@contextmanager
def _scratch(prefix: str, context: JobContext) -> Iterator[Path]:
    directory = TemporaryDirectory(prefix=prefix)
    try:
        yield Path(directory.name)
    finally:
        started = monotonic()
        try:
            directory.cleanup()
        finally:
            if context.on_cleanup is not None:
                context.on_cleanup(monotonic() - started)


@dataclass(frozen=True, slots=True)
class AstapSetup:
    version: str
    installed: tuple[str, ...]
    command_database: str
    selection_reason: str


@dataclass(frozen=True, slots=True)
class AstapCandidate:
    header: fits.Header
    version: str
    database: str


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
    candidate = solve_astap(
        executable,
        catalog,
        image,
        position=(ra_deg, dec_deg),
        field_height_deg=field_height_deg,
        timeout_seconds=timeout_seconds,
        database="d05",
    )
    return _summarize_header(candidate.header)


def _check_catalog(catalog: Path, database: str, context: JobContext) -> None:
    name = database.upper()
    for suffix in TILE_SUFFIXES:
        context.check_cancelled()
        tile = catalog / f"{database}_{suffix}"
        if not tile.is_file():
            if suffix == TILE_SUFFIXES[0]:
                raise ValueError(f"No ASTAP {name} catalog tiles found. Check the catalog folder.")
            raise ValueError(f"The ASTAP {name} catalog is incomplete. Missing tile {tile.name}.")
        length = tile.stat().st_size
        if (
            length < _TILE_HEADER_BYTES + 2 * _D_SERIES_RECORD_BYTES
            or (length - _TILE_HEADER_BYTES) % _D_SERIES_RECORD_BYTES
        ):
            raise ValueError(f"The ASTAP {name} tile {tile.name} has an invalid .1476 layout.")
    # The native reader opens the selected tiles. Check the catalog signature up front.
    first = catalog / f"{database}_{TILE_SUFFIXES[0]}"
    with first.open("rb") as stream:
        header = stream.read(_TILE_HEADER_BYTES)
        first_record = stream.read(_D_SERIES_RECORD_BYTES)
    if not (
        len(header) == _TILE_HEADER_BYTES
        and header.startswith(b"GAIA DR3")
        and header[-1] == _D_SERIES_RECORD_BYTES
        and len(first_record) == _D_SERIES_RECORD_BYTES
        and first_record.startswith(b"\xff\xff\xff")
    ):
        raise ValueError(f"The ASTAP {name} tile {first.name} has an invalid .1476 layout.")


def check_astap_setup(
    executable: Path, catalog: Path, database: str, context: JobContext = DEFAULT_JOB_CONTEXT
) -> AstapSetup:
    """Check a CLI and inventory complete supported local catalogs without an image."""
    context.check_cancelled()
    if not executable.is_file():
        raise ValueError("The ASTAP executable is missing. Choose the local ASTAP CLI executable.")
    if not catalog.is_dir():
        raise ValueError("The ASTAP catalog folder is missing. Choose its current location.")
    if database not in ASTAP_DATABASE_CHOICES:
        raise ValueError("Expected Automatic or an ASTAP D05, D20, D50, or D80 database name.")
    installed: list[str] = []
    problems: list[str] = []
    for name in ASTAP_DATABASES if database == "auto" else (database,):
        if database == "auto" and not (catalog / f"{name}_{TILE_SUFFIXES[0]}").exists():
            continue
        try:
            _check_catalog(catalog, name, context)
        except (OSError, ValueError) as error:
            problems.append(str(error))
        else:
            installed.append(name)
    if not installed:
        detail = " ".join(problems) or "No complete ASTAP D05, D20, D50 or D80 catalog found."
        raise ValueError(detail)
    with _scratch("astromosaic-astap-check-", context) as scratch:
        output = _run_astap([str(executable.resolve()), "-h"], scratch, 8, context)
    match = re.search(r"^ASTAP astrometric solver version ([\w.-]+)", output, re.I | re.M)
    if match is None:
        raise ValueError(
            "The selected program did not report an ASTAP solver version. Select the ASTAP CLI."
        )
    native_version = match[1]
    if not native_version.upper().startswith("CLI-"):
        raise ValueError(
            "Choose the ASTAP CLI. The desktop ASTAP executable has not been verified."
        )
    if database != "auto":
        return AstapSetup(native_version, tuple(installed), database, "Manual catalog selection.")
    other_catalog = any((catalog / name).is_file() for name in _OTHER_NATIVE_CATALOGS)
    if native_version == _VERIFIED_AUTO_VERSION and not problems and not other_catalog:
        return AstapSetup(native_version, tuple(installed), "auto", "ASTAP native Automatic.")
    reason = "A native Automatic choice could use an unverified or incomplete catalog."
    if native_version != _VERIFIED_AUTO_VERSION:
        reason = "Native Automatic is unverified for this CLI version."
    return AstapSetup(
        native_version,
        tuple(installed),
        installed[-1],
        f"{reason} AstroMosaic selected the densest complete D-series catalog. "
        + " ".join(problems),
    )


def _native_catalog_path(
    catalog: Path, scratch: Path, setup: AstapSetup, context: JobContext
) -> str:
    path = str(catalog.resolve())
    if os.name != "nt":
        return path
    try:
        if path.encode("mbcs").decode("mbcs") == path:
            return path
    except UnicodeError:
        pass

    # The tested Windows CLI reads legacy-code-page arguments. Use an ASCII
    # scratch alias to the existing files for paths that cannot round-trip.
    alias = scratch / "catalog"
    try:
        alias.symlink_to(catalog.resolve(), target_is_directory=True)
    except OSError:
        alias.mkdir()
        try:
            for database in setup.installed:
                for suffix in TILE_SUFFIXES:
                    context.check_cancelled()
                    name = f"{database}_{suffix}"
                    (alias / name).hardlink_to(catalog / name)
        except OSError as error:
            raise ValueError(
                "ASTAP cannot read this catalog path. Use a folder with a Windows "
                "code-page-compatible name or put scratch and the catalog on the same volume."
            ) from error
    return alias.name


def solve_astap(
    executable: Path,
    catalog: Path,
    image: Path | Callable[[Path], None],
    *,
    position: tuple[float, float] | None = None,
    field_height_deg: float = 0,
    timeout_seconds: float = 60,
    database: str = "auto",
    setup: AstapSetup | None = None,
    search_seconds: Callable[[], float] | None = None,
    sip: bool = False,
    context: JobContext = DEFAULT_JOB_CONTEXT,
) -> AstapCandidate:
    """Run a hinted or blind ASTAP attempt and verify the catalog it actually used."""
    context.check_cancelled()
    if setup is None:
        setup = check_astap_setup(executable, catalog, database, context)
    if not 0 <= field_height_deg <= 180:
        raise ValueError("Expected an ASTAP field height between 0 and 180 degrees.")
    if not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("The solver timeout must be positive and finite.")

    with _scratch("astromosaic-astap-", context) as scratch:
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
            _native_catalog_path(catalog, scratch, setup, context),
            "-D",
            setup.command_database,
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
            "-progress",
        ]
        if position is not None:
            ra_deg, dec_deg = position
            if not (0 <= ra_deg < 360 and -90 <= dec_deg <= 90):
                raise ValueError("Expected valid ASTAP sky coordinates in degrees.")
            command.extend(("-ra", str(ra_deg / 15), "-spd", str(dec_deg + 90)))
        if sip and setup.version == _VERIFIED_AUTO_VERSION:
            command.append("-sip")
        output = _run_astap(
            command,
            scratch,
            search_seconds() if search_seconds is not None else timeout_seconds,
            context,
        )
        context.check_cancelled()
        selected = re.findall(r"^Using star database ([a-z0-9]+)\s*$", output, re.I | re.M)
        if not selected:
            raise ValueError("ASTAP did not identify the catalog used for its solution.")
        actual = selected[-1].lower()
        if actual not in setup.installed or (
            setup.command_database != "auto" and actual != setup.command_database
        ):
            raise ValueError(f"ASTAP used unexpected database {actual.upper()}. Check the catalog.")
        return AstapCandidate(_read_solution_header(scratch), setup.version, actual)


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
        encoding="mbcs" if os.name == "nt" else "utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    ) as process:
        try:
            output = _wait_for_astap(process, timeout_seconds, context)
        except BaseException:
            started = monotonic()
            try:
                process.kill()
                process.communicate()
            finally:
                if context.on_cleanup is not None:
                    context.on_cleanup(monotonic() - started)
            raise
        if process.returncode:
            detail = output.strip().splitlines()[-1] if output.strip() else "No solver details."
            raise ValueError(f"ASTAP exited with code {process.returncode}. {detail}")
        return output


def _wait_for_astap(
    process: subprocess.Popen[str], timeout_seconds: float, context: JobContext
) -> str:
    if context.is_cancelled is None and context.checkpoint is None:
        return process.communicate(timeout=timeout_seconds)[0]
    deadline = monotonic() + timeout_seconds
    while True:
        context.check_cancelled()
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, timeout_seconds)
        try:
            return process.communicate(timeout=min(remaining, 0.1))[0]
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
