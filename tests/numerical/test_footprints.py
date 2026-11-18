from pathlib import Path

import fitsio
import numpy as np
import pytest
from astropy.coordinates import FK5, ICRS
from astropy.io import fits
from astropy.wcs import WCS, Sip

from astromosaic.core import Region
from astromosaic.geometry import PanelGeometry, TileSky, tan_output_wcs
from astromosaic.geometry.footprint import tan_footprint
from astromosaic.photometry import PanelCorrection
from astromosaic.pipeline import mosaic
from astromosaic.pipeline.mosaic import RenderSpec, _Coordinates, preview_mosaic, render_mosaic
from astromosaic.pipeline.refinement import RefinementReport, RefinementSpec


@pytest.mark.parametrize("case", ["sip", "tpv", "other_frame", "horizon", "reverse_horizon"])
def test_unproven_tan_bounds_use_the_full_mapper(case: str) -> None:
    source_size = (48, 42)
    target_size = (256, 144)
    source_center = (180.0, 0.0) if case == "horizon" else (60.0, 0.0)
    source = tan_output_wcs(source_center, source_size, 4, 0, Region(0, 0, *source_size))
    scale = 4500 if case == "reverse_horizon" else 4
    target = tan_output_wcs((0, 0), target_size, scale, 0, Region(0, 0, *target_size))
    frame = FK5() if case == "other_frame" else ICRS()
    if case == "sip":
        a = np.zeros((3, 3))
        a[2, 0] = 0.002
        source.sip = Sip(a, np.zeros_like(a), None, None, source.wcs.crpix)
    if case == "tpv":
        header = source.to_header()
        header.update(
            {
                "CTYPE1": "RA---TPV",
                "CTYPE2": "DEC--TPV",
                "PV1_1": 1.0,
                "PV2_1": 1.0,
                "PV1_4": 0.05,
                "PV2_5": 0.01,
            }
        )
        source = WCS(header)
    assert (
        tan_footprint(
            PanelGeometry(source, frame),
            PanelGeometry(target, ICRS()),
            source_size,
            target_size,
            (0.0, 0.0),
        )
        is None
    )


def test_tan_selection_preserves_shifted_cropped_mosaic_and_keeps_sip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_size = (48, 42)
    spec = RenderSpec((359.999, 25), (256, 144), 4, 19, Region(8, 7, 240, 128), 16)
    y, x = np.indices(source_size[::-1], dtype=np.float32)
    sources = []
    for index, center in enumerate(((359.91, 25.02), (0.08, 24.96), (359.997, 24.99))):
        wcs = tan_output_wcs(center, source_size, 4, 11, Region(0, 0, *source_size))
        if index == 1:
            wcs.wcs.cdelt[0] *= -1
        if index == 2:
            wcs.wcs.ctype = ["RA---TAN-SIP", "DEC--TAN-SIP"]
            a = np.zeros((3, 3))
            a[2, 0] = 0.002
            wcs.sip = Sip(a, np.zeros_like(a), None, None, wcs.wcs.crpix)
        header = wcs.to_header(relax=True)
        header["FILTER"], header["BUNIT"] = "L", "MJy/sr"
        source = tmp_path / f"panel-{index}.fits"
        pixels = x * 0.75 - y * 0.5 + index
        pixels[23:28, 14:19] = np.nan
        fits.writeto(source, pixels, header)
        sources.append(source)
    mask = tmp_path / "mask.fits"
    fits.writeto(mask, (x > 6).astype(np.uint8))

    controls = RefinementSpec(max_shift_px=32)
    fitted = RefinementReport(
        "ready",
        ((1, 2, 3),),
        (48, 48, 48),
        (),
        None,
        None,
        corrections=(PanelCorrection(), PanelCorrection(shift=(24, -13)), PanelCorrection()),
    )
    monkeypatch.setattr(mosaic, "refine_panels", lambda *_args: fitted)

    counts = {"tan": 0, "sip": 0}
    locate = TileSky.in_panel

    def count_mapping(
        self: TileSky, geometry: PanelGeometry, shift: tuple[float, float]
    ) -> _Coordinates:
        counts["sip" if geometry.wcs.has_distortion else "tan"] += 1
        return locate(self, geometry, shift)

    monkeypatch.setattr(TileSky, "in_panel", count_mapping)
    selected = tmp_path / "selected.fits"
    result = render_mosaic(sources, selected, spec, sky_masks={1: mask}, refinement=controls)
    assert 0 < counts["tan"] < result.tiles
    assert counts["sip"] == result.tiles
    assert result.covered_pixels > 1000
    monkeypatch.setattr(mosaic, "_PREVIEW_EDGE", 96)
    preview = preview_mosaic(sources, spec, sky_masks={1: mask}, refinement=controls)
    assert preview.tile.region.width == 96

    monkeypatch.setattr(mosaic, "_footprint_reservation", lambda *_args: 0)
    reference = tmp_path / "reference.fits"
    full = render_mosaic(sources, reference, spec, sky_masks={1: mask}, refinement=controls)
    assert result.covered_pixels == full.covered_pixels
    full_preview = preview_mosaic(sources, spec, sky_masks={1: mask}, refinement=controls)
    np.testing.assert_array_equal(preview.tile.pixels, full_preview.tile.pixels)
    np.testing.assert_array_equal(preview.tile.valid, full_preview.tile.valid)
    with fitsio.FITS(selected) as actual, fitsio.FITS(reference) as expected:
        np.testing.assert_array_equal(actual[0].read(), expected[0].read())
        np.testing.assert_array_equal(actual["COVERAGE"].read(), expected["COVERAGE"].read())
    assert fits.getheader(selected) == fits.getheader(reference)
