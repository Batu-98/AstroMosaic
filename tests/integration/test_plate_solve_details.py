import os

import pytest


def test_measured_error_view_distinguishes_missing_stars_from_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QWidget

    from astromosaic.ui.plate_solve_details import PlateSolveDetails

    if "QT_QPA_PLATFORM" not in os.environ:
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    parent = QWidget()
    quality = {
        "model": "SIP-3",
        "unique_matches": 25,
        "rms_arcsec": 1.2,
        "edge_status": "insufficient",
        "field_geometry": {
            "model_grid": [{"model_displacement_source_px": 2.0, "model_vector_source_px": [0, 2]}]
            * 81,
        },
        "measured_regions": [
            {"matches": 0, "support": "insufficient"},
            {"matches": 7, "p95_source_px": 0.0, "support": "measured"},
            *([{}] * 79),
        ],
    }
    dialog = PlateSolveDetails(quality, parent)
    try:
        dialog.show()
        app.processEvents()
        model = dialog.grid.item(0, 0)
        assert model is not None and model.text() == "2.00"
        assert "Δy +2.000" in model.toolTip()
        dialog.mode.setCurrentIndex(1)
        unsupported, measured = dialog.grid.item(0, 0), dialog.grid.item(0, 1)
        assert unsupported is not None and unsupported.text() == "—"
        assert measured is not None and measured.text() == "0.00"
    finally:
        dialog.close()
        parent.deleteLater()
        app.processEvents()
