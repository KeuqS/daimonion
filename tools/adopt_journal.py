"""The crash journal: what a killed run leaves behind for `--recover`.

The in-process rollback only covers failures the process survives. The
journal covers the rest: written (and fsynced, file and directory) before
the first byte of the target changes and removed only on commit or after
a rollback, so while it exists the run it describes has not committed and
`recover` can finish what the rollback was going to do -- or undo a run
that committed nothing. `_undo_run` is the same undo for a live run that
failed its verification.

This is a drivers-layer module by the tests/test_tool_layers.py table: it
acts on the real target tree.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools.adopt_crash import fire_crash_hook  # noqa: E402
from tools.adopt_files import _files_under  # noqa: E402
from tools.adopt_files import _fsync_dir  # noqa: E402
from tools.adopt_files import _remove_new_dirs  # noqa: E402
from tools.adopt_files import _roll_back  # noqa: E402
from tools.adopt_files import _write_bytes  # noqa: E402
from tools.adopt_models import JOURNAL_NAME  # noqa: E402
from tools.adopt_models import AdoptError  # noqa: E402
from tools.adopt_models import Adoption  # noqa: E402
from tools.adopt_models import Recovery  # noqa: E402
from tools.adopt_models import StaleJournalError  # noqa: E402
from tools.adopt_models import _Run  # noqa: E402

# --- the crash journal -------------------------------------------------------
#
# The in-process rollback only covers failures the process survives. A journal
# on disk covers the rest: it is written (and fsynced) before the first byte of
# the target changes, and removed only on commit or after a rollback, so while
# it exists the run it describes has not committed and `--recover` can finish
# what the rollback was going to do -- or undo a run that committed nothing.


def journal_path(target: Path) -> Path:
    """Where the journal of `target` lives (in the target: it must be findable)."""
    return target / JOURNAL_NAME


@dataclass
class _Journal:
    """What a killed run leaves behind for `--recover` to undo it with.

    `old` is the old bytes of every file the run may modify, `existing` is
    every file that was there before it started (so recovery can tell what the
    run created) and `dirs` the directories (so recovery can remove the empty
    ones it created). `may_create` is the plan itself, for the report.
    """

    target: Path
    ref: str
    started: str
    may_create: list[str]
    existing: list[str]
    dirs: list[str]
    old: dict[str, bytes]

    def as_dict(self) -> dict[str, Any]:
        """Serializable form; the old bytes are base64 because they are not text."""
        return {
            "version": 1,
            "tool": "tools/adopt.py",
            "target": str(self.target),
            "ref": self.ref,
            "started": self.started,
            "may_create": self.may_create,
            "existing": self.existing,
            "dirs": self.dirs,
            "old": {name: base64.b64encode(content).decode("ascii") for name, content in self.old.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> _Journal:
        """Rebuild a journal, refusing anything this version did not write."""
        if data["version"] != 1:
            msg = f"journal version {data['version']!r} is not version 1"
            raise ValueError(msg)
        return cls(
            target=Path(data["target"]),
            ref=str(data["ref"]),
            started=str(data["started"]),
            may_create=[str(name) for name in data["may_create"]],
            existing=[str(name) for name in data["existing"]],
            dirs=[str(name) for name in data["dirs"]],
            old={str(name): base64.b64decode(content) for name, content in data["old"].items()},
        )


def _write_journal(target: Path, journal: _Journal) -> None:
    """Write the journal durably, before the first change to the target.

    On disk and fsynced -- file and directory -- on purpose: it has to survive
    the process that writes it. The rename is atomic, so a journal at its final
    name is always complete; an unreadable one means nothing was written yet.
    """
    path = journal_path(target)
    payload = json.dumps(journal.as_dict(), sort_keys=True).encode("utf-8")
    temporary = path.with_name(f"{path.name}.new")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary).replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    _fsync_dir(target)


def _read_journal(path: Path) -> _Journal:
    """The journal at `path`; a journal this tool cannot vouch for is not recoverable."""
    try:
        return _Journal.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        msg = (
            f"{path} is not a journal this tool can read ({exc}); a journal is written before the "
            "target is first written, so if nothing has touched the project since, it is a leftover "
            "of a run that never started and safe to delete by hand"
        )
        raise AdoptError(msg) from exc


def _remove_journal(target: Path) -> None:
    """Drop the journal: the commit point of a run, and the end of a rollback.

    Not fsynced, deliberately. If a power loss un-does the unlink the journal
    comes back, and recovering twice is a no-op; if this were flushed first,
    a crash could leave an adopted tree whose journal was already gone.
    """
    journal_path(target).unlink(missing_ok=True)


def _restore(journal: _Journal) -> list[str]:
    """Write the recorded old bytes back; returns the files that had drifted."""
    restored: list[str] = []
    for relative, content in journal.old.items():
        path = journal.target / relative
        if path.is_file() and path.read_bytes() == content:
            continue
        _write_bytes(path, content)
        restored.append(relative)
        # Crash point: a recovery killed mid-restore. The files already written
        # back are on disk, the rest of the journal is not applied, and the
        # journal itself is untouched -- the next `--recover` reads the same
        # journal and converges, because every write is decided by what the
        # tree holds now, not by how far a previous one got.
        fire_crash_hook("recover")
    return sorted(restored)


def _unlink_created_files(target: Path, journal: _Journal) -> list[str]:
    """Delete files and directories created during the run, crashing safely at checkpoints."""
    removed = sorted(_files_under(target) - set(journal.existing) - {JOURNAL_NAME})
    for relative in removed:
        (target / relative).unlink()
        # Crash point: a recovery killed while it deletes what the run created.
        # The old bytes are all back by now, so what is in question is a subset
        # of the run's own files, and the journal (dropped last) still names
        # the ones this kill got to keep: the next `--recover` removes exactly
        # the rest and no second time.
        fire_crash_hook("recover")
    _remove_new_dirs(target, set(journal.dirs))
    return removed


def recover(target: Path) -> Recovery:
    """Undo an interrupted adoption from its journal, and remove the journal.

    This is the whole recovery: the recorded old bytes go back, every file that
    was not there before the run is deleted, the directories it created are
    removed, and the journal goes last -- a kill during recovery leaves it for
    the next `--recover`. Running it twice is a no-op: a tree that already
    matches is rewritten nowhere, and with no journal there is nothing to do at
    all. Both are success.
    """
    path = journal_path(target)
    if not path.is_file():
        return Recovery(target=str(target), journal=str(path), notes=["no journal: nothing to recover"])
    journal = _read_journal(path)
    if Path(journal.target).resolve() != target.resolve():
        msg = f"{path} records {journal.target}, not {target}: recover it from the project it belongs to"
        raise AdoptError(msg)
    restored = _restore(journal)
    removed = _unlink_created_files(target, journal)
    _remove_journal(target)
    recovery = Recovery(
        target=str(target),
        journal=str(path),
        found=True,
        applied=bool(restored or removed),
        restored=restored,
        removed=removed,
    )
    unplanned = [name for name in removed if name not in set(journal.may_create)]
    if unplanned:
        recovery.notes.append(
            f"removed {len(unplanned)} path(s) the plan did not name (e.g. {unplanned[0]}): the render "
            "creates files tools/detect.py does not list (copier's answers file, task output), which is "
            "why what gets deleted is decided by what was there before the run, not by the plan"
        )
    return recovery


def _refuse_stale_journal(target: Path) -> None:
    """Refuse to adopt over the journal of a run that did not finish.

    The tree is not in a state anybody chose, so a plan computed from it would
    be a plan about an accident; `--recover` is the way out.
    """
    stale = journal_path(target)
    if not stale.is_file():
        return
    msg = (
        f"{stale} is still there: a previous adoption did not finish\n"
        f"recover it first: python tools/adopt.py {target} --recover"
    )
    raise StaleJournalError(msg)


def _undo_run(run: _Run, adoption: Adoption, problem: str | None, note: str) -> None:
    """Take the whole run back -- render and merges -- and drop the journal.

    What the run created is read off the disk (present now, absent before it
    started) instead of remembered: that is the rule `--recover` applies, so a
    kill between any two writes is undone by the same code.
    """
    created = sorted(_files_under(run.target) - run.existing - {JOURNAL_NAME})
    adoption.restored, adoption.removed = _roll_back(run.target, run.backup, created, run.before_dirs)
    _remove_journal(run.target)
    adoption.ok = False
    adoption.applied = False
    adoption.error = problem
    adoption.notes.append(note)
