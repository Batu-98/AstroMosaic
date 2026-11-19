"""Phase 6 foreground regressions on independently exposed observations."""

import json
import os
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

import numpy as np
import pytest

from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.core.masks import FOREGROUND, UNCLASSIFIED, SourceMask
from astromosaic.pipeline.foreground import ForegroundAlignmentRejected, ForegroundPairDiagnostic
from astromosaic.storage.project import align_project_foreground, load_project, save_project

_ROOT = Path(__file__).resolve().parents[2]
_ALPACA = _ROOT / "data/application-tests/phase6a-alpaca"
_PA4 = _ROOT / "data/application-tests/owner01-pa4/foreground-check.astromosaic"
_PA4_BASELINE = (
    _ROOT / "output/application-tests/phase6a-20261119-155643-651/pa4-foreground-pairs.json"
)


def _require(*paths: Path) -> None:
    if not all(path.is_file() for path in paths):
        pytest.skip("Prepare the local real-observation references from docs/phase-6.md.")


def test_pa4_pair_diagnostics_match_frozen_replay() -> None:
    _require(_PA4, _PA4_BASELINE)
    project = load_project(_PA4)
    baseline = json.loads(_PA4_BASELINE.read_bytes())["pairs"]
    measured: list[ForegroundPairDiagnostic] = []

    with pytest.raises(ForegroundAlignmentRejected) as failure:
        align_project_foreground(project, JobContext(), on_pair=measured.append)

    assert failure.value.stage == "disconnected"
    assert failure.value.groups == tuple((i,) for i in range(6))
    assert len(measured) == 15
    for pair, reference in zip(measured, baseline, strict=True):
        assert [f"{int(project.panels[i].source.path.stem):02}" for i in pair.panels] == reference[
            "panels"
        ]
        assert pair.stage == "correlation"
        assert pair.thumbnail.usable_samples == tuple(reference["eligible_samples"])
        assert pair.thumbnail.shared_threshold == reference["minimum_shared_samples"]
        assert pair.thumbnail.peak_shared_samples == reference["peak_shared_samples"]
        assert pair.thumbnail.peak == pytest.approx(reference["peak_correlation"], abs=1e-6)
        assert pair.thumbnail.competing_peak is None and pair.refinement is None


def test_real_translation_collects_patch_evidence_and_retries() -> None:
    path = _ALPACA / "positive.astromosaic"
    _require(path, _ALPACA / "reference.json")
    project = load_project(path)
    reference = json.loads((_ALPACA / "reference.json").read_bytes())
    interrupted: list[ForegroundPairDiagnostic] = []

    with pytest.raises(MosaicCancelled):
        align_project_foreground(
            project,
            JobContext(is_cancelled=lambda: bool(interrupted)),
            on_pair=interrupted.append,
        )

    retry: list[ForegroundPairDiagnostic] = []
    result = align_project_foreground(project, JobContext(), on_pair=retry.append)
    assert retry == interrupted and len(retry) == 1
    pair = retry[0]
    alignment = result.current_foreground()
    assert alignment is not None and pair.stage == "accepted"
    assert pair.thumbnail.peak is not None and pair.thumbnail.competing_peak is not None
    assert pair.thumbnail.peak - pair.thumbnail.competing_peak >= 0.06
    assert pair.refinement is not None
    assert pair.refinement.shift == alignment.panels[1].shift
    assert pair.refinement.agreeing_patches == alignment.overlaps[0].patches == 3
    np.testing.assert_allclose(
        alignment.panels[1].shift,
        reference["expected_positive_shift_xy"],
        atol=reference["absolute_tolerance_px_per_axis"],
        rtol=0,
    )


def test_real_disconnected_and_low_support_masks(tmp_path: Path) -> None:
    path = _ALPACA / "negative.astromosaic"
    _require(path)
    project = load_project(path)
    diagnostics: list[ForegroundPairDiagnostic] = []
    with pytest.raises(ForegroundAlignmentRejected) as failure:
        align_project_foreground(project, JobContext(), on_pair=diagnostics.append)
    assert failure.value.groups == ((0,), (1,))
    assert diagnostics[0].stage == "correlation"

    panel = project.panels[1]
    mask = panel.source_mask
    assert mask is not None
    labels = np.full_like(mask.grid(), UNCLASSIFIED)
    ground_cells = np.argwhere(mask.grid() == FOREGROUND)
    row, col = ground_cells[len(ground_cells) // 2]
    labels[row, col] = FOREGROUND
    reduced = SourceMask(mask.source_size, labels.tobytes())
    edited = replace(project, panels=(project.panels[0], replace(panel, source_mask=reduced)))
    saved = tmp_path / "reduced-mask.astromosaic"
    save_project(saved, edited)
    reopened = load_project(saved)
    assert reopened.panels[1].source_mask == reduced

    reduced_diagnostics: list[ForegroundPairDiagnostic] = []
    with pytest.raises(ForegroundAlignmentRejected) as failure:
        align_project_foreground(reopened, JobContext(), on_pair=reduced_diagnostics.append)
    assert failure.value.groups == ((0,), (1,))
    assert reduced_diagnostics[0].stage == "support"
    assert reduced_diagnostics[0].thumbnail.usable_samples[1] < 24


def test_desktop_details_open_the_selected_real_mask(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _ALPACA / "negative.astromosaic"
    _require(path)
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings, QTimer
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.foreground_details import ForegroundAlignmentDetails
    from astromosaic.ui.mask_editor import MaskEditor
    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance()
    app = instance if isinstance(instance, QApplication) else QApplication([])
    window = ProjectWindow(
        use_gpu=os.environ.get("ASTROMOSAIC_TEST_OPENGL") == "1",
        preferences=QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat),
    )
    secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
    if secondary is not None:
        window.move(secondary.availableGeometry().center() - window.rect().center())

    deadline = monotonic() + 15
    callbacks: list[str] = []

    def open_second_mask() -> None:
        dialog = app.activeModalWidget()
        if isinstance(dialog, ForegroundAlignmentDetails):
            rows = dialog.model.rowCount()
            name = dialog.model.index(0, 1).data()
            stage = dialog.model.index(0, 2).data()
            callbacks.append(f"{rows} | {name} | {stage}")
            dialog.mask_b.click()
            if dialog.isVisible():
                dialog.reject()

    def close_mask() -> None:
        dialog = app.activeModalWidget()
        if isinstance(dialog, MaskEditor):
            callbacks.append(dialog.windowTitle())
            dialog.reject()
        elif monotonic() < deadline:
            QTimer.singleShot(10, close_mask)

    try:
        window._set_project(load_project(path), path)
        window.show()
        window.align_action.trigger()
        while window.job is not None and monotonic() < deadline:
            app.processEvents()
            sleep(0.01)
        assert window.job is None and window.foreground_details_action.isEnabled()
        assert "Panel groups 1 | 2." in window.status.text()
        QTimer.singleShot(0, open_second_mask)
        window.foreground_details_action.trigger()
        assert window.panels.currentIndex().row() == 1
        QTimer.singleShot(0, close_mask)
        while len(callbacks) < 2 and monotonic() < deadline:
            app.processEvents()
            sleep(0.01)
        assert callbacks[0] == "1 | 2. C.fits | Low correlation"
        assert "C.fits" in callbacks[1]
    finally:
        window.close()
        app.processEvents()
