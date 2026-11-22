"""Exercise the profile and exposure choices through the shared sky workflow."""

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Literal

import imagecodecs
import numpy as np
import pytest
import tifffile
from numpy.typing import NDArray

from astromosaic.cli import main
from astromosaic.core import Region
from astromosaic.core.job import DEFAULT_JOB_CONTEXT, JobContext, MosaicCancelled
from astromosaic.io import open_panel
from astromosaic.io.tiff_metadata import CameraExposure
from astromosaic.photometry.photo_match import metadata_gain
from astromosaic.photometry.photo_settings import PhotoProfile, PhotoSettings
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.pipeline.photo_color import resolve_photo_profile
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    load_project,
    preview_project,
    render_project,
    render_project_photo,
    save_project,
)

_JOB = DEFAULT_JOB_CONTEXT
_SRGB = Path(__file__).resolve().parents[2] / "src/astromosaic/io/sRGB2014.icc"


def _encode(linear: NDArray[np.float64]) -> NDArray[np.uint16]:
    values = np.clip(linear, 0, 1)
    return np.rint(
        65535 * np.where(values <= 0.0031308, values * 12.92, 1.055 * values ** (1 / 2.4) - 0.055)
    ).astype(np.uint16)


def _write(
    path: Path,
    pixels: NDArray[np.uint16],
    grid: RenderSpec,
    *,
    icc: bytes | None = None,
    exif_srgb: bool = False,
) -> ProjectPanel:
    tifffile.imwrite(
        path,
        pixels,
        iccprofile=icc,
        photometric="rgb",
        metadata=None,
        description="AstroMosaic TIFF 1\n" + grid.output_wcs().to_header().tostring(sep="\n"),
        extratags=[(40961, "H", 1, 1, False)] if exif_srgb else (),
    )
    return ProjectPanel(FileReference.capture(path))


@pytest.mark.parametrize(
    ("profile", "reference"),
    [
        ("displayp3", [0.000264159988, 0.006759031086, 0.032503755025]),
        ("adobergb", [-0.001117121394, 0.003334801682, 0.026917168783]),
    ],
)
def test_matrix_path_keeps_the_16_bit_gradient_and_wide_gamut(
    tmp_path: Path, profile: Literal["displayp3", "adobergb"], reference: list[float]
) -> None:
    source = tmp_path / "matrix.tif"
    icc = imagecodecs.cms_profile(profile)
    codes = np.repeat(np.arange(65536, dtype=np.uint16)[None, :, None], 3, axis=2)
    patches = np.array([[[1200, 4900, 12455], [65535, 0, 0], [0, 65535, 0]]], dtype=np.uint16)
    tifffile.imwrite(
        source, np.concatenate((codes, patches), axis=1), photometric="rgb", iccprofile=icc
    )
    with open_panel(source, keep_icc=True) as reader:
        color = resolve_photo_profile(reader, None, PhotoProfile())
        tile = reader.read_tile(Region(0, 0, 65539, 1))
    linear = color.decode(tile.pixels)
    assert linear.dtype == np.float32 and (np.diff(linear[0, :65536], axis=0) > 0).all()
    assert linear.min() < 0 < 1 < linear.max()
    np.testing.assert_allclose(linear[0, 65536], reference, atol=1.5e-4, rtol=0)


