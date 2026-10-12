"""The merge confirmation: show the plan, ask, and apply or step back.

Without an `ask` callback the automatic plan applies as-is, which is what
a non-interactive caller (CI, an MCP tool) wants. With one, the questions
are the plan itself: whether to merge at all, which task files may grow,
where the CI checks go, and -- one by one -- the values that name the
generated project. The plan and the application share the run's one fresh
scaffold, rendered before the prompt so a decline never renders twice.

This is a drivers-layer module by the tests/test_tool_layers.py table: it
prompts through the caller and merges into the real target tree.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import detect  # noqa: E402
from tools.adopt_crash import _crash_on_write  # noqa: E402
from tools.adopt_journal import _undo_run  # noqa: E402
from tools.adopt_merge import _MergeError  # noqa: E402
from tools.adopt_merge import _plan_merges  # noqa: E402
from tools.adopt_merge import merge_generated_files  # noqa: E402
from tools.adopt_merge import plan_merges  # noqa: E402
from tools.adopt_merge import render_fresh_source  # noqa: E402
from tools.adopt_models import Adoption  # noqa: E402
from tools.adopt_models import _Run  # noqa: E402
from tools.adopt_report import _merge_summary_from  # noqa: E402


def _finish_with_merges(run: _Run, adoption: Adoption, ask: Callable[[str], str] | None) -> None:
    """Confirm the merge plan (when asked), apply it, or take the run back.

    The run's one fresh scaffold is rendered here, before the prompt, and
    shared by the plan the human confirms and the merge that applies it:
    within a run the answers and the template tree cannot change, so the
    second scaffold this step used to render (three copier renders per
    interactive adoption) produced byte-identical files. Rendering it before
    asking also means a decline or a cancel never renders a second time, and
    the scaffold is freed whichever way the run goes.
    """
    source = render_fresh_source(run.data, run.ref)
    try:
        confirmation = _confirm_merges(run, ask, source)
        if confirmation.cancel:
            _undo_run(run, adoption, None, "cancelled: the render was rolled back too")
            adoption.cancelled = True
            return
        if not confirmation.merge:
            adoption.notes.append("merges skipped: your files were left as they were")
            return
        try:
            with _crash_on_write("merge", run.target):
                merge_generated_files(
                    run,
                    adoption,
                    source=source,
                    approved=confirmation.approved,
                    approved_files=confirmation.files,
                )
        except _MergeError as exc:
            _undo_run(
                run, adoption, f"merge failed and was rolled back: {exc}", "rolled back: the project is unchanged"
            )
    finally:
        shutil.rmtree(source, ignore_errors=True)


@dataclass(frozen=True)
class Confirmation:
    """The human's answer to the merge plan."""

    cancel: bool = False
    merge: bool = True
    approved: frozenset[str] = frozenset()
    files: frozenset[str] = frozenset()


def _confirm_merges(run: _Run, ask: Callable[[str], str] | None, source: Path) -> Confirmation:
    """Show what would be merged and ask; returns the answer.

    Without an `ask` callback this is a no-op: the automatic plan is applied,
    which is what a non-interactive caller (CI, an MCP tool) wants. With one,
    the questions are the plan itself and then, one by one, the values that
    were *not* copied because they name the generated project -- those are the
    decisions a human should make. The plan is computed against the run's
    already-rendered scaffold, so prompting adds no render of its own.
    """
    if ask is None:
        return Confirmation()
    plan = _plan_merges(run.target, run.data, source)
    lines = _merge_summary_from(plan)
    if not lines:
        return Confirmation()
    answer = ask(_MERGE_QUESTION.format(plan="\n".join(lines)))
    if answer == "cancel":
        return Confirmation(cancel=True)
    if answer == "no":
        return Confirmation(merge=False)
    approved_files = _ask_about_task_files(plan, ask)
    approved_files |= _ask_about_ci_jobs(plan, ask)
    approved_values = _ask_about_values(plan, ask)
    return Confirmation(approved=frozenset(approved_values), files=frozenset(approved_files))


# The file kinds where appending means a real edit of the adopter's task list.
TASK_APPEND_KINDS = ("taskfile", "python_tasks")


def _ask_about_task_files(plan: dict[str, Any], ask: Callable[[str], str]) -> set[str]:
    """Ask about the task files (Taskfile.yml, tasks.py, duties.py): appending tasks is a real edit."""
    approved: set[str] = set()
    for entry in plan["files"]:
        if entry.get("kind") not in TASK_APPEND_KINDS or not entry.get("reported"):
            continue
        name = Path(entry["path"]).name
        if ask(f"append these tasks to your {name}: {', '.join(entry['reported'][:8])}? [Y]es / [n]o") == "yes":
            approved.add(name)
    return approved


def _ask_about_ci_jobs(plan: dict[str, Any], ask: Callable[[str], str]) -> set[str]:
    """Ask where the template's read-only jobs go: into their ci.yml, or beside it."""
    approved: set[str] = set()
    for entry in plan["files"]:
        if entry.get("kind") != "ci_jobs" or not entry.get("reported"):
            continue
        name = Path(entry["path"]).name
        answer = ask(
            f"append these jobs to your {name}: {', '.join(entry['reported'][:8])}? "
            "[Y]es / [n]o (copier-ci.yml alongside instead)"
        )
        if answer == "yes":
            approved.add(name)
    return approved


def _ask_about_values(plan: dict[str, Any], ask: Callable[[str], str]) -> set[str]:
    """Ask, one by one, about the values that name this project."""
    approved: set[str] = set()
    approve_rest = False
    for line in plan["tool_config"]["needs_your_value"]:
        key_path = line.split(" (template:")[0]
        if approve_rest:
            approved.add(key_path)
            continue
        answer = ask(f"add {line}? [Y]es / [n]o / [a]ll:")
        if answer == "all":
            approve_rest = True
            approved.add(key_path)
        elif answer == "yes":
            approved.add(key_path)
    return approved


_MERGE_QUESTION = """\
these files the template also generates already exist, and this is what would
be added to them (nothing of yours is rewritten):

{plan}

Apply? [Y]es / [n]o (render only) / [c]ancel:"""


def _plan_only(target: Path, data: dict[str, Any], ref: str, adoption: Adoption, detection: detect.Detection) -> None:
    """Fill in a dry-run result: what would be rendered, and what merged."""
    adoption.ok = True
    adoption.unchanged = detection.kept
    adoption.notes.append(f"dry run: would render {len(detection.added)} new file(s)")
    plan = plan_merges(target, data, ref)
    adoption.deps = plan["dependencies"]
    adoption.tool_config = plan["tool_config"]
    adoption.files_merged = plan["files"]
    for section in (plan["dependencies"], plan["tool_config"]):
        adoption.notes.extend(section["notes"])
