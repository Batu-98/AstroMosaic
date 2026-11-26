"""Exercise the frozen color and exposure controls before adopting photo corrections."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import imagecodecs
import numpy as np
import pytest
import tifffile

from astromosaic.core import Region
from astromosaic.io import open_panel

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE = _ROOT / "tests/fixtures/phase8c_profile_assignment.json"
_SRGB = _ROOT / "src/astromosaic/io/sRGB2014.icc"


def _replay(module: str, *arguments: str) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", module, *arguments],
        cwd=_ROOT,
        env=os.environ | {"OPENBLAS_NUM_THREADS": "1"},
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    return cast(dict[str, Any], json.loads(result.stdout))


def test_matrix_icc_probe_preserves_gamut_and_all_gradient_steps() -> None:
    report = _replay("tools.phase8c_color_reference", "--srgb-profile", str(_SRGB))
    profiles = report["profiles"]
    srgb = profiles["srgb"]
    assert srgb["neutral_ramp_repeated_steps"] == [18818] * 3
    assert not srgb["matrix_candidate_qualified"]
    for name in ("displayp3", "adobergb"):
        result = profiles[name]
        assert result["matrix_candidate_qualified"]
        assert result["neutral_ramp_repeated_steps"] == [0, 0, 0]
        assert result["neutral_ramp_decreasing_steps"] == [0, 0, 0]
        assert result["linear_range"][0] < 0 < 1 < result["linear_range"][1]

    fixture = json.loads(_FIXTURE.read_bytes())
    for name, patch in fixture["reference_linear_srgb"].items():
        calculated = (
            np.asarray(fixture["rgb_uint16"]) / 65535
            if name == "linear_srgb"
            else profiles[name]["reference_patches_linear_srgb"]["dark_mixed"]
        )
        np.testing.assert_allclose(calculated, patch, atol=1e-11, rtol=0)


def test_profile_assignment_control_tiffs_store_the_same_rgb_codes(tmp_path: Path) -> None:
    fixture = json.loads(_FIXTURE.read_bytes())
    codes = np.array([[fixture["rgb_uint16"]]], dtype=np.uint16)
    p3 = imagecodecs.cms_profile("displayp3")
    fixtures = {
        "srgb": (_SRGB.read_bytes(), "srgb"),
        "displayp3": (p3, "unsupported"),
        "untagged": (None, None),
        "truncated": (p3[:64], "unsupported"),
    }
    for name, (profile, current_encoding) in fixtures.items():
        path = tmp_path / f"{name}.tiff"
        tifffile.imwrite(path, codes, photometric="rgb", metadata=None, iccprofile=profile)
        with open_panel(path) as panel:
            tile = panel.read_tile(Region(0, 0, 1, 1))
            assert tile.valid.all()
            assert panel.descriptor.icc_encoding == current_encoding
            np.testing.assert_array_equal(tile.pixels, codes)


def test_registered_exposure_controls_hold_out_stars_and_keep_validity(tmp_path: Path) -> None:
    owner, peer = _ROOT / "tests/20.TIF", _ROOT / "tests/21.TIF"
    if not owner.is_file() or not peer.is_file():
        pytest.skip("Install the two original owner TIFFs documented in docs/phase-8.md.")
    output = tmp_path / "exposure.npz"
    report = _replay(
        "tools.phase8c_exposure_reference", str(owner), str(peer), "--samples", str(output)
    )
    assert (
        report["actual_owner_capture_metadata"]
        == [{"seconds": 10.0, "f_number": 4.0, "iso": 6400}] * 2
    )
    controls = report["cases"]
    gain = controls["gain_and_offset"]
    assert gain["reference_fit_gain"] == pytest.approx(1.25, abs=0.0001)
    assert gain["reference_fit_offset"] == pytest.approx(-0.003, abs=0.00001)
    assert gain["held_out_samples"] == 61057
    assert gain["held_out_off_rgb_p95"] > 0.0028
    assert gain["held_out_corrected_rgb_p95"] < 0.000003
    assert gain["aperture_flux_maximum_fractional_error"] < 0.0001
    assert controls["weak_gain"]["expected_effective_mode"] == "offset_only"
    assert controls["insufficient_overlap"]["training_samples"] == 16
    assert controls["insufficient_overlap"]["expected_effective_mode"] == "off"

    with np.load(output, allow_pickle=False) as samples:
        validity = samples["gain_and_offset_coverage"]
        black = (samples["gain_and_offset_reference"] == 0).all(axis=-1)
        assert np.any(validity & black)
        region = np.s_[128:256, 256:512]
        assert samples["masked_contamination_coverage"][128:192, 256:384].all()
        assert not samples["masked_contamination_photometry"][region].any()
