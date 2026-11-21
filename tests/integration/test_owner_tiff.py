"""Local owner fixtures stay ignored and are optional outside this workspace."""

import hashlib
from pathlib import Path

import fitsio
import numpy as np
import pytest

from astromosaic.astrometry.solve import (
    SolveOptions,
    _pointing,
    _stage_astap_input,
    load_solution,
    solve_panel,
    write_solution,
)
from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.io import open_panel
from astromosaic.storage.project import FileReference, ProjectPanel, inspect_project_panel


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("20.TIF", "c3d7f1bd6264ea489ed62220ef051ffda2911cd9d7c5daef1ce00b9d9983d4db"),
        ("21.TIF", "71aca62355bf0fb86c6ef8012ce98f729a7b90e5cc3d6de1bc4b2db66ed68171"),
    ],
)
def test_owner_rgb_tiff_loads_camera_optics_and_stages_original_green_samples(
    tmp_path: Path,
    name: str,
    expected: str,
) -> None:
    source = Path(__file__).parents[1] / name
    if not source.is_file():
        pytest.skip("The optional private owner TIFF is not installed in this workspace.")
    assert _sha256(source) == expected

    context = JobContext()
    info = inspect_project_panel(ProjectPanel(FileReference.capture(source)), context)
    assert info.wcs_status == "Missing"
    assert info.camera_model == "NIKON D5300"
    assert info.embedded_optics.focal_length_mm == 24
    pitch = 10_000 * 32768 / 83841555
    assert info.embedded_optics.pixel_size_x_um == pytest.approx(pitch)
    assert info.embedded_optics.pixel_size_y_um == pytest.approx(pitch)
    staged = tmp_path / "green.fits"
    with open_panel(source) as panel:
        assert (panel.descriptor.width, panel.descriptor.height) == (6000, 4000)
        assert panel.descriptor.channel_layout == "rgb"
        assert panel.descriptor.icc_encoding == "srgb"
        position, scale, vertical = _pointing(panel, SolveOptions())
        assert position is None
        assert scale == vertical == pytest.approx(206.264806 * pitch / 24)
        _stage_astap_input(panel, staged, SolveOptions(), context)
        with fitsio.FITS(staged) as hdus:
            assert hdus[0].get_info()["dims"] == [4000, 6000]
            for y in (0, 1996, 3992):
                for x in (0, 2996, 5992):
                    tile = panel.read_tile(Region(x, y, 8, 8))
                    np.testing.assert_array_equal(
                        hdus[0][y : y + 8, x : x + 8], tile.pixels[..., 1]
                    )
                    assert tile.valid.all()
    assert _sha256(source) == expected


@pytest.mark.parametrize(("name", "wrong_scale"), [("20.TIF", 16.8), ("21.TIF", 67.2)])
def test_owner_tiff_uses_scale_free_recovery_and_persists_sip(
    tmp_path: Path,
    name: str,
    wrong_scale: float,
) -> None:
    root = Path(__file__).parents[2]
    source = root / "tests" / name
    catalog = root / ".tooling/phase2-gaia/stars-deep-gaia17.bin"
    index = root / ".tooling/phase2-gaia/blind-gaia16.idx"
    if not all(path.is_file() for path in (source, catalog, index)):
        pytest.skip("The optional private owner image and matched local Seiza data are required.")
    pytest.importorskip("seiza")
    original = _sha256(source)
    options = SolveOptions(
        gaia_catalog=catalog,
        gaia_index=index,
        position=(10, 10),
        scale_arcsec=wrong_scale,
        strict_edges=True,
    )
    sidecar = tmp_path / "owner.wcs.json"
    with open_panel(source, max_tile_bytes=options.max_working_bytes) as panel:
        result = solve_panel(panel, options)
        assert result.geometry is not None, result.attempts
        assert result.quality is not None and result.quality["model"] == "SIP-3"
        assert result.quality["edge_status"] == "supported-pass"
        assert float(str(result.quality["held_out_outer_p95_source_px"])) <= 1.5
        attempt = result.attempts[-1]
        assert attempt.stage == "gaia-dr3" and attempt.method == "blind"
        assert attempt.effective_position_deg is None and attempt.effective_scale_arcsec_px is None
        assert attempt.effective_scale_interval_arcsec_px == (0.1, 120.0)
        regions = result.quality["measured_regions"]
        assert isinstance(regions, list) and len(regions) == 81
        assert all(cell["p95_source_px"] is None for cell in regions if cell["matches"] < 5)
        write_solution(sidecar, panel, result)
        reopened, _ = load_solution(sidecar, panel)
        x, y = np.array([0.0, 2999.5, 5999.0]), np.array([0.0, 1999.5, 3999.0])
        assert (
            np.max(reopened.forward(x, y).separation(result.geometry.forward(x, y)).arcsec) < 1e-5
        )
    assert _sha256(source) == original
