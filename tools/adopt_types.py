"""Shared vocabulary of the adoption driver: errors, records, constants.

`tools/adopt.py` adopts this template into an existing project as one
crash-recoverable transaction; this module is the bottom of its split: the
exception taxonomy (`AdoptError` and its refusals), the records the run
carries (`_Run`) and reports (`Adoption`, `Recovery`), the constants that
name the journal and the crash drill, and `repo_root()` -- the one repo-root
reader every sibling goes through, so a patched `tools.adopt_types.TOP`
redirects the ref judgement, the render and the merge scaffold at once.

This is a drivers-layer module by the tests/test_tool_layers.py table: it
touches no tree and runs no subprocess; it only names what a run is.
"""

# WHYNOT: this module is the bottom of the adopt split; its records and
# private helpers exist for leaf siblings, so a local "unused" verdict
# is a false positive (uses resolve through other leaves).
# pyright: reportPrivateUsage=false, reportUnusedClass=false

from __future__ import annotations

import sys
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))


def repo_root() -> Path:
    """The repo root: the directory containing copier.yml.

    Read through this function (not the module-global `TOP` directly) so a
    test that does `monkeypatch.setattr(tools.adopt_types, "TOP", ...)`
    redirects every in-repo reader at once: the render, the ref judgement
    and the merge scaffold expand the same tree.
    """
    return TOP


CONFIG_FILES = ("copier.yml", "copier.yaml")

# The crash journal: written before the first change to the target, removed on
# commit or after a rollback, and the only reason `--recover` can exist.
JOURNAL_NAME = ".copier-adopt-journal.json"
# The crash-point env var. Duplicated (not imported) from adopt_crash on
# purpose: adopt_types is the leaf every other leaf imports, so it must
# import nothing in-repo. adopt_crash defines its own copy for the same
# reason; the two literals are asserted equal in tests.
CRASH_POINT_ENV = "COPIER_ADOPT_CRASH_AT"


class AdoptError(Exception):
    """The request cannot be carried out as asked."""


class OwnershipError(AdoptError):
    """Another copier template owns the target (a refusal, not a failure)."""


class StaleJournalError(AdoptError):
    """A previous run left its journal behind: recover it before adopting."""


@dataclass
class _Run:
    """What the render produced, for the steps that verify or amend it."""

    target: Path
    backup: dict[str, bytes]
    answers: dict[str, Any]
    ref: str
    preexisting_files: set[str]
    preexisting_dirs: set[str]


@dataclass
class Adoption:
    """The plan, what the run did, and -- when it failed -- what was undone."""

    target: str
    mode: str
    ref: str
    ref_reason: str
    skip: list[str] = field(default_factory=list)
    created: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    restored: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    ok: bool = False
    applied: bool = False
    error: str | None = None
    notes: list[str] = field(default_factory=list)
    merged_dependencies: dict[str, Any] | None = None
    merged_tool_config: dict[str, Any] | None = None
    merged_files: list[dict[str, Any]] = field(default_factory=list)
    cancelled: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serializable form used by --json and the MCP tool."""
        return {
            "target": self.target,
            "mode": self.mode,
            "ref": self.ref,
            "ref_reason": self.ref_reason,
            "skip": self.skip,
            "created_count": len(self.created),
            "created": self.created,
            "unchanged": self.unchanged,
            "restored": self.restored,
            "removed": self.removed,
            "ok": self.ok,
            "applied": self.applied,
            "error": self.error,
            "notes": self.notes,
            "merged_dependencies": self.merged_dependencies,
            "merged_tool_config": self.merged_tool_config,
            "merged_files": self.merged_files,
            "cancelled": self.cancelled,
        }


@dataclass
class Recovery:
    """What `--recover` found in the journal, and what it put back."""

    target: str
    journal: str
    found: bool = False
    applied: bool = False
    restored: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Serializable form used by --json."""
        return {
            "target": self.target,
            "journal": self.journal,
            "found": self.found,
            "applied": self.applied,
            "restored_count": len(self.restored),
            "restored": self.restored,
            "removed_count": len(self.removed),
            "removed": self.removed,
            "notes": self.notes,
        }
