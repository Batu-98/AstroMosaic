"""Compare native GPU preview jobs against the CPU reference on real sky panels."""

import os
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from astromosaic.core import Region
from astromosaic.display import DisplayFrame
from astromosaic.storage.project import load_project

_DATA = Path(__file__).resolve().parents[2] / "data" / "application-tests"


def _compare(gpu: DisplayFrame, cpu: DisplayFrame) -> None:
    assert gpu.output_size == cpu.output_size and gpu.has_coverage
    assert gpu.tone_levels == cpu.tone_levels
    np.testing.assert_array_equal(gpu.rgba[..., 3], cpu.rgba[..., 3])
    np.testing.assert_allclose(gpu.rgba[..., :3], cpu.rgba[..., :3], atol=2e-7, rtol=0)


@pytest.mark.parametrize("manifest", ["sky01-m17-atlas/project", "owner01-pa4/pair-20-21"])
def test_real_sky_gpu_preview_and_detail(manifest: str) -> None:
    if os.environ.get("ASTROMOSAIC_TEST_OPENGL") != "1":
        pytest.skip("Set ASTROMOSAIC_TEST_OPENGL=1 on a native desktop with OpenGL 4.3.")
    pytest.importorskip("PySide6")
    path = _DATA / f"{manifest}.astromosaic"
    if not path.is_file():
        pytest.skip("Prepare the M17 and PA4 observational references in docs/phase-6.md.")

    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.mosaic_job import PreviewDetailJob, PreviewJob
    from astromosaic.ui.preview_state import PreviewSelection, PreviewState

    project = load_project(path)
    if not all(project.panels[index].source.path.is_file() for index in project.sky_indices()):
        pytest.skip("The referenced observation files are unavailable.")
    app = cast(QApplication | None, QApplication.instance()) or QApplication([])
    selection = PreviewSelection(project, "sky", None)
    frames = []
    details = []
    for use_gpu in (False, True):
        state = PreviewState()
        request = state.start(selection)
        job = PreviewJob(request, app, adaptive_edge=512, use_gpu=use_gpu)
        job.start()
        assert job.wait(90_000)
        assert job.result is not None, job.error
        assert job.gpu_sampled == use_gpu
        overview = state.complete(request, selection, job.result)
        assert overview is not None and overview.frame.has_coverage
        frames.append(overview.frame)

        width, height = overview.frame.output_size
        detail = PreviewDetailJob(
            overview, app, Region(width // 2 - 32, height // 2 - 32, 64, 64), use_gpu=use_gpu
        )
        detail.start()
        assert detail.wait(30_000)
        assert detail.result is not None, detail.error
        assert detail.gpu_sampled == use_gpu
        details.append(detail.result)
        job.deleteLater()
        detail.deleteLater()
        app.processEvents()

    _compare(frames[1], frames[0])
    _compare(details[1], details[0])
