"""Publish a complete new file without clobbering another writer's output."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import IO


@contextmanager
def atomic_binary_file(path: Path) -> Iterator[IO[bytes]]:
    path = path.absolute()
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"The output file already exists: {path}")
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w+b", dir=path.parent, prefix=".astromosaic-", suffix=".part", delete=False
        ) as stream:
            temporary = Path(stream.name)
            yield stream
            stream.flush()
            os.fsync(stream.fileno())

        if os.name == "nt":
            # Windows rename rejects an existing destination.
            temporary.rename(path)
        else:
            os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
