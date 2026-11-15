import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import sep

from astromosaic.cli import main
from astromosaic.pipeline.smoke import write_smoke_panel


def test_inspect_and_error_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "panel with spaces.fits"
    write_smoke_panel(path)
    assert main(["inspect", str(path)]) == 0
    metadata = json.loads(capsys.readouterr().out)
    assert metadata["width"] == 16
    assert metadata["unit"] == "MJy/sr"

    assert main(["inspect", str(tmp_path / "missing.fits")]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "astromosaic:" in output.err


def test_module_cli_spawn_smoke() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "astromosaic", "smoke", "--spawn"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert json.loads(result.stdout) == {
        "backend": "cpu",
        "spawned": True,
        "width": 5,
        "height": 4,
        "valid_pixels": 19,
        "min_pixel": -4,
        "max_pixel": 4,
    }


def test_engine_runs_with_qt_imports_blocked() -> None:
    script = """
import sys

class BlockQt:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'PySide6', 'PyQt6', 'PySide2', 'PyQt5'}:
            raise AssertionError(f'Unexpected Qt import: {fullname}')

sys.meta_path.insert(0, BlockQt())
from astromosaic.cli import main
raise SystemExit(main(['smoke']))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert json.loads(result.stdout)["valid_pixels"] == 19


def test_compiled_dependency_paths_and_sep_aperture() -> None:
    for module in ("numpy", "scipy.ndimage", "astropy.wcs", "sep", "reproject"):
        assert importlib.util.find_spec(module) is not None
    data = np.zeros((11, 11), dtype=np.float32)
    data[5, 5] = 3.25
    flux, _, flags = sep.sum_circle(data, [5.0], [5.0], 2.0)
    np.testing.assert_array_equal(flux, [3.25])
    np.testing.assert_array_equal(flags, [0])
