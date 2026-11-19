"""Phase 6C checks on the frozen horizon observations and installed catalogs."""

import json
import os
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep
from typing import Any

import numpy as np
import pytest
from astropy.io import fits

from astromosaic.astrometry import solve
from astromosaic.astrometry.astap_catalog import CatalogCone, CatalogReadUsage, query_astap_cone
from astromosaic.astrometry.astap_probe import AstapCandidate
from astromosaic.astrometry.solve import CatalogRegionReport, SolveOptions, load_solution
from astromosaic.astrometry.solve_budget import SolveBudget
from astromosaic.astrometry.solve_validation import QualityRejected
from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.core.masks import SKY, UNCLASSIFIED, SourceMask
from astromosaic.storage.project import load_project, open_project_sky_panel, save_project

_ROOT = Path(__file__).resolve().parents[2]
_RUN = _ROOT / "output/application-tests/phase6c"
_PA4 = _ROOT / "data/application-tests/owner01-pa4/all-panels-unaligned.astromosaic"
_D50 = _ROOT / ".tooling/phase36-dense/d50"
_ASTAP = Path("C:/Program Files/astap")


def _require(*paths: Path) -> None:
    if not all(path.is_file() for path in paths):
        pytest.skip("Prepare the Phase 6C local real-observation references in docs/phase-6.md.")


def _seed(
    database: str, panel: int
) -> tuple[AstapCandidate, tuple[int, int], list[tuple[float, float, float]]]:
    path = _RUN / "native-candidates" / f"{database}-{panel:02d}.json"
    _require(path)
    data = json.loads(path.read_bytes())
    candidate = AstapCandidate(
        fits.Header.fromstring(data["wcs"], sep="\n"), data["version"], data["database"]
    )
    width, height = data["size"]
    detections = [(x, y, flux) for x, y, flux in data["detections"]]
    return candidate, (width, height), detections


@pytest.mark.parametrize(
    ("panel", "gate", "region_count"),
    [(3, "association", 41), (6, "held-out", 49), (7, "edge-support", 54)],
)
def test_dense_horizon_catalog_reaches_quality_gates(
    panel: int, gate: str, region_count: int
) -> None:
    _require(_D50 / "d50_0101.1476")
    candidate, size, detections = _seed("d50", panel)
    regions: list[CatalogRegionReport] = []
    budget = SolveBudget.begin(120)
    with pytest.raises(QualityRejected) as rejected:
        solve._validate_astap(
            candidate, _D50, size, detections, True, budget.context(JobContext()), regions
        )
    assert rejected.value.gate == gate and rejected.value.evidence is not None
    assert len(regions) == region_count
    assert all(region.outcome == "complete" and region.area_sq_deg > 0 for region in regions)
    assert sum(region.detected_stars for region in regions) == len(detections)
    assert sum(region.read_bytes for region in regions) <= 64 * 1024**2
    assert all(
        region.retained_stars <= max(30, 3 * region.detected_stars) <= 100_000
        and region.decoded_stars >= region.retained_stars
        for region in regions
    )


def test_early_filter_preserves_wide_catalog_solution(monkeypatch: pytest.MonkeyPatch) -> None:
    _require(_ASTAP / "d05_0101.1476")
    candidate, size, detections = _seed("d05", 7)
    filtered, quality = solve._validate_astap(
        candidate, _ASTAP, size, detections, False, JobContext()
    )

    def read_full_cone(*args: Any, **kwargs: Any) -> CatalogCone:
        kwargs["selection"] = None
        return query_astap_cone(*args, **kwargs)

    monkeypatch.setattr(solve, "query_astap_cone", read_full_cone)
    complete, reference = solve._validate_astap(
        candidate, _ASTAP, size, detections, False, JobContext()
    )
    assert filtered == complete
    assert quality["unique_matches"] == reference["unique_matches"] == 292
    assert quality["chance_control_matches"] == reference["chance_control_matches"]
    assert quality["measured_regions"] == reference["measured_regions"]
    filtered_bytes, full_bytes = quality["catalog_read_bytes"], reference["catalog_read_bytes"]
    assert isinstance(filtered_bytes, int) and isinstance(full_bytes, int)
    assert filtered_bytes < full_bytes