def test_assignment_precedence_and_saved_icc_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    grid = RenderSpec((120, -25), (16, 16), 4)
    path, assigned_path = tmp_path / "source.tiff", tmp_path / "Assigned.icc"
    pixels = np.tile(np.array([1200, 4900, 12455], dtype=np.uint16), (16, 16, 1))
    p3 = imagecodecs.cms_profile("displayp3")
    panel = _write(path, pixels, grid, icc=p3, exif_srgb=True)
    project = MosaicProject((panel,), grid)
    with pytest.raises(ValueError, match=r"source.tiff has conflicting ICC and EXIF"):
        preview_project(project, _JOB, allow_visual=True)

    assigned_path.write_bytes(imagecodecs.cms_profile("adobergb"))
    original, updated = tmp_path / "base.astromosaic", tmp_path / "photo.astromosaic"
    save_project(original, project)
    assert (
        main(
            [
                "project",
                "set-photo",
                str(original),
                "-o",
                str(updated),
                "--photo-profile",
                "display-p3",
                "--panel-profile",
                f"1={assigned_path}",
            ]
        )
        == 0
    )
    assert json.loads(updated.read_bytes())["panels"][0]["photo_profile"]["path"] == "Assigned.icc"
    reloaded = load_project(updated)
    preview = preview_project(reloaded, _JOB, allow_visual=True)
    assert preview.photo is not None and preview.photo.panels[0].color_origin == "panel_assignment"
    np.testing.assert_allclose(
        preview.tile.pixels[4, 4], [-0.001117121394, 0.003334801682, 0.026917168783], atol=1.5e-4
    )
    output = tmp_path / "photo.tiff"
    capsys.readouterr()
    assert main(["project", "export-photo", str(updated), "-o", str(output), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)["photo"]["panels"][0]
    np.testing.assert_array_equal(
        tifffile.imread(output)[..., :3], _encode(preview.tile.pixels.astype(np.float64))
    )
    assert report["profile_sha256"] == PhotoProfile.capture(assigned_path).digest
    assigned_path.write_bytes(p3)
    with pytest.raises(ValueError, match="assigned ICC file changed"):
        preview_project(reloaded, _JOB, allow_visual=True)
    with pytest.raises(ValueError, match="unsupported TIFF ICC profile"):
        render_project(
            replace(reloaded, assume_surface_brightness=True), tmp_path / "science.tiff", _JOB
        )


def test_exif_srgb_and_untagged_assumption(tmp_path: Path) -> None:
    grid = RenderSpec((120, -25), (8, 8), 4)
    pixels = np.full((8, 8, 3), 32768, np.uint16)
    tagged = _write(tmp_path / "exif.tif", pixels, grid, exif_srgb=True)
    untagged = _write(tmp_path / "unknown.tif", pixels, grid)
    project = MosaicProject((tagged, untagged), grid)
    with pytest.raises(ValueError, match=r"unknown.tif does not declare"):
        render_project_photo(project, tmp_path / "missing.tiff", _JOB, tone=None)
    assumed = replace(project, photo_settings=PhotoSettings(PhotoProfile("assume-srgb")))
    preview = preview_project(assumed, _JOB, allow_visual=True)
    assert preview.photo is not None
    assert [item.color_origin for item in preview.photo.panels] == [
        "exif_color_space",
        "assumption",
    ]
    with pytest.raises(ValueError, match="uses sRGB-encoded samples"):
        render_project(
            replace(project, assume_surface_brightness=True), tmp_path / "science.tif", _JOB
        )


def test_photo_cli_accepts_names_outside_the_console_encoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    grid = RenderSpec((120, -25), (8, 8), 4)
    pixels = np.full((8, 8, 3), 32768, np.uint16)
    panel = _write(tmp_path / "\u661f.tiff", pixels, grid, icc=_SRGB.read_bytes())
    manifest = tmp_path / "Project.astromosaic"
    save_project(manifest, MosaicProject((panel,), grid))
    destination, log = tmp_path / "Photo.tiff", tmp_path / "log.txt"
    with log.open("w", encoding="ascii") as stream, monkeypatch.context() as console:
        console.setattr(sys, "stdout", stream)
        assert main(["project", "export-photo", str(manifest), "-o", str(destination)]) == 0
    assert destination.is_file()
    assert r"\u661f.tiff: srgb" in log.read_text(encoding="ascii")


def test_exposure_metadata_requires_compatible_camera_and_iso() -> None:
    reference = CameraExposure(10, 4, 6400, "camera", "maker")
    for peer, gain in (
        (reference, 1),
        (replace(reference, seconds=5), 2),
        (replace(reference, f_number=8), 4),
    ):
        effective, detail = metadata_gain(reference, peer)
        assert effective == pytest.approx(gain) and detail == ""
    for peer, reason in (
        (replace(reference, iso=3200), "ISO differs"),
        (replace(reference, f_number=None), "aperture"),
        (replace(reference, camera="other"), "provenance"),
        (replace(reference, conflicting=True), "Conflicting"),
    ):
        effective, detail = metadata_gain(reference, peer)
        assert effective == 1 and reason in detail


def test_standard_fit_is_shared_saved_and_cancelable(tmp_path: Path) -> None:
    grid = RenderSpec((120, -25), (256, 192), 4)
    x, y = np.meshgrid(np.linspace(0, 1, 256), np.linspace(0, 1, 192))
    base = 0.008 + 0.02 * np.stack((x, y, (x + y) / 2), axis=-1)
    source = _write(tmp_path / "a.tif", _encode(base), grid, icc=_SRGB.read_bytes())
    peer = _write(tmp_path / "b.tif", _encode((base + 0.003) / 1.25), grid, icc=_SRGB.read_bytes())
    project = MosaicProject(
        (source, peer), grid, photo_settings=PhotoSettings(brightness="standard")
    )
    destination = tmp_path / "out.tiff"
    stages: list[str] = []
    job = JobContext(is_cancelled=lambda: bool(stages), on_stage=stages.append)
    with pytest.raises(MosaicCancelled):
        render_project_photo(project, destination, job, tone=None)
    assert stages == ["photo-overlap"] and not destination.exists()
    assert not list(tmp_path.glob("*.part"))
    stages.clear()
    job = JobContext(is_cancelled=lambda: "photo-stars" in stages, on_stage=stages.append)
    with pytest.raises(MosaicCancelled):
        render_project_photo(project, destination, job, tone=None)
    assert stages == ["photo-overlap", "photo-stars"] and not destination.exists()
    assert not list(tmp_path.glob("*.part"))

    preview = preview_project(project, _JOB, allow_visual=True)
    assert preview.photo is not None
    fit = preview.photo.panels[1].brightness
    assert fit.method == "offset-only" and fit.gain == 1
    assert fit.offset == pytest.approx(0.0012, abs=2e-4)
    assert fit.stellar_gain is not None and fit.stellar_gain.status == "insufficient"
    assert fit.stellar_gain.stars == 0
    assert fit.before_p95 is not None and fit.after_p95 is not None
    assert fit.after_p95 < fit.before_p95
    spec = replace(grid, crop=Region(51, 49, 96, 72))
    cropped = render_project_photo(project, destination, _JOB, tone=None, grid=spec)
    assert cropped.photo == preview.photo
    assert cropped.peak_reserved_bytes <= grid.max_working_bytes
    np.testing.assert_allclose(
        tifffile.imread(destination)[..., :3],
        _encode(preview.tile.pixels[49:121, 51:147].astype(np.float64)),
        atol=1,
    )
    reversed_preview = preview_project(
        replace(project, panels=(peer, source)), _JOB, allow_visual=True
    )
    assert reversed_preview.photo is not None
    assert reversed_preview.photo.reference_panel == 2
    assert reversed_preview.photo.panels[0].brightness == fit
