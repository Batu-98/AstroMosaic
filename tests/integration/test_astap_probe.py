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
    executable.touch()
    (tmp_path / "d05_0101.1476").touch()
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
