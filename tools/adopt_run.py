"""The adoption transaction: plan, render, verify, merge, or roll back.

`adopt` is the single entry point: it detects the target's mode, refuses
what it must (a project this template owns, a foreign template without
takeover, a stale journal), resolves the revision, and then -- unless this
is a dry run -- renders into the live target inside a journaled,
signal-guarded transaction. Anything the render or the merge step does
wrong restores the project byte for byte.

This is a drivers-layer module by the tests/test_tool_layers.py table: it
acts on the real target tree with copier.
"""

# WHYNOT: leaf sibling of the adopt split; the private names below are
# intra-package collaborators, not encapsulated APIs (they were one
# module before the split).
# pyright: reportPrivateUsage=false

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import batch  # noqa: E402
from tools import detect  # noqa: E402
from tools import file_merge  # noqa: E402
from tools.adopt_confirm import _finish_with_merges  # noqa: E402
from tools.adopt_confirm import _plan_only  # noqa: E402
from tools.adopt_crash import _crash_on_write  # noqa: E402
from tools.adopt_crash import _Interrupted  # noqa: E402
from tools.adopt_crash import _signals_roll_back  # noqa: E402
from tools.adopt_crash import crash_drill  # noqa: E402
from tools.adopt_journal import _Journal  # noqa: E402
from tools.adopt_journal import _refuse_stale_journal  # noqa: E402
from tools.adopt_journal import _remove_journal  # noqa: E402
from tools.adopt_journal import _undo_run  # noqa: E402
from tools.adopt_journal import _write_journal  # noqa: E402
from tools.adopt_merge import MERGE_TARGETS  # noqa: E402
from tools.adopt_revision import _plan_answers  # noqa: E402
from tools.adopt_revision import resolve_ref  # noqa: E402
from tools.adopt_tree import _dirs_under  # noqa: E402
from tools.adopt_tree import _files_under  # noqa: E402
from tools.adopt_tree import _snapshot  # noqa: E402
from tools.adopt_tree import _verify  # noqa: E402
from tools.adopt_types import JOURNAL_NAME  # noqa: E402
from tools.adopt_types import AdoptError  # noqa: E402
from tools.adopt_types import Adoption  # noqa: E402
from tools.adopt_types import OwnershipError  # noqa: E402
from tools.adopt_types import _Run  # noqa: E402
from tools.adopt_types import repo_root  # noqa: E402


def _check_adopt_preconditions(target: Path, detection: detect.Detection) -> None:
    """Verify the target can be adopted before any state is changed."""
    _refuse_stale_journal(target)
    if detection.mode == "update":
        msg = "this project was already generated from this template: run `copier update` (or tools/batch.py)"
        raise AdoptError(msg)
    if detection.mode == "foreign":
        msg = (
            f"another copier template owns this project ({detection.foreign_src}); "
            "pass takeover=True to replace its record"
        )
        raise OwnershipError(msg)


def _init_adoption(
    target: Path,
    detection: detect.Detection,
    resolved_ref: str,
    reason: str,
    skip: list[str] | None,
) -> Adoption:
    """Create the initial Adoption record with populated notes and skip list."""
    adoption = Adoption(
        target=str(target),
        mode=detection.mode,
        ref=resolved_ref,
        ref_reason=reason,
        skip=list(detection.skip if skip is None else skip),
        notes=list(detection.notes),
    )
    if skip is None and detection.mode == "adopt" and not adoption.skip:
        adoption.notes.append("no collisions: nothing existing would be replaced")
    return adoption


def _apply_dry_run_plan(
    target: Path,
    answers: dict[str, Any],
    adoption: Adoption,
    detection: detect.Detection,
    *,
    merge_generated: bool,
) -> Adoption:
    """Calculate the dry-run plan without writing anything to disk."""
    _plan_only(target, answers, adoption.ref, adoption, detection)
    if not merge_generated:
        adoption.merged_dependencies = None
        adoption.merged_tool_config = None
        adoption.merged_files = []
    return adoption


def _apply_adoption_transaction(
    run: _Run,
    journal: _Journal,
    adoption: Adoption,
    *,
    merge_generated: bool,
    ask: Callable[[str], str] | None,
) -> Adoption:
    """Execute the transactional adoption: render, verify, merge, and clean up."""
    target = run.target
    with _signals_roll_back():
        try:
            _write_journal(target, journal)
            with _crash_on_write("render", target), batch.report_stream_only():
                batch.render(
                    str(repo_root()),
                    target,
                    run.answers,
                    run.ref,
                    skip_if_exists=tuple(adoption.skip),
                    overwrite=False,
                )
            crash_drill("verify")
            changed, removed, created = _verify(target, run.backup, run.preexisting_files | {JOURNAL_NAME})
            if changed or removed:
                problem = f"the render modified existing files ({', '.join([*changed, *removed][:5])})"
                _undo_run(run, adoption, problem, "rolled back: the project is unchanged")
                return adoption
            adoption.ok = True
            adoption.applied = True
            adoption.created = created
            adoption.unchanged = sorted(run.backup)
            if merge_generated:
                _finish_with_merges(run, adoption, ask)
            _remove_journal(target)
        except _Interrupted as exc:
            _undo_run(run, adoption, f"{exc}; rolled back", "rolled back: the project is unchanged")
        except Exception as exc:  # noqa: BLE001  WHYNOT: the render's own failure type and an unexpected one in the merge step are both rolled back, not raised.
            _undo_run(run, adoption, f"{type(exc).__name__}: {exc}", "rolled back: the project is unchanged")
    return adoption


def adopt(  # noqa: PLR0913  WHYNOT: the keyword-only options are the operation's whole contract; a bag would hide them from the MCP tool schema.
    target: Path,
    *,
    ref: str | None = None,
    answers: dict[str, Any] | None = None,
    skip: list[str] | None = None,
    takeover: bool = False,
    dry_run: bool = False,
    merge_generated: bool = True,
    ask: Callable[[str], str] | None = None,
) -> Adoption:
    """Plan (and unless `dry_run`, apply) an adoption of `target`.

    The mutation is crash-recoverable: the journal is written and fsynced
    before the first change and removed only when the run has committed or been
    rolled back, so `recover` can undo whatever a killed process left.
    """
    detection = detect.detect(target, takeover=takeover)
    _check_adopt_preconditions(target, detection)
    resolved_ref, reason = resolve_ref(ref)
    adoption = _init_adoption(target, detection, resolved_ref, reason, skip)
    planned_answers = _plan_answers(detection, answers or {})
    if dry_run:
        return _apply_dry_run_plan(target, planned_answers, adoption, detection, merge_generated=merge_generated)

    backup = _snapshot(target, sorted({*detection.kept, *detection.collisions, *MERGE_TARGETS}))
    preexisting_files = _files_under(target)
    preexisting_dirs = _dirs_under(target)
    journal = _Journal(
        target=target,
        ref=resolved_ref,
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        planned_creates=sorted({*detection.added, f".github/workflows/{file_merge.CI_CALLER_NAME}"}),
        preexisting_files=sorted(preexisting_files),
        preexisting_dirs=sorted(preexisting_dirs),
        old_bytes=backup,
    )
    run = _Run(
        target=target,
        backup=backup,
        answers=planned_answers,
        ref=resolved_ref,
        preexisting_files=preexisting_files,
        preexisting_dirs=preexisting_dirs,
    )
    return _apply_adoption_transaction(run, journal, adoption, merge_generated=merge_generated, ask=ask)
