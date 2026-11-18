import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from astropy.io import fits

from astromosaic.astrometry import astap_probe


def test_solution_must_agree_with_status_and_use_solved_keywords(tmp_path: Path) -> None:
    geometry = {
        "CRVAL1": 250.42,
        "CRVAL2": 36.46,
        "CRPIX1": 256.5,
        "CRPIX2": 200.5,
        "CD1_1": -0.001,
        "CD1_2": 0.0001,
        "CD2_1": 0.0001,
        "CD2_2": 0.001,
    }
    ini = tmp_path / "result.ini"
    ini.write_text("PLTSOLVD=T\n" + "\n".join(f"{k}={v}" for k, v in geometry.items()), "ascii")
    header = fits.Header(dict(geometry, CTYPE1="RA---TAN", CTYPE2="DEC--TAN", PLTRAH=17, NAXIS=0))
    wcs_file = tmp_path / "result.wcs"
    wcs_file.write_text(header.tostring(), "ascii")

    assert astap_probe._read_solution(tmp_path) == {
        "ra_deg": 250.42,
        "dec_deg": 36.46,
        "reference_x_fits": 256.5,
        "reference_y_fits": 200.5,
    }

    header["CRVAL1"] = 252.45
    wcs_file.write_text(header.tostring(), "ascii")
    with pytest.raises(ValueError, match="disagree"):
        astap_probe._read_solution(tmp_path)


def test_cancellation_stops_solver_and_releases_scratch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "astap"
    monkeypatch.setattr(
        astap_probe,
        "check_astap_setup",
        Mock(return_value=astap_probe.AstapSetup("CLI-test", ("d05",), "d05", "Manual")),
    )
    source = tmp_path / "field α.fits"
    source.write_bytes(b"source pixels")

    process = MagicMock()
    process.__enter__.return_value = process
    process.communicate.side_effect = [KeyboardInterrupt(), ("", None)]
    start = Mock(return_value=process)
    monkeypatch.setattr(subprocess, "Popen", start)

    with pytest.raises(KeyboardInterrupt):
        astap_probe.solve_d05(
            executable,
            tmp_path,
            source,
            ra_deg=10.0,
            dec_deg=20.0,
            field_height_deg=1.0,
        )

    process.kill.assert_called_once_with()
    assert process.communicate.call_count == 2
    assert not start.call_args.kwargs["cwd"].exists()
    assert source.read_bytes() == b"source pixels"


def test_auto_skips_incomplete_dense_catalog_and_manual_cannot_change_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "astap_cli.exe"
    executable.touch()
    tile = b"GAIA DR3".ljust(109) + b"\x05" + b"\xff" * 3 + b"\x01\x40" + b"\x00" * 5
    suffixes = ("0101.1476", "3601.1476")
    monkeypatch.setattr(astap_probe, "TILE_SUFFIXES", suffixes)
    for suffix in suffixes:
        (tmp_path / f"d20_{suffix}").write_bytes(tile)
    (tmp_path / "d80_0101.1476").write_bytes(tile)
    run = Mock(return_value="ASTAP astrometric solver version CLI-2026.11.01\n")
    monkeypatch.setattr(astap_probe, "_run_astap", run)

    selected = astap_probe.check_astap_setup(executable, tmp_path, "auto")
    assert selected.installed == ("d20",)
    assert selected.command_database == "d20" and "incomplete" in selected.selection_reason
    with pytest.raises(ValueError, match="incomplete"):
        astap_probe.check_astap_setup(executable, tmp_path, "d80")
    assert run.call_count == 1
    run.return_value = "Using star database D80\n"
    with pytest.raises(ValueError, match="unexpected database D80"):
        astap_probe.solve_astap(executable, tmp_path, Path(executable), setup=selected)

    (tmp_path / "d80_3601.1476").write_bytes(tile)
    run.return_value = "ASTAP astrometric solver version CLI-2026.11.01\n"
    native_auto = astap_probe.check_astap_setup(executable, tmp_path, "auto")
    assert native_auto.installed == ("d20", "d80") and native_auto.command_database == "auto"
