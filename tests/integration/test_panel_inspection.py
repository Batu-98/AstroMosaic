from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import tifffile
from astropy.io import fits

from astromosaic.astrometry import solve
from astromosaic.astrometry.hints import PanelOptics
from astromosaic.astrometry.solve import SolveOptions, solve_panel, write_solution
from astromosaic.cli import main
from astromosaic.core.job import JobContext
from astromosaic.core.masks import SKY, SourceMask
from astromosaic.io import open_panel
from astromosaic.pipeline.smoke import write_smoke_panel
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    inspect_project_panel,
    save_project,
)


@pytest.mark.parametrize("suffix", [".fits", ".tiff"])
def test_panel_wcs_status_and_optics(tmp_path: Path, suffix: str) -> None:
    reference = tmp_path / "reference.fits"
    write_smoke_panel(reference)
    header = fits.getheader(reference)
    for key in ("BSCALE", "BZERO", "BLANK"):
        del header[key]
    header["FOCALLEN"] = 450.0
    header["XPIXSZ"] = (3.75, "Unbinned pixel size in micrometers")
    header["YPIXSZ"] = (7.5, "Pixel size in micrometers (after binning)")
    header["XBINNING"] = header["YBINNING"] = 2
    pixels = np.ones((12, 16), dtype=np.float32)
    image = tmp_path / f"panel{suffix}"
    if suffix == ".fits":
        fits.writeto(image, pixels, header)
    else:
        tifffile.imwrite(
            image,
            pixels,
            metadata=None,
            description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False),
        )

    panel = ProjectPanel(FileReference.capture(image))
    context = JobContext()
    info = inspect_project_panel(panel, context)
    assert info.wcs_status == "Embedded"
    assert info.embedded_optics == PanelOptics(450.0, 7.5, 7.5)
    sidecar = tmp_path / "solved.wcs.json"
    with open_panel(image) as opened:
        write_solution(sidecar, opened, solve_panel(opened, SolveOptions()))
    attached = replace(panel, wcs_sidecar=FileReference.capture(sidecar))
    assert inspect_project_panel(attached, context).wcs_status == "Sidecar"
    edited = replace(attached, source_mask=SourceMask((16, 12), bytes([SKY]) * pixels.size))
    stale = inspect_project_panel(edited, context)
    assert stale.wcs_status == "Invalid"
    assert "different input or sky mask revision" in stale.detail
    relocated = image.rename(tmp_path / f"moved{suffix}")
    assert inspect_project_panel(panel, context).wcs_status == "Unavailable"
    assert (
        inspect_project_panel(
            replace(attached, source=panel.source.relink(relocated)), context
        ).wcs_status
        == "Sidecar"
    )


def test_missing_metadata_and_invalid_wcs_are_distinct(tmp_path: Path) -> None:
    plain = tmp_path / "plain.tif"
    tifffile.imwrite(plain, np.ones((5, 5), dtype=np.uint16), resolution=(300, 300))
    malformed = tmp_path / "malformed.fits"
    fits.writeto(
        malformed,
        np.ones((5, 5), dtype=np.uint16),
        fits.Header({"CTYPE1": "RA---TAN", "FOCALLEN": -12, "XPIXSZ": "unknown", "YPIXSZ": True}),
    )
    for path, status in ((plain, "Missing"), (malformed, "Invalid")):
        info = inspect_project_panel(ProjectPanel(FileReference.capture(path)), JobContext())
        assert info.wcs_status == status
        assert info.embedded_optics == PanelOptics()
    malformed.write_bytes(b"not a FITS image")
    unreadable = inspect_project_panel(ProjectPanel(FileReference.capture(malformed)), JobContext())
    assert unreadable.wcs_status == "Unavailable"
    assert unreadable.detail


def test_cli_solve_uses_project_optics_and_scale_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = tmp_path / "panel.fits"
    reference = tmp_path / "reference.fits"
    write_smoke_panel(reference)
    solved = fits.getheader(reference)
    header = fits.Header(
        {"FOCALLEN": 400, "XPIXSZ": 3.75, "YPIXSZ": 3.75, "XBINNING": 2, "YBINNING": 2}
    )
    heights: list[object] = []

    def fake_astap(*args: object, **kwargs: object) -> tuple[fits.Header, str]:
        assert kwargs["position"] is None
        heights.append(kwargs["field_height_deg"])
        return solved, "test ASTAP"

    monkeypatch.setattr(solve, "solve_astap", fake_astap)
    manifest = tmp_path / "test.astromosaic"

    def check(expected: float, *options: str) -> None:
        fits.writeto(image, np.ones((12, 16), dtype=np.float32), header, overwrite=True)
        panel = ProjectPanel(FileReference.capture(image), optics=PanelOptics(500, 4.0, 5.0))
        save_project(manifest, MosaicProject((panel,)), replace_existing=True)
        arguments = ["--astap", str(tmp_path / "ASTAP.exe"), "--astap-catalog", str(tmp_path)]
        assert main(["solve", str(manifest), "--panel", "1", *arguments, *options]) == 0
        assert heights.pop() == pytest.approx(12 * expected / 3600)

    check(206.264806 * 5 / 500)
    header["PIXSCALE"] = 1.75
    check(1.75)
    check(3.25, "--scale", "3.25")
    assert (
        main(["solve", str(image), "--astap", "ASTAP.exe", "--astap-catalog", str(tmp_path)]) == 0
    )
    assert heights.pop() == pytest.approx(12 * 1.75 / 3600)
    del header["PIXSCALE"]
    fits.writeto(image, np.ones((12, 16), dtype=np.float32), header, overwrite=True)
    info = inspect_project_panel(ProjectPanel(FileReference.capture(image)), JobContext())
    assert info.embedded_optics == PanelOptics(400)


def test_gaia_uses_a_scalar_hint_for_equal_axis_scales(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = tmp_path / "panel.fits"
    reference = tmp_path / "reference.fits"
    write_smoke_panel(reference)
    solved = fits.getheader(reference)
    header = fits.Header({"RA": 359.999, "DEC": 20.0, "FOCALLEN": 500, "XPIXSZ": 4, "YPIXSZ": 4})
    fits.writeto(image, np.ones((12, 16), dtype=np.float32), header)
    seen: list[float | None] = []

    def fake_gaia(
        source: object,
        options: SolveOptions,
        catalog: Path,
        position: tuple[float, float] | None,
        scale: float | None,
        context: JobContext,
    ) -> tuple[fits.Header, solve.SolverAttempt]:
        assert position == (359.999, 20)
        seen.append(scale)
        return solved, solve.SolverAttempt("gaia-dr3", "solved", "test Gaia")

    monkeypatch.setattr(solve, "_solve_gaia", fake_gaia)
    options = SolveOptions(gaia_catalog=tmp_path / "gaia.bin")
    with open_panel(image) as panel:
        assert solve_panel(panel, options).stage == "gaia-dr3"
        assert (
            solve_panel(panel, replace(options, optics=PanelOptics(pixel_size_y_um=5))).stage
            == "gaia-dr3"
        )
    assert seen[0] == pytest.approx(206.264806 * 4 / 500)
    assert seen[1] is None
