"""Human and machine reports: what a run planned, did, or undid.

`render_report` narrates an adoption (or its dry run) for the terminal;
`render_recovery` narrates a `--recover`; the `as_dict` forms on the
records are the `--json` equivalents. `_merge_summary_from` formats a
merge plan once so the confirmation prompt and the report can never drift
into describing two different merges, and `merge_problem` guards the
add-only contract the merge step promises.

This is a drivers-layer module by the tests/test_tool_layers.py table: it
renders text about adoption artifacts, changing nothing.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import pyproject_merge  # noqa: E402
from tools.adopt_models import Adoption  # noqa: E402
from tools.adopt_models import Recovery  # noqa: E402


def merge_problem(target_pyproject: Path, before: bytes | None) -> str | None:
    """Why the merged pyproject is not acceptable, or None when it is.

    The merge may only add: every requirement that was declared before must
    still be declared, unchanged, and the file must still parse. A target that
    did not parse *before* the merge is not the merge's fault - the merge
    refuses to touch it and says so in its own note - so it is not a problem
    here either (checking it in this order is what keeps a pre-broken file from
    being reported as broken *by* the merge, which refused the whole adoption).
    """
    if before is None:
        return None
    try:
        before_document = tomllib.loads(before.decode("utf-8"))
    except tomllib.TOMLDecodeError:
        return None
    try:
        after_document = tomllib.loads(target_pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as exc:
        return f"the merged file does not parse: {exc}"
    after = pyproject_merge.declared_values(after_document)
    for name, raw in pyproject_merge.declared_values(before_document).items():
        if name not in after:
            return f"{name} was dropped"
        if after[name] != raw:
            return f"{name} was changed from {raw!r} to {after[name]!r}"
    return None


def _render_outcome_lines(adoption: Adoption) -> list[str]:
    """Format the status and failure details of the adoption run."""
    if adoption.cancelled:
        return ["cancelled -- nothing was applied"]
    if not adoption.applied and adoption.error is None:
        return ["dry run -- nothing written"]
    if adoption.error is not None:
        lines = [f"FAILED: {adoption.error}"]
        if adoption.restored:
            lines.append(f"  restored: {', '.join(adoption.restored)}")
        if adoption.removed:
            lines.append(f"  removed what the run created: {len(adoption.removed)} file(s)")
        return lines
    return [f"adopted: {len(adoption.created)} file(s) added, {len(adoption.unchanged)} existing file(s) untouched"]


def render_report(adoption: Adoption) -> str:
    """Human-readable plan and outcome."""
    lines = [
        f"target: {adoption.target}",
        f"mode:   {adoption.mode}",
        f"ref:    {adoption.ref}  ({adoption.ref_reason})",
    ]
    if adoption.skip:
        lines.append(f"skip:   {' '.join(adoption.skip)}")
    lines.append("")
    lines.extend(_render_outcome_lines(adoption))
    merged = _merge_summary(adoption)
    if merged:
        heading = "merged into your files" if adoption.applied else "would merge into your files"
        lines += ["", heading]
        lines.extend(f"  {line}" for line in merged)
    if adoption.notes:
        lines.append("")
        lines.extend(f"  {note}" for note in adoption.notes)
    if adoption.applied:
        lines += [
            "",
            "next",
            "  git diff     # review; the adoption only added files",
            "  git status   # untracked additions: CI, hygiene, AGENTS.md, ...",
        ]
    return "\n".join(lines)


def _merge_summary_from(plan: dict[str, Any]) -> list[str]:
    """The merge-summary lines, computed from a plan: the one implementation.

    Both readers of a merge come through here -- the confirmation prompt (via
    `_confirm_merges`) and the human report (via `_merge_summary`) -- so the
    plan a human approves and the outcome they review can never drift into
    describing two different merges.
    """
    lines: list[str] = []
    dependencies = plan.get("dependencies") or {}
    if dependencies.get("added"):
        added = [f"{section}: {', '.join(names)}" for section, names in dependencies["added"].items()]
        lines.append(f"pyproject.toml dependencies -> {'; '.join(added)}")
    config = plan.get("tool_config") or {}
    if config.get("added"):
        tables = sorted(config["added"])
        shown = ", ".join(f"[{table}]" for table in tables[:3])
        more = f" and {len(tables) - 3} more" if len(tables) > 3 else ""
        lines.append(f"pyproject.toml tool config -> {len(tables)} table(s): {shown}{more}")
    for entry in plan.get("files", []):
        detail = ", ".join(entry.get("added", [])[:6]) + ("..." if len(entry.get("added", [])) > 6 else "")
        if detail:
            lines.append(f"{Path(entry['path']).name} -> {detail}")
        elif entry.get("reported"):
            lines.append(f"{Path(entry['path']).name} -> not written: {', '.join(entry['reported'][:6])}")
    return lines


def _merge_summary(adoption: Adoption) -> list[str]:
    """One line per file the merge step touched, for the review step.

    An adapter over `_merge_summary_from`, deliberately not a second rendering
    of it: the two used to be twin implementations of the same lines (TODO.md
    §28.5 R6), which is exactly the kind of drift a summary must not have. The
    fields an Adoption carries are the plan's dict shape under other names, so
    the adapter is the whole difference.
    """
    return _merge_summary_from(
        {"dependencies": adoption.deps, "tool_config": adoption.tool_config, "files": adoption.files_merged}
    )


def render_recovery(recovery: Recovery) -> str:
    """Human-readable recovery outcome."""
    lines = [f"target:  {recovery.target}", f"journal: {recovery.journal}"]
    if not recovery.found:
        lines.append("nothing to recover: this project has no journal")
    elif recovery.applied:
        lines.append(f"recovered: {len(recovery.restored)} file(s) restored, {len(recovery.removed)} removed")
    else:
        lines.append("recovered: the project already matched the journal")
    lines.extend(f"  {note}" for note in recovery.notes)
    if recovery.found:
        lines.append("  nothing of the interrupted run is left; adopt again when you are ready")
    return "\n".join(lines)
