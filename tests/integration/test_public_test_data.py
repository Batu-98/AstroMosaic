"""Protect original public observations from partial or mismatched downloads."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest

from tools import public_test_data


def _entry(payload: bytes) -> public_test_data.ObservationFile:
    return dict(
        name="sample.fits",
        url="https://example.invalid/sample.fits",
        size_bytes=len(payload),
        sha256=sha256(payload).hexdigest(),
    )


def test_mismatched_download_leaves_no_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = _entry(b"expected")
    destination = tmp_path / entry["name"]
    monkeypatch.setattr(public_test_data, "urlopen", lambda url, *, timeout: BytesIO(b"damaged!"))

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        public_test_data.check_file(entry, destination, fetch=True)

    assert not list(tmp_path.iterdir())


def test_fetch_preserves_existing_file_with_different_hash(tmp_path: Path) -> None:
    entry = _entry(b"expected")
    destination = tmp_path / entry["name"]
    destination.write_bytes(b"original")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        public_test_data.check_file(entry, destination, fetch=True)

    assert destination.read_bytes() == b"original"
