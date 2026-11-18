"""Publish a complete file after flushing its temporary copy."""

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import IO


@contextmanager
def atomic_binary_file(
    path: Path,
    *,
    replace_existing: bool = False,
    publish_check: Callable[[], None] | None = None,
) -> Iterator[IO[bytes]]:
    path = path.absolute()
    if not replace_existing and (path.exists() or path.is_symlink()):
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

        if publish_check is not None:
            if replace_existing:
                raise ValueError("A guarded publish requires a new output path.")
            identity = temporary.stat()
            publish_check()
        if replace_existing:
            temporary.replace(path)
        elif os.name == "nt":
            # Windows rename rejects an existing destination.
            temporary.rename(path)
        else:
            os.link(temporary, path)
        if publish_check is not None:
            try:
                publish_check()
            except BaseException:
                if path.exists() and os.path.samestat(identity, path.stat()):
                    path.unlink()
                raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
