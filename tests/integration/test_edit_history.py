from dataclasses import dataclass, replace

from astromosaic.ui.edit_history import EditHistory


@dataclass(frozen=True, slots=True)
class _Edit:
    label: int
    mask: bytes


def test_history_evicts_oldest_step_and_releases_a_replaced_branch() -> None:
    initial = _Edit(0, b"sky")
    history = EditHistory(initial, max_steps=2)
    values = [replace(initial, label=label) for label in range(1, 5)]
    for value in values:
        assert history.commit(value, "Change")
    assert history.steps == 2
    assert history.undo() == history.undo() == "Change"
    assert history.value == values[1] and history.undo() is None
    assert history.redo() == "Change"
    assert not history.commit(history.value, "Same") and history.redo_label == "Change"
    assert history.commit(replace(initial, label=5), "Branch")
    assert history.steps == 2 and history.redo() is None
    assert history.undo() == "Branch" and history.value == values[2]


def test_history_counts_shared_payloads_and_reports_a_single_oversized_edit() -> None:
    base = _Edit(0, bytes(1024))
    history = EditHistory(base, max_steps=10, max_bytes=2800)
    for label in range(1, 5):
        assert history.commit(replace(base, label=label), "Metadata")
    assert history.steps == 4 and history.retained_bytes < 2800

    for label in range(5, 8):
        assert history.commit(_Edit(label, bytes((label,)) * 1024), "Mask")
    assert history.steps == 1 and history.retained_bytes <= 2800
    assert history.undo() == "Mask" and history.value.label == 6
    assert history.redo() == "Mask"

    huge = _Edit(8, bytes(4096))
    assert history.commit(huge, "Oversized")
    assert history.value is huge and history.steps == 0 and history.limit_reached
    assert history.undo() is None
    assert history.complete_edit(huge, base)
    assert history.value is base and history.retained_bytes < 2800
    assert history.commit(replace(base, label=9), "Metadata")
    assert not history.limit_reached and history.undo() == "Metadata"
