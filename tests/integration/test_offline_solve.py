import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from threading import Event

import fitsio
import numpy as np
import pytest
from astropy.io import fits

from astromosaic.astrometry import solve
from astromosaic.astrometry.solve import SolveOptions, solve_panel
from astromosaic.cli import main
from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.io.fits import open_fits_panel
from astromosaic.pipeline.smoke import write_smoke_panel


def test_valid_wcs_reuse_stops_before_catalogs_or_pixel_reads(tmp_path: Path) -> None:
    source = tmp_path / "panel.fits"
    write_smoke_panel(source)
    with open_fits_panel(source) as panel:
        options = SolveOptions(
            gaia_catalog=tmp_path / "missing.bin", astap=tmp_path / "missing.exe"
        )
        result = solve_panel(panel, options)
    assert result.geometry is not None
    assert [(stage.stage, stage.outcome) for stage in result.attempts] == [
        ("existing-wcs", "solved")
    ]


def test_solver_fallback_stages_masked_input_and_renderer_reuses_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    reference = tmp_path / "reference.fits"
    write_smoke_panel(reference)
    solved = fits.getheader(reference)
    source, mask = tmp_path / "unsolved α.fits", tmp_path / "sky.fits"
    pixels = np.full((12, 16), 2.0, dtype=np.float32)
    pixels[8:] = 999.0
    fits.writeto(source, pixels, fits.Header({"BUNIT": "MJy/sr", "FILTER": "L"}))
    fits.writeto(mask, (pixels == 2).astype(np.uint8))
    original = source.read_bytes()
    order = []

    def gaia_failure(*args: object) -> None:
        order.append("gaia")
        raise ValueError("No reliable Gaia match.")

    def fake_astap(
        _exe: Path,
        _db: Path,
        stage: Callable[[Path], None],
        *,
        position: tuple[float, float] | None,
        **kwargs: object,
    ) -> tuple[fits.Header, str]:
        name = "hinted" if position else "blind"
        order.append(name)
        staged = tmp_path / f"staged-{name}.fits"
        stage(staged)
        with fitsio.FITS(staged) as hdus:
            np.testing.assert_array_equal(hdus[0].read(), 2.0)
            assert "CRVAL1" not in hdus[0].read_header()
        if position is not None:
            raise subprocess.TimeoutExpired("ASTAP", 1)
        return solved, "test"

    monkeypatch.setattr(solve, "_solve_gaia", gaia_failure)
    monkeypatch.setattr(solve, "solve_astap", fake_astap)
    sidecar = tmp_path / "panel.wcs.json"
    assert (
        main(
            [
                "solve",
                str(source),
                "-o",
                str(sidecar),
                "--sky-mask",
                str(mask),
                "--gaia-catalog",
                str(tmp_path / "gaia.bin"),
                "--astap",
                str(tmp_path / "astap.exe"),
                "--astap-catalog",
                str(tmp_path),
                "--hint",
                "359.999",
                "20",
                "--scale",
                "7.2",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["stage"] == "astap-blind"
    assert [item["outcome"] for item in report["attempts"]] == [
        "failed",
        "failed",
        "timeout",
        "solved",
    ]
    assert order == ["gaia", "hinted", "blind"]

    destination = tmp_path / "rendered.fits"
    arguments = [
        "mosaic",
        str(source),
        "--wcs",
        f"1={sidecar}",
        "-o",
        str(destination),
        "--center",
        "359.999",
        "20",
        "--size",
        "13",
        "13",
        "--scale",
        "7.2",
    ]
    assert main(arguments) == 1
    assert "different input or sky mask revision" in capsys.readouterr().err
    assert main([*arguments, "--sky-mask", f"1={mask}"]) == 0
    with fitsio.FITS(destination) as hdus:
        result = hdus[0].read()
        valid = hdus["COVERAGE"].read() == 1
        np.testing.assert_array_equal(result[valid], 2)
        assert 0 < np.count_nonzero(valid) < valid.size
        assert np.isnan(result[~valid]).all()
    assert source.read_bytes() == original


def test_exhausted_chain_reports_skips_and_writes_no_solution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "unsolved.fits"
    fits.writeto(source, np.ones((4, 4), dtype=np.float32))
    output = tmp_path / "missing.json"
    assert main(["solve", str(source), "-o", str(output)]) == 1
    details = json.loads(capsys.readouterr().out)
    assert details["status"] == "unsolved"
    assert details["stage"] is None
    assert [item["stage"] for item in details["attempts"]] == [
        "existing-wcs",
        "gaia-dr3",
        "astap-hinted",
        "astap-blind",
    ]
    assert details["attempts"][2]["detail"] == "No usable pointing hint."
    assert not output.exists()


def test_cancellation_during_gaia_stops_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "unresolved.fits"
    fits.writeto(source, np.ones((5, 5), dtype=np.float32))
    cancellation = Event()

    def cancel_in_gaia(*args: object) -> None:
        cancellation.set()
        raise RuntimeError("Native solver cancelled.")

    def unexpected_astap(*args: object, **kwargs: object) -> None:
        pytest.fail("Cancellation started another solver attempt.")

    monkeypatch.setattr(solve, "_solve_gaia", cancel_in_gaia)
    monkeypatch.setattr(solve, "solve_astap", unexpected_astap)
    with open_fits_panel(source) as panel, pytest.raises(MosaicCancelled):
        solve_panel(
            panel,
            SolveOptions(
                gaia_catalog=tmp_path / "gaia.bin",
                astap=tmp_path / "astap.exe",
                astap_catalog=tmp_path,
                position=(0, 0),
            ),
            JobContext(is_cancelled=cancellation.is_set),
        )
