import json
import subprocess
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from threading import Event

import fitsio
import numpy as np
import pytest
from astropy.io import fits

from astromosaic.astrometry import solve
from astromosaic.astrometry.astap_probe import AstapCandidate
from astromosaic.astrometry.solve import SolveOptions, solve_panel
from astromosaic.astrometry.stars import measure_stars
from astromosaic.cli import main
from astromosaic.core import Region
from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.core.masks import FOREGROUND, SKY, SourceMask
from astromosaic.geometry import tan_output_wcs
from astromosaic.io import open_panel
from astromosaic.io.fits import open_fits_panel
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.pipeline.smoke import write_smoke_panel
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    load_project,
    preview_project,
    save_project,
)


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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stub_solve_evidence: None,
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
    (tmp_path / "gaia.bin").touch()

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
    ) -> AstapCandidate:
        name = "hinted" if position else "blind"
        order.append(name)
        staged = tmp_path / f"staged-{name}.fits"
        stage(staged)
        with fitsio.FITS(staged) as hdus:
            np.testing.assert_array_equal(hdus[0].read(), 2.0)
            assert "CRVAL1" not in hdus[0].read_header()
        if position is not None:
            raise subprocess.TimeoutExpired("ASTAP", 1)
        assert kwargs["field_height_deg"] == 0
        return AstapCandidate(solved, "CLI-test", "d05")

    monkeypatch.setattr(solve, "search_gaia", gaia_failure)
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
    assert report["attempts"][-1]["catalog"] == "d05"
    assert [item["outcome"] for item in report["attempts"]] == [
        "failed",
        "timeout",
        "solved",
    ]
    assert order == ["hinted", "blind"]

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
    assert details["status"] == "unavailable"
    assert details["stage"] is None
    assert [item["stage"] for item in details["attempts"]] == [
        "existing-wcs",
        "astap-hinted",
        "astap-blind",
        "gaia-dr3",
    ]
    assert details["attempts"][1]["detail"] == "No usable pointing or scale hint."
    assert not output.exists()


def test_project_solve_uses_edited_mask_and_rejects_a_stale_wcs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stub_solve_evidence: None,
) -> None:
    width, height = size = (160, 176)
    center = (359.999, 20.0)
    y, x = np.mgrid[:height, :width]
    pixels = np.full((height, width), 2.0, dtype=np.float32)
    pixels[74:88] = 500
    pixels[88:] = 999
    for star_y in (113, 146):
        for star_x in (28, 62, 96, 130):
            pixels += 320 * np.exp(-((y - star_y) ** 2 + (x - star_x) ** 2) / 5.2)
    source = tmp_path / "mixed.fits"
    fits.writeto(source, pixels, fits.Header({"BUNIT": "MJy/sr", "FILTER": "L"}))
    original = source.read_bytes()
    labels = np.zeros((height, width), dtype=np.uint8)
    labels[:74], labels[88:] = SKY, FOREGROUND
    mask = SourceMask(size, labels.tobytes())
    panel = ProjectPanel(FileReference.capture(source), foreground_suggestion="mixed")
    project = MosaicProject((panel,), RenderSpec(center, size, 7.2))
    manifest = tmp_path / "night.astromosaic"
    save_project(manifest, project)
    sidecar = tmp_path / "panel.wcs.json"
    args = ["solve", str(manifest), "--panel", "1", "-o", str(sidecar)]
    assert main(args) == 1
    assert "Apply a sky mask" in capsys.readouterr().err
    assert not sidecar.exists()

    with open_panel(source) as raw:
        unmasked = measure_stars(raw, 64 * 1024**2, JobContext())
        assert np.any(unmasked.exclusions[:, 1] > 100)

    def astap_uses_sky(
        _exe: Path, _db: Path, stage: Callable[[Path], None], **kwargs: object
    ) -> AstapCandidate:
        staged = tmp_path / "staged-project.fits"
        stage(staged)
        with fitsio.FITS(staged) as hdus:
            np.testing.assert_array_equal(hdus[0].read(), 2.0)
        header = tan_output_wcs(center, size, 7.2, 0, Region(0, 0, width, height)).to_header()
        return AstapCandidate(header, "CLI-test", "d05")

    monkeypatch.setattr(solve, "solve_astap", astap_uses_sky)
    panel = replace(panel, source_mask=mask)
    save_project(manifest, replace(project, panels=(panel,)), replace_existing=True)
    assert (
        main(
            [
                *args,
                "--gaia-catalog",
                "local.bin",
                "--astap",
                "astap.exe",
                "--astap-catalog",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["stage"] == "astap-blind"

    panel = replace(panel, wcs_sidecar=FileReference.capture(sidecar))
    save_project(manifest, replace(project, panels=(panel,)), replace_existing=True)
    reopened = load_project(manifest)
    preview = preview_project(reopened, JobContext())
    assert preview.tile.valid[40, 80] and not preview.tile.valid[100, 80]
    assert np.nanmax(preview.tile.pixels) == 2
    assert main(args[:-2]) == 0
    assert json.loads(capsys.readouterr().out)["quality"]["grade"] == "geometry-only"

    labels[75, 80] = FOREGROUND
    assert SourceMask(size, labels.tobytes()).sky_fingerprint == mask.sky_fingerprint
    labels[40, 80] = FOREGROUND
    edited = replace(panel, source_mask=SourceMask(size, labels.tobytes()))
    with pytest.raises(ValueError, match="different input or sky mask revision"):
        preview_project(replace(project, panels=(edited,)), JobContext())
    assert source.read_bytes() == original


def test_cancellation_during_gaia_stops_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stub_solve_evidence: None,
) -> None:
    source = tmp_path / "unresolved.fits"
    fits.writeto(source, np.ones((5, 5), dtype=np.float32))
    cancellation = Event()
    catalog, index = tmp_path / "gaia.bin", tmp_path / "blind.idx"
    catalog.touch()
    index.touch()
    calls = []

    def cancel_in_gaia(*args: object) -> None:
        calls.append("hinted")
        cancellation.set()
        raise RuntimeError("Native solver cancelled.")

    monkeypatch.setattr(solve, "search_gaia", cancel_in_gaia)
    with open_fits_panel(source) as panel, pytest.raises(MosaicCancelled):
        solve_panel(
            panel,
            SolveOptions(
                gaia_catalog=catalog,
                gaia_index=index,
                position=(0, 0),
                scale_arcsec=1,
            ),
            JobContext(is_cancelled=cancellation.is_set),
        )
    assert calls == ["hinted"]
