"""Fixtures for dispatch tests with dummy solver processes and small images."""

import numpy as np
import pytest
from astropy.io import fits

from astromosaic.astrometry import solve
from astromosaic.astrometry.astap_probe import AstapSetup
from astromosaic.astrometry.stars import Star, StarField


@pytest.fixture
def stub_solve_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep workflow tests focused on dispatch, masking, publication and reuse."""
    field = StarField(tuple(Star(float(i), 4.0, 10.0, 2.0) for i in range(20)), np.empty((0, 2)))
    monkeypatch.setattr(solve, "measure_stars", lambda *args: field)
    monkeypatch.setattr(
        solve,
        "check_astap_setup",
        lambda *args: AstapSetup("CLI-test", ("d05",), "auto", "Native Automatic"),
    )
    quality = {
        "grade": "catalog-validated",
        "model": "TAN",
        "unique_matches": 20,
        "rms_arcsec": 0.3,
    }
    monkeypatch.setattr(
        solve, "_validate_astap", lambda candidate, *args: (candidate.header, quality)
    )
    monkeypatch.setattr(
        solve,
        "validate_gaia",
        lambda candidate, *args: (fits.Header.fromstring(candidate.header, sep="\n"), quality),
    )
