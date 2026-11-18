from pathlib import Path

import pytest

from astromosaic.astrometry.astap_catalog import _cone_tiles, query_astap_cone
from astromosaic.core.job import JobContext, MosaicCancelled


def _tile(path: Path, records: bytes, *, epoch: int = 2025) -> None:
    description = f"GAIA DR3, density<=500 stars/sqr(degree), Epoch={epoch}."
    path.write_bytes(description.encode("ascii").ljust(109, b" ") + b"\x05" + records)


# HNSKY's documented Sirius example is RA C3 06 48 and DEC D7 39 E8.
# The five-byte format moves DEC's signed high byte into a section marker.
_SIRIUS = bytes.fromhex("ff ff ff 68 06 c3 06 48 d7 39")


def test_real_format_example_has_signed_declination_magnitude_and_stable_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "d05_1519.1476"
    _tile(path, _SIRIUS)
    original = path.read_bytes()
    result = query_astap_cone(tmp_path, "d05", (101.28715, -16.7161), 0.1)
    assert len(result.stars) == 1
    star = result.stars[0]
    assert star.ra_deg == pytest.approx(101.28715, abs=0.00003)
    assert star.dec_deg == pytest.approx(-16.7161401, abs=0.00000003)
    assert star.magnitude == -1.0
    assert star.identifier == "d05_1519.1476:115"
    assert result.epoch_year == 2025
    assert result.read_bytes == len(original)
    assert result.tiles == (path.name,)
    assert query_astap_cone(tmp_path, "d05", (101.28715, -16.7161), 0.000001).stars == ()
    assert path.read_bytes() == original


def test_cone_bounds_include_wrap_equator_and_poles() -> None:
    assert set(_cone_tiles((0.0, 0.0), 0.01)) == {
        "1801.1476",
        "1869.1476",
        "1901.1476",
        "1969.1476",
    }
    assert _cone_tiles((180.0, 89.9), 0.3) == ("3601.1476",)
    assert _cone_tiles((180.0, -89.9), 0.3) == ("0101.1476",)


@pytest.mark.parametrize("records", [_SIRIUS[:-1], _SIRIUS[5:]])
def test_truncated_or_unsectioned_records_are_rejected(tmp_path: Path, records: bytes) -> None:
    _tile(tmp_path / "d05_1519.1476", records)
    with pytest.raises(ValueError, match="length|precedes"):
        query_astap_cone(tmp_path, "d05", (101.28715, -16.7161), 0.1)


def test_missing_tiles_budgets_and_cancellation_do_not_return_partial_results(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="Missing ASTAP"):
        query_astap_cone(tmp_path, "d05", (101.28715, -16.7161), 0.1)
    _tile(tmp_path / "d05_1519.1476", _SIRIUS + _SIRIUS)
    with pytest.raises(ValueError, match="read byte budget"):
        query_astap_cone(tmp_path, "d05", (101.28715, -16.7161), 0.1, max_read_bytes=1)
    with pytest.raises(ValueError, match="retained star budget"):
        query_astap_cone(tmp_path, "d05", (101.28715, -16.7161), 0.1, max_stars=1)
    with pytest.raises(MosaicCancelled):
        query_astap_cone(
            tmp_path,
            "d05",
            (101.28715, -16.7161),
            0.1,
            context=JobContext(is_cancelled=lambda: True),
        )


def test_catalog_density_and_epoch_must_match(tmp_path: Path) -> None:
    for tile in _cone_tiles((0.0, 0.0), 0.01):
        _tile(tmp_path / f"d05_{tile}", _SIRIUS, epoch=2025)
    _tile(tmp_path / "d05_1969.1476", _SIRIUS, epoch=2024)
    with pytest.raises(ValueError, match="inconsistent catalog epochs"):
        query_astap_cone(tmp_path, "d05", (0.0, 0.0), 0.01)
    _tile(tmp_path / "d20_1519.1476", _SIRIUS)
    with pytest.raises(ValueError, match="density or epoch"):
        query_astap_cone(tmp_path, "d20", (101.28715, -16.7161), 0.1)


def test_section_state_crosses_blocks_and_cancellation_is_checked_per_block(tmp_path: Path) -> None:
    records = _SIRIUS + _SIRIUS[5:] * 4095
    _tile(tmp_path / "d05_1519.1476", records)
    result = query_astap_cone(tmp_path, "d05", (101.28715, -16.7161), 0.1)
    assert len(result.stars) == 4096
    assert result.stars[-1].identifier.endswith(":20590")
    assert result.stars[-1].magnitude == -1.0
    checks = 0

    def cancelled() -> bool:
        nonlocal checks
        checks += 1
        return checks == 4

    with pytest.raises(MosaicCancelled):
        query_astap_cone(
            tmp_path,
            "d05",
            (101.28715, -16.7161),
            0.1,
            context=JobContext(is_cancelled=cancelled),
        )


@pytest.mark.parametrize(
    ("center", "radius"),
    [((360.0, 0.0), 1.0), ((0.0, float("nan")), 1.0), ((0.0, 0.0), 0.0), ((0.0, 0.0), 11.0)],
)
def test_invalid_cones_fail_before_file_access(
    tmp_path: Path,
    center: tuple[float, float],
    radius: float,
) -> None:
    with pytest.raises(ValueError, match="cone center|validation radius"):
        query_astap_cone(tmp_path, "d05", center, radius)
