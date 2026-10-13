"""Durable tree surgery: snapshot, verify, and roll back.

The transaction renders into the live target, so every step that touches
the tree goes through here: `_snapshot` records the old bytes of every
file the run may write over, `_verify` diffs the render against them, and
`_roll_back` restores the backups and removes what the run created. Every
write is fsynced -- a restore must survive the crash that follows it.

This is a drivers-layer module by the tests/test_tool_layers.py table: it
acts on the real target tree.
"""

# WHYNOT: leaf module of the adopt split; these helpers are used by leaf
# siblings (imported private names read as unused locally).
# pyright: reportUnusedFunction=false

from __future__ import annotations

import os
import sys
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools.adopt_crash import crash_drill  # noqa: E402


def _files_under(target: Path) -> set[str]:
    """Every file in the tree, relative to `target`."""
    return {str(path.relative_to(target)) for path in target.rglob("*") if path.is_file()}


def _dirs_under(target: Path) -> set[str]:
    """Every directory in the tree, relative to `target`."""
    return {str(path.relative_to(target)) for path in target.rglob("*") if path.is_dir()}


def _write_bytes(path: Path, content: bytes) -> None:
    """Write `content` at `path` and flush it to disk.

    A restore is fsynced before the journal is removed: whatever a crash does
    afterwards, the recovery that was already applied is on disk, and the
    journal is either gone after a complete restore or still there to redo it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_dir(directory: Path) -> None:
    """Flush a directory entry (a rename is not durable without it)."""
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _snapshot(target: Path, risky: list[str]) -> dict[str, bytes]:
    """Content of every existing file the run could write over."""
    backup: dict[str, bytes] = {}
    for relative in risky:
        path = target / relative
        if path.is_file():
            backup[relative] = path.read_bytes()
    return backup


def _verify(target: Path, backup: dict[str, bytes], before: set[str]) -> tuple[list[str], list[str], list[str]]:
    """(changed, removed, created) -- what the render did that it should not have."""
    changed = [
        relative
        for relative, content in backup.items()
        if (target / relative).is_file() and (target / relative).read_bytes() != content
    ]
    removed = [relative for relative in backup if not (target / relative).exists()]
    return sorted(changed), sorted(removed), sorted(_files_under(target) - before)


def _remove_new_dirs(target: Path, before: set[str]) -> None:
    """Remove the directories the run created, deepest first (the empty ones).

    A render can leave an empty one behind (a `docs/how-to/` whose files were
    all conditional), and leaving it would make "the project is unchanged" a
    lie.
    """
    for relative in sorted(_dirs_under(target) - before, key=lambda name: len(Path(name).parts), reverse=True):
        directory = target / relative
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()


def _roll_back(
    target: Path, backup: dict[str, bytes], created: list[str], before_dirs: set[str]
) -> tuple[list[str], list[str]]:
    """Restore the backed-up files and remove every path this run created.

    Returns what it actually had to put back and delete: a file that never
    drifted is not reported as restored.

    The undo is a crash region like the render: a SIGKILL after any of these
    writes (`COPIER_ADOPT_CRASH_AT=rollback`) leaves a half-undone tree with
    the journal still on disk -- `_remove_journal` runs only after this
    returns -- and `--recover` finishes what the kill interrupted.
    """
    restored: list[str] = []
    for relative, content in backup.items():
        path = target / relative
        if path.is_file() and path.read_bytes() == content:
            continue
        _write_bytes(path, content)
        restored.append(relative)
        # Crash point: a rollback killed mid-restore, with the rest of the old
        # bytes still to go back and everything the run created still in place.
        crash_drill("rollback")
    removed: list[str] = []
    for relative in created:
        path = target / relative
        if path.is_file():
            path.unlink()
            removed.append(relative)
            # Crash point: a rollback killed mid-deletion, with a subset of the
            # run's files gone and the journal there to name the rest.
            crash_drill("rollback")
    _remove_new_dirs(target, before_dirs)
    return sorted(restored), sorted(removed)
