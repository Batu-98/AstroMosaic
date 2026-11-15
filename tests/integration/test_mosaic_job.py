from dataclasses import replace
from pathlib import Path
from threading import Event

import numpy as np
import pytest
from astropy.io import fits

from astromosaic.core import Region, Tile
from astromosaic.io.fits import FitsTileSource
from astromosaic.pipeline.mosaic import JobContext, MosaicCancelled, RenderSpec, render_mosaic
from astromosaic.pipeline.smoke import write_smoke_panel

SPEC = RenderSpec((359.999, 20.0), (9, 7), 7.2, tile_size=3)


def test_cancel_releases_handles_and_allows_retry(tmp_path: Path) -> None:
    source = tmp_path / "source.fits"
    write_smoke_panel(source)
    destination = tmp_path / "mosaic.fits"
    cancellation = Event()
    reports = []

    def progress(done: int, total: int) -> None:
        reports.append((done, total))
        assert not destination.exists()
        assert len(list(tmp_path.glob(".astromosaic-*.part"))) == 1
        cancellation.set()

    context = JobContext(is_cancelled=cancellation.is_set, on_progress=progress)
    with pytest.raises(MosaicCancelled):
        render_mosaic([source], destination, SPEC, context=context)
    assert reports == [(9, 63)]
    assert not destination.exists()
    assert not list(tmp_path.glob("*.part"))

    renamed = source.rename(tmp_path / "Gök alanı.fits")
    assert render_mosaic([renamed], destination, SPEC).covered_pixels == 62


def test_destination_race_and_input_alias_do_not_clobber(tmp_path: Path) -> None:
    source = tmp_path / "source.fits"
    write_smoke_panel(source)
    original = source.read_bytes()
    with pytest.raises(FileExistsError):
        render_mosaic([source], source, SPEC)
    assert source.read_bytes() == original

    destination = tmp_path / "mosaic.fits"

    def progress(done: int, total: int) -> None:
        if done == total:
            destination.write_bytes(b"Published during rendering")

    with pytest.raises(FileExistsError):
        render_mosaic([source], destination, SPEC, context=JobContext(on_progress=progress))
    assert destination.read_bytes() == b"Published during rendering"
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (replace(SPEC, max_output_bytes=100), "output byte limit"),
        (replace(SPEC, max_working_bytes=1), "working byte budget"),
        (replace(SPEC, center=(90, -20)), "no valid input coverage"),
    ],
)
def test_infeasible_jobs_leave_no_output_or_pixel_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spec: RenderSpec, message: str
) -> None:
    source = tmp_path / "source.fits"
    write_smoke_panel(source)
    destination = tmp_path / "mosaic.fits"

    def unexpected_pixels(_panel: FitsTileSource, _region: Region, *, halo: int = 0) -> Tile:
        pytest.fail("The renderer read pixels from an infeasible or non-overlapping input.")

    monkeypatch.setattr(FitsTileSource, "read_tile", unexpected_pixels)
    with pytest.raises(ValueError, match=message):
        render_mosaic([source], destination, spec)
    assert not destination.exists()
    assert not list(tmp_path.glob("*.part"))


def test_incomplete_wcs_and_panel_metadata_require_explicit_input(tmp_path: Path) -> None:
    source = tmp_path / "source.fits"
    write_smoke_panel(source)
    with fits.open(source, do_not_scale_image_data=True) as hdus:
        header = hdus[0].header.copy()
    pixels = np.ones((12, 16), dtype=np.float32)
    for key in ("FILTER", "BUNIT", "BSCALE", "BZERO", "BLANK"):
        del header[key]
    missing = tmp_path / "missing-labels.fits"
    fits.writeto(missing, pixels, header=header)
    output = tmp_path / "mosaic.fits"
    with pytest.raises(ValueError, match="common FILTER"):
        render_mosaic([missing], output, SPEC)
    with pytest.raises(ValueError, match="surface-brightness BUNIT"):
        render_mosaic([missing], output, SPEC, filter_name="L")

    pixel_flux = tmp_path / "pixel-flux.fits"
    header["BUNIT"] = "Jy/pix"
    fits.writeto(pixel_flux, pixels, header=header)
    with pytest.raises(ValueError, match="Per-pixel units"):
        render_mosaic([pixel_flux], output, SPEC, filter_name="L", assume_surface_brightness=True)
    assert not output.exists()

    missing_wcs = tmp_path / "missing-wcs.fits"
    del header["CRVAL1"]
    fits.writeto(missing_wcs, pixels, header=header)
    with pytest.raises(ValueError, match="Input panel 1: Expected an existing celestial WCS"):
        render_mosaic([missing_wcs], output, SPEC)

    assert (
        render_mosaic(
            [missing], output, SPEC, filter_name="L", assume_surface_brightness=True
        ).covered_pixels
        == 63
    )
    exported = fits.getheader(output)
    assert exported["FILTER"] == "L"
    assert "BUNIT" not in exported
    assert any("User declared a common" in line for line in exported["HISTORY"])
