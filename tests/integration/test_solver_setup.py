import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from astromosaic.astrometry import astap_probe
from astromosaic.astrometry.solve import SolveOptions
from astromosaic.astrometry.solver_setup import check_solver_paths
from astromosaic.core.job import JobContext


def test_reports_gaia_hints_and_broken_catalog_or_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = tmp_path / "stars.bin"
    index = tmp_path / "blind.idx"
    catalog.write_bytes(b"catalog")
    index.write_bytes(b"index")

    def open_catalog(path: Path) -> SimpleNamespace:
        if path.read_bytes() != b"catalog":
            raise OSError("wrong star catalog format")
        return SimpleNamespace(star_count=lambda: 40)

    def open_index(path: Path) -> SimpleNamespace:
        if path.read_bytes() != b"index":
            raise OSError("wrong index format")
        return SimpleNamespace(pattern_count=lambda: 20)

    monkeypatch.setitem(
        sys.modules,
        "seiza",
        SimpleNamespace(
            StarCatalog=SimpleNamespace(open=open_catalog),
            BlindIndex=SimpleNamespace(open=open_index),
        ),
    )
    options = SolveOptions(gaia_catalog=catalog)
    gaia, astap = check_solver_paths(options)
    assert "requires panel pointing and plate scale" in gaia
    assert "Add the matching blind index" in gaia
    assert "Choose the ASTAP CLI" in astap

    options = replace(options, gaia_index=index)
    assert "Catalog and blind index open" in check_solver_paths(options)[0]
    index.write_bytes(b"catalog")
    assert "Could not open the blind index" in check_solver_paths(options)[0]
    index.rename(tmp_path / "moved.idx")
    assert "Blind index is missing" in check_solver_paths(options)[0]
    catalog.write_bytes(b"index")
    assert "Could not open the Gaia DR3 catalog" in check_solver_paths(options)[0]
    catalog.rename(tmp_path / "moved.bin")
    assert "Browse to its current file location" in check_solver_paths(options)[0]


def test_checks_astap_installation_when_gaia_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "astap_cli.exe"
    executable.touch()
    tile = tmp_path / "d50_0101.1476"
    contents = b"GAIA DR3".ljust(109) + b"\x05" + b"\xff\xff\xff\x01\x40" + b"\x00" * 5
    tile.write_bytes(contents)
    other_tile = tmp_path / "d50_3601.1476"
    other_tile.write_bytes(contents)
    monkeypatch.setattr(astap_probe, "TILE_SUFFIXES", ("0101.1476", "3601.1476"))
    calls: list[Path] = []

    def run_help(command: list[str], scratch: Path, timeout: float, context: JobContext) -> str:
        assert command == [str(executable), "-h"]
        assert scratch.is_dir() and 0 < timeout < 15
        calls.append(scratch)
        context.check_cancelled()
        return "ASTAP astrometric solver version CLI-2026.11.01, multi-threaded"

    monkeypatch.setattr(astap_probe, "_run_astap", run_help)
    monkeypatch.setitem(sys.modules, "seiza", None)
    options = SolveOptions(
        gaia_catalog=tmp_path / "stars.bin",
        astap=executable,
        astap_catalog=tmp_path,
        astap_database="d50",
    )
    gaia, astap = check_solver_paths(options)
    assert "Gaia DR3 support is unavailable" in gaia
    assert "CLI-2026.11.01 responds. Complete catalogs: D50." in astap
    assert len(calls) == 1 and not calls[0].exists()

    mistaken_database = replace(options, astap_database="d20")
    assert "No ASTAP D20 catalog tiles found" in check_solver_paths(mistaken_database)[1]
    assert (
        "catalog folder is missing"
        in check_solver_paths(replace(options, astap_catalog=tmp_path / "moved"))[1]
    )
    other_tile.rename(tmp_path / "moved.1476")
    assert "Missing tile d50_3601.1476" in check_solver_paths(options)[1]
    other_tile.write_bytes(contents[:-1])
    assert "invalid .1476 layout" in check_solver_paths(options)[1]
    other_tile.write_bytes(contents)
    tile.write_bytes(b"format invalid")
    assert "invalid .1476 layout" in check_solver_paths(options)[1]
    executable.rename(tmp_path / "moved.exe")
    assert "executable is missing" in check_solver_paths(options)[1]
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("Unknown program", "did not report an ASTAP solver version"),
        (None, "did not answer the help check in time"),
    ],
)
def test_reports_wrong_or_unresponsive_astap_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: str | None, expected: str
) -> None:
    executable = tmp_path / "other.exe"
    executable.touch()
    (tmp_path / "d05_0101.1476").write_bytes(
        b"GAIA DR3".ljust(109) + b"\x05" + b"\xff" * 3 + b"\x01\x40" + b"\x00" * 5
    )
    monkeypatch.setattr(astap_probe, "TILE_SUFFIXES", ("0101.1476",))

    def run_help(command: list[str], scratch: Path, timeout: float, context: JobContext) -> str:
        if output is None:
            raise subprocess.TimeoutExpired(command, timeout)
        return output

    monkeypatch.setattr(astap_probe, "_run_astap", run_help)
    assert expected in check_solver_paths(SolveOptions(astap=executable, astap_catalog=tmp_path))[1]
