import json
from dataclasses import replace
from pathlib import Path

import pytest

from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.pipeline.refinement import RefinementSpec
from astromosaic.pipeline.smoke import write_smoke_panel
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    load_project,
    render_project,
    save_project,
)


def test_project_manifest_reopens_with_settings_and_relocates_with_its_files(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original"
    original.mkdir()
    source = original / "Gökyüzü.fits"
    write_smoke_panel(source)
    mask = original / "mask.fits"
    mask.write_bytes(b"mask placeholder")
    wcs = original / "panel.wcs.json"
    wcs.write_text('{"version": 1, "stage": "gaia-dr3"}', encoding="utf-8")
    panel = ProjectPanel(
        FileReference.capture(source), 0.75, FileReference.capture(mask), FileReference.capture(wcs)
    )
    spec = RenderSpec((359.999, 20.0), (13, 11), 7.2, 23, Region(1, 2, 8, 6), 3)
    project = MosaicProject((panel,), spec, "L", True, RefinementSpec(4.0, "plane"))
    path = original / "Night.astromosaic"
    save_project(path, project)
    assert load_project(path) == project
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 2
    assert data["panels"][0]["source"]["path"] == source.name
    relocated = original.rename(tmp_path / "relocated")
    reopened = load_project(relocated / path.name)
    assert reopened.render == spec
    assert all(
        ref.path.parent == relocated and ref.status() == "Ready"
        for _, ref in reopened.panels[0].references()
    )
    legacy = relocated / "legacy.astromosaic"
    data["version"] = 1
    for record in data["panels"]:
        for key in ("foreground_suggestion", "foreground_override", "source_mask"):
            del record[key]
    legacy.write_text(json.dumps(data), encoding="utf-8")
    assert load_project(legacy) == reopened


def test_relink_requires_saved_fingerprint_and_changes_are_checked_before_render(
    tmp_path: Path,
) -> None:
    source = tmp_path / "light.fits"
    write_smoke_panel(source)
    project = MosaicProject((ProjectPanel(FileReference.capture(source)),))
    moved = source.rename(tmp_path / "renamed.fits")
    assert project.panels[0].source.status() == "Missing"
    output = tmp_path / "mosaic.tiff"
    with pytest.raises(ValueError, match="Source file is missing"):
        render_project(project, output, JobContext())
    wrong = tmp_path / "wrong.fits"
    wrong.write_bytes(b"not the source")
    with pytest.raises(ValueError, match="differs from the saved reference"):
        project.relink_panel(0, wrong)
    relinked = project.relink_panel(0, moved)
    assert relinked.panels[0].source.status() == "Ready"
    with moved.open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="Source file is changed"):
        render_project(relinked, output, JobContext())
    assert not output.exists()


def test_replacing_project_is_atomic_when_publication_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "project.astromosaic"
    project = MosaicProject()
    save_project(path, project)
    candidate = replace(project, filter_name="RGB")
    with pytest.raises(FileExistsError):
        save_project(path, candidate)

    def fail(_temporary: Path, _target: Path) -> Path:
        raise PermissionError("Publication failed")

    with monkeypatch.context() as patch:
        patch.setattr(type(path), "replace", fail)
        with pytest.raises(PermissionError, match="Publication failed"):
            save_project(path, candidate, replace_existing=True)
    assert load_project(path) == project
    assert not list(tmp_path.glob("*.part"))
    save_project(path, candidate, replace_existing=True)
    assert load_project(path) == candidate


@pytest.mark.parametrize(("field", "value"), [("version", 99), ("panels", {}), ("render", [])])
def test_invalid_project_is_rejected(tmp_path: Path, field: str, value: object) -> None:
    path = tmp_path / "project.astromosaic"
    save_project(path, MosaicProject())
    data = json.loads(path.read_text(encoding="utf-8"))
    data[field] = value
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid project manifest"):
        load_project(path)