def test_real_catalog_scan_cancels_and_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    _require(_D50 / "d50_0101.1476")
    candidate, size, detections = _seed("d50", 7)
    reads: list[CatalogReadUsage] = []
    partial: list[CatalogRegionReport] = []

    def track_real_reads(*args: Any, **kwargs: Any) -> CatalogCone:
        reads.append(kwargs["usage"])
        return query_astap_cone(*args, **kwargs)

    with monkeypatch.context() as temporary:
        temporary.setattr(solve, "query_astap_cone", track_real_reads)
        with pytest.raises(MosaicCancelled):
            solve._validate_astap(
                candidate,
                _D50,
                size,
                detections,
                True,
                JobContext(is_cancelled=lambda: bool(reads) and reads[-1].read_bytes >= 20_480),
                partial,
            )
    assert len(partial) == 1 and partial[0].outcome == "interrupted"
    assert partial[0].decoded_stars > 0 and partial[0].read_bytes >= 20_480

    with pytest.raises(QualityRejected) as retry:
        solve._validate_astap(candidate, _D50, size, detections, True, JobContext())
    assert retry.value.gate == "edge-support"


def test_real_sidecar_reports_and_sky_mask_revision(tmp_path: Path) -> None:
    path = _RUN / "replays/installed-07-d05.wcs.json"
    _require(_PA4, path)
    panel = load_project(_PA4).panels[6]
    quality, attempts = solve.read_solution_diagnostics(path)
    assert quality["unique_matches"] == 292 and attempts[-1]["catalog"] == "d05"

    record = json.loads(path.read_bytes())
    record["version"] = 1
    record.pop("quality")
    legacy = tmp_path / "legacy.wcs.json"
    legacy.write_text(json.dumps(record), encoding="utf-8")
    assert solve.read_solution_quality(legacy) == {"grade": "geometry-only"}
    with open_project_sky_panel(panel, 128 * 1024**2, JobContext()) as source:
        current, _ = load_solution(path, source)
        old, _ = load_solution(legacy, source)
        assert current.wcs.to_header() == old.wcs.to_header()

    mask = panel.source_mask
    assert mask is not None
    labels = mask.grid().copy()
    row, column = np.argwhere(labels == SKY)[0]
    labels[row, column] = UNCLASSIFIED
    changed = replace(panel, source_mask=SourceMask(mask.source_size, labels.tobytes()))
    with (
        open_project_sky_panel(changed, 128 * 1024**2, JobContext()) as source,
        pytest.raises(ValueError, match="different input or sky mask revision"),
    ):
        load_solution(path, source)


def test_desktop_details_open_for_a_rejected_real_solution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _require(_PA4, _ASTAP / "astap_cli.exe", _D50 / "d50_0101.1476")
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings, QTimer
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.mosaic_job import PlateSolveJob
    from astromosaic.ui.plate_solve_details import PlateSolveDetails
    from astromosaic.ui.project_window import ProjectWindow

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance()
    app = instance if isinstance(instance, QApplication) else QApplication([])
    window = ProjectWindow(
        use_gpu=False,
        preferences=QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat),
    )
    secondary = next((screen for screen in app.screens() if screen != app.primaryScreen()), None)
    if secondary is not None:
        window.move(secondary.availableGeometry().center() - window.rect().center())
    project = load_project(_PA4)
    project = replace(project, panels=(project.panels[6],))
    manifest = tmp_path / "horizon.astromosaic"
    save_project(manifest, project)
    options = SolveOptions(
        astap=_ASTAP / "astap_cli.exe",
        astap_catalog=_D50,
        astap_database="d50",
        timeout_seconds=12,
        total_seconds=55,
        max_working_bytes=128 * 1024**2,
        strict_edges=True,
    )
    evidence: list[tuple[str, int]] = []

    def inspect_details() -> None:
        dialog = app.activeModalWidget()
        if isinstance(dialog, PlateSolveDetails):
            evidence.append((dialog.attempt_detail.text(), dialog.catalog_table.rowCount()))
            dialog.reject()

    try:
        window._set_project(project, manifest)
        window.show()
        window._launch_job(PlateSolveJob(project, options, tmp_path / "wcs", window), "Solving…")
        deadline = monotonic() + 60
        while window.job is not None and monotonic() < deadline:
            app.processEvents()
            sleep(0.01)
        assert window.job is None and window.solve_details_action.isEnabled()
        assert window.project.panels[0].wcs_sidecar is None
        QTimer.singleShot(0, inspect_details)
        window.solve_details_action.trigger()
        assert len(evidence) == 1
        summary, regions = evidence[0]
        assert "Field-edge support" in summary and "Held-out edge stars 19" in summary
        assert "Catalog d50" in summary and "Scale " in summary and regions == 54
    finally:
        window.close()
        app.processEvents()
