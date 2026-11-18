"""Probe an explicitly selected local ASTAP CLI without changing source images.

This development tool writes raw evidence into a new, ignored output directory.
It does not change application settings or download any data.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from math import isfinite
from pathlib import Path
from time import perf_counter

from astropy.io import fits


def fingerprint(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256")
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def run_probe(
    executable: Path,
    catalog: Path,
    image: Path,
    output: Path,
    timeout: float,
    position: tuple[float, float],
    scale: float,
) -> dict[str, object]:
    """Run separate deterministic cases against copies of the same image."""
    for path in (executable, image):
        if not path.is_file():
            raise ValueError(f"Required local file is missing: {path}")
    if not catalog.is_dir():
        raise ValueError("Provide an installed local ASTAP catalog directory.")
    if not isfinite(timeout) or timeout <= 0 or not isfinite(scale) or scale <= 0:
        raise ValueError("Expected positive finite timeout and pixel scale.")
    if not (0 <= position[0] < 360 and -90 <= position[1] <= 90):
        raise ValueError("Expected valid pointing in degrees.")
    header = fits.getheader(image)
    field_height = int(header["NAXIS2"]) * scale / 3600
    output.mkdir(parents=True, exist_ok=False)
    before = fingerprint(image)
    cases = (
        ("manual-tan", ("-D", "d05"), field_height),
        ("native-auto", (), field_height),
        ("explicit-auto", ("-D", "auto"), field_height),
        ("manual-sip", ("-D", "d05", "-sip"), field_height),
        ("extract2", ("-D", "d05", "-extract2", "5"), field_height),
        ("auto-fov", ("-D", "auto"), 0.0),
        ("wrong-fov", ("-D", "auto"), field_height * 0.5),
        ("missing-database", ("-D", "auto"), field_height),
        ("manual-missing-d20", ("-D", "d20"), field_height),
    )
    records: list[dict[str, object]] = []
    for name, extra, case_height in cases:
        work = output / name
        work.mkdir()
        staged = work / "input.fits"
        shutil.copyfile(image, staged)
        staged_before = fingerprint(staged)
        case_catalog = catalog
        if name == "missing-database":
            case_catalog = work / "empty-catalog"
            case_catalog.mkdir()
        command = [
            str(executable.resolve()),
            "-f",
            "input.fits",
            "-d",
            str(case_catalog.resolve()),
            "-ra",
            str(position[0] / 15),
            "-spd",
            str(position[1] + 90),
            "-r",
            "3",
            "-fov",
            str(case_height),
            "-z",
            "0",
            "-threads",
            "1",
            "-o",
            "result",
            "-wcs",
            "-log",
            "-progress",
            *extra,
        ]
        start = perf_counter()
        try:
            result = subprocess.run(
                command,
                cwd=work,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            text, returncode = result.stdout, result.returncode
        except subprocess.TimeoutExpired as error:
            text = (error.stdout or b"").decode("utf-8", errors="replace")
            returncode = None
        elapsed = perf_counter() - start
        (work / "stdout.txt").write_text(text, encoding="utf-8")
        record: dict[str, object] = {
            "name": name,
            "command": command,
            "elapsed_seconds": elapsed,
            "returncode": returncode,
            "files": sorted(path.name for path in work.iterdir()),
            "staged_file_unchanged": fingerprint(staged) == staged_before,
        }
        wcs_path = work / "result.wcs"
        if wcs_path.is_file():
            header = fits.Header.fromstring(wcs_path.read_text("ascii"))
            record["wcs"] = {
                key: header.get(key)
                for key in ("CTYPE1", "CTYPE2", "A_ORDER", "B_ORDER", "AP_ORDER", "BP_ORDER")
            }
        ini = work / "result.ini"
        if ini.is_file():
            record["ini"] = ini.read_text("ascii")
        records.append(record)
        print(
            json.dumps(
                {
                    key: record[key]
                    for key in ("name", "elapsed_seconds", "returncode", "staged_file_unchanged")
                }
            ),
            flush=True,
        )
    after = fingerprint(image)
    if before != after:
        raise RuntimeError("The original fixture changed during the probe.")
    report: dict[str, object] = {
        "schema_version": 1,
        "executable": fingerprint(executable),
        "fixture": before,
        "fixture_unchanged": before == after,
        "catalog_directory": str(catalog.resolve()),
        "cases": records,
    }
    (output / "manifest.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--astap", required=True, type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--image", required=True, type=Path, help="Phase 2 unsolved M13 fixture.")
    parser.add_argument("--output", required=True, type=Path, help="New ignored evidence folder.")
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--hint", type=float, nargs=2, default=(250.42, 36.46))
    parser.add_argument("--scale", type=float, default=1.0069)
    args = parser.parse_args()
    run_probe(
        args.astap,
        args.catalog,
        args.image,
        args.output,
        args.timeout,
        tuple(args.hint),
        args.scale,
    )


if __name__ == "__main__":
    main()
