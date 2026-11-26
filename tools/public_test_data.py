"""Verify public observation files and optionally fetch the missing originals."""

from __future__ import annotations

import argparse
import json
import sys
from hashlib import file_digest, sha256
from pathlib import Path
from typing import TypedDict, cast
from urllib.request import urlopen

from astromosaic.io.atomic import atomic_binary_file

_DEFAULT_ROOT = Path("data/public-test-data")
_MANIFEST = Path(__file__).resolve().parents[1] / "tests/fixtures/public_test_data.json"
_CHUNK_SIZE = 1024**2


class ObservationFile(TypedDict):
    name: str
    url: str
    size_bytes: int
    sha256: str


class Dataset(TypedDict):
    id: str
    source_page: str
    credit: str
    usage: str
    files: list[ObservationFile]


def _destination(root: Path, dataset: str, name: str) -> Path:
    for component in (dataset, name):
        if Path(component).name != component or component in {"", ".", ".."}:
            raise ValueError(f"Invalid manifest path component: {component!r}")
    path = root / dataset / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"File path leaves the data directory: {path}")
    return path


def _check(entry: ObservationFile, size: int, checksum: str) -> None:
    if size != entry["size_bytes"]:
        raise ValueError(f"Unexpected size for {entry['name']}: {size} bytes.")
    if checksum != entry["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {entry['name']}.")


def _fetch(entry: ObservationFile, path: Path) -> None:
    digest = sha256()
    size = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(entry["url"], timeout=45) as source, atomic_binary_file(path) as output:
        while chunk := source.read(_CHUNK_SIZE):
            size += len(chunk)
            if size > entry["size_bytes"]:
                raise ValueError(f"Download exceeds the recorded size for {entry['name']}.")
            digest.update(chunk)
            output.write(chunk)
        _check(entry, size, digest.hexdigest())


def check_file(entry: ObservationFile, path: Path, *, fetch: bool = False) -> None:
    if not path.exists() and fetch:
        _fetch(entry, path)
        return
    size = path.stat().st_size
    with path.open("rb") as stream:
        _check(entry, size, file_digest(stream, "sha256").hexdigest())


def main() -> int:
    manifest = json.loads(_MANIFEST.read_bytes())
    if manifest["schema_version"] != 1:
        raise ValueError("Unsupported public test data manifest version.")
    datasets = cast(list[Dataset], manifest["datasets"])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_DEFAULT_ROOT)
    parser.add_argument("--dataset", action="append", choices=[d["id"] for d in datasets])
    parser.add_argument("--fetch", action="store_true", help="Download missing originals.")
    options = parser.parse_args()
    verified = 0
    failed = 0
    size = 0
    for dataset in datasets:
        if options.dataset and dataset["id"] not in options.dataset:
            continue
        for entry in dataset["files"]:
            try:
                path = _destination(options.root, dataset["id"], entry["name"])
                check_file(entry, path, fetch=options.fetch)
            except (OSError, ValueError) as error:
                print(error, file=sys.stderr, flush=True)
                failed += 1
            else:
                print(f"Verified {dataset['id']}/{entry['name']}", flush=True)
                verified += 1
                size += entry["size_bytes"]
    print(f"Verified {verified} files ({size / 1024**3:.2f} GiB). Failed {failed}.")
    return int(failed != 0)


if __name__ == "__main__":
    raise SystemExit(main())
