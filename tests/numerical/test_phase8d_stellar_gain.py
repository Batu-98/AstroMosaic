"""Qualify the offline gain guard with independent and injected real observations."""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import tifffile

from astromosaic.core import Region
from astromosaic.photometry.photo_settings import PhotoProfile, PhotoSettings
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.storage.project import FileReference, MosaicProject, ProjectPanel, save_project
from tools.phase8d_overlap_reference import (
    _OWNER_HASH,
    _decode,
    _digest,
    _encode,
    measure_project,
)
from tools.phase8d_stellar_gain import Aperture, qualify_gains

_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("method", ["standard", "gain-plane"])
def test_stellar_gate_accepts_injected_gain(tmp_path: Path, method: str) -> None:
    owner = _ROOT / "tests/20.TIF"
    if not owner.is_file():
        pytest.skip("Install the frozen owner reference documented in docs/phase-8d.md.")
    assert _digest(owner) == _OWNER_HASH
    original = tifffile.memmap(owner, mode="r")
    crop = _decode(original[1408:2432, 2048:3584])
    del original
    grid = RenderSpec((120, -25), (1536, 1024), 4)
    panels = []
    truth = np.array(
        [(1.0, 0.0, 0.0, 0.0), (1.25, -0.005, 0.0025, -0.0015), (0.84, -0.004, -0.0015, 0.0015)]
    )
    if method == "standard":
        truth[:, 2:] = 0
    for name, (left, right), (gain, offset, dx, dy) in zip(
        "ABC", ((0, 948), (192, 1320), (384, 1536)), truth, strict=True
    ):
        height = grid.size[1]
        width = right - left
        plane = offset + dx * np.linspace(-1, 1, width) + dy * np.linspace(-1, 1, height)[:, None]
        values = (crop[:, left:right] - plane[..., None]) / gain
        path = tmp_path / f"{name}.tiff"
        detector = replace(grid, crop=Region(left, 0, width, height))
        header = detector.output_wcs().to_header().tostring(sep="\n")
        tifffile.imwrite(
            path,
            _encode(values),
            photometric="rgb",
            metadata=None,
            description="AstroMosaic TIFF 1\n" + header,
        )
        panels.append(ProjectPanel(FileReference.capture(path)))
    project = tmp_path / "injected.astromosaic"
    save_project(
        project,
        MosaicProject(tuple(panels), grid, photo_settings=PhotoSettings(PhotoProfile("srgb"))),
    )
    report = measure_project(project, preserve_calibrated_scale=True, stellar_gain=True)
    stellar = report["stellar_gain"]
    assert isinstance(stellar, dict)
    assert stellar["selected"] == method, stellar
    selected = stellar["candidates"][method]
    assert selected["selection_passed"] and selected["test_passed"]
    assert all(abs(edge["test"]["median_after"]) <= 0.01 for edge in selected["edges"])
    coefficients = report["coefficients"]
    assert isinstance(coefficients, dict)
    recovered = np.array(list(coefficients[method].values()))
    np.testing.assert_allclose(recovered[:, 0], truth[:, 0], rtol=0.01)
    np.testing.assert_allclose(recovered[:, 1:], truth[:, 1:], atol=2e-4)
    assert report["verified_order_independence"]
    assert _digest(owner) == _OWNER_HASH


def test_stellar_gate_rejects_calibrated_sdss_gain(tmp_path: Path) -> None:
    project = _ROOT / "output/phase8d-candidates/sdss/m2/comparison.astromosaic"
    if not project.is_file():
        pytest.skip("Prepare the calibrated SDSS M2 reference documented in docs/phase-8d.md.")
    exported = subprocess.run(
        [
            sys.executable,
            "-m",
            "astromosaic",
            "project",
            "export-photo",
            str(project),
            "-o",
            str(tmp_path / "standard.tiff"),
            "--brightness",
            "standard",
            "--json",
        ],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert exported.returncode == 0, exported.stderr
    runtime = json.loads(exported.stdout)
    application = {row["panel"]: (row["brightness"]["gain"],) for row in runtime["photo"]["panels"]}
    report = measure_project(
        project,
        preserve_calibrated_scale=True,
        stellar_gain=True,
        additional_gains={"application-standard": application},
    )
    assert report["selected"] == "gain-offset"
    stellar = report["stellar_gain"]
    assert isinstance(stellar, dict)
    assert stellar["selected"] == "off"
    for model in ("standard", "gain-offset", "gain-plane", "application-standard"):
        candidate = stellar["candidates"][model]
        assert not candidate["selection_passed"] and not candidate["test_passed"]
        assert candidate["edges"][0]["test"]["status"] == "rejected"
    assert stellar["candidates"]["fixed-gain-plane"]["selection_passed"]


def test_stellar_gate_requires_independent_spatial_support() -> None:
    report = {
        "scored_edges": [["A", "B"]],
        "coefficients": {"off": {"A": [1.0], "B": [1.0]}, "gain": {"A": [1.0], "B": [1.25]}},
    }
    first = [Aperture((64.0 + i * 3, 64.0 * 4), (1, 4), 1.0) for i in range(10)]
    second = [replace(star, flux=0.8) for star in first]
    result = qualify_gains(report, {"A": first, "B": second})
    assert result["eligible"] == ["off"]
    candidates = result["candidates"]
    assert isinstance(candidates, dict)
    edge = candidates["gain"]["edges"][0]
    assert edge["selection"]["stars"] == 10
    assert edge["selection"]["status"] == "insufficient"
    assert edge["test"]["stars"] == 0
