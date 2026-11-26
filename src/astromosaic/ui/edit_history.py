"""Qt-free history of immutable desktop project and draft values."""

from collections.abc import Iterable
from dataclasses import fields, is_dataclass
from pathlib import PurePath
from sys import getsizeof

HISTORY_STEPS = 100
HISTORY_BYTES = 8 * 1024**2


def _children(value: object) -> Iterable[object]:
    if isinstance(value, (tuple, frozenset)):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return (getattr(value, field.name) for field in fields(value))
    return ()


def _size(value: object) -> int:
    # Paths also retain their spelling. Charge it without depending on pathlib internals.
    return getsizeof(value) + (getsizeof(str(value)) if isinstance(value, PurePath) else 0)


class EditHistory[Value]:
    def __init__(
        self, value: Value, *, max_steps: int = HISTORY_STEPS, max_bytes: int = HISTORY_BYTES
    ) -> None:
        self._max_steps = max_steps
        self._max_bytes = max_bytes
        self._revisions: list[tuple[Value, str | None]] = [(value, None)]
        self._cursor = 0
        self._references: dict[int, int] = {}
        self._bytes = 0
        self.limit_reached = False
        self._retain(self._revisions[0])

    @property
    def steps(self) -> int:
        return len(self._revisions) - 1

    @property
    def retained_bytes(self) -> int:
        return self._bytes

    @property
    def value(self) -> Value:
        return self._revisions[self._cursor][0]

    @property
    def undo_label(self) -> str | None:
        return self._revisions[self._cursor][1]

    @property
    def redo_label(self) -> str | None:
        index = self._cursor + 1
        return self._revisions[index][1] if index < len(self._revisions) else None

    def commit(self, value: Value, label: str) -> bool:
        if value == self.value:
            return False
        for revision in self._revisions[self._cursor + 1 :]:
            self._release(revision)
        del self._revisions[self._cursor + 1 :]
        revision = (value, label)
        self._revisions.append(revision)
        self._retain(revision)
        self._cursor += 1
        self._trim()
        return True

    def complete_edit(self, started: Value, value: Value) -> bool:
        """Replace the current result of an edit that finishes asynchronously."""
        if self.value is not started or value == started or self.redo_label is not None:
            return False
        previous = self._revisions[self._cursor]
        revision = (value, previous[1])
        self._retain(revision)
        self._release(previous)
        self._revisions[self._cursor] = revision
        if self.steps:
            self._trim()
        return True

    def undo(self) -> str | None:
        label = self.undo_label
        if label is not None:
            self._cursor -= 1
        return label

    def redo(self) -> str | None:
        label = self.redo_label
        if label is not None:
            self._cursor += 1
        return label

    def _retain(self, value: object) -> None:
        key = id(value)
        count = self._references.get(key, 0)
        self._references[key] = count + 1
        if count == 0:
            self._bytes += _size(value)
            for child in _children(value):
                self._retain(child)

    def _release(self, value: object) -> None:
        key = id(value)
        count = self._references[key]
        if count == 1:
            del self._references[key]
            self._bytes -= _size(value)
            for child in _children(value):
                self._release(child)
        else:
            self._references[key] = count - 1

    def _trim(self) -> None:
        while self.steps and (self.steps > self._max_steps or self._bytes > self._max_bytes):
            self._release(self._revisions.pop(0))
            self._cursor -= 1
            previous = self._revisions[0]
            baseline = (previous[0], None)
            self._retain(baseline)
            self._release(previous)
            self._revisions[0] = baseline
        # A large change can leave only the new active value in memory.
        self.limit_reached = self.steps == 0
