"""The merge step: what the template generated, added to what exists.

Adoption renders with `overwrite=False`, so the files the adopter already
has are left alone -- and then this step merges the template's entries
into them without rewriting anything of theirs: dependencies and tool
configuration into `pyproject.toml`, missing entries into the
line-oriented files (`.gitignore`, task runners), the template's checks
beside (or, when approved, into) their CI workflow. `plan_merges`
computes the same merge read-only for a dry run; `merge_generated_files`
applies it, recording old bytes into the run's backup as it goes, and
`_MergeError` rolls the whole run back.

This is a drivers-layer module by the tests/test_tool_layers.py table: it
renders a fresh scaffold for comparison and consumes the merge machinery.
"""

# WHYNOT: leaf sibling of the adopt split; the private names below are
# intra-package collaborators, not encapsulated APIs (they were one
# module before the split).
# pyright: reportPrivateUsage=false

from __future__ import annotations

import contextlib
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import batch  # noqa: E402
from tools import file_merge  # noqa: E402
from tools import pyproject_merge  # noqa: E402
from tools.adopt_models import Adoption  # noqa: E402
from tools.adopt_models import _Run  # noqa: E402
from tools.adopt_models import top  # noqa: E402
from tools.adopt_report import merge_problem  # noqa: E402

# --- the merge step ----------------------------------------------------------
#
# This is the transaction's write phase. It records old bytes into the same
# `_Run.backup` dict the journal covers and the rollback restores, and its
# `_MergeError` is a rollback trigger -- so the layering runs one way through
# `tools/adopt_models.py`: this module borrows `_Run` and `Adoption` from
# there, the journal borrows them too, and nothing borrows back. The merge
# plan side (`plan_merges`, `_plan_merges`) and the read-only verdict
# (`merge_problem`, in `tools/adopt_report.py`) stay callable without a run.

# The template files an adopter commonly already has, and how to merge each.
MERGE_KINDS = {
    ".gitignore": "gitignore",
    "justfile": "justfile",
    "Makefile": "makefile",
    "Taskfile.yml": "taskfile",
    "tasks.py": "python_tasks",
    "duties.py": "python_tasks",
}

# Every existing file the merge step edits, plus the CI caller's own workflow
# it may append to. The snapshot must cover them even when the template does
# not render them for these answers (a `Taskfile.yml` the template omits is
# still a file the merge appends to, and the journal must hold its old bytes).
MERGE_TARGETS = ("pyproject.toml", ".github/workflows/ci.yml", *MERGE_KINDS)


def plan_merges(target: Path, data: dict[str, Any], ref: str) -> dict[str, Any]:
    """Compute every merge without writing, for a dry run.

    Renders the fresh scaffold it plans against and removes it afterwards. A
    caller that already holds the run's scaffold (`_finish_with_merges` renders
    one and the plan and the application share it) plans with `_plan_merges`
    instead of paying for a second render of the same answers.
    """
    source = render_fresh_source(data, ref)
    try:
        return _plan_merges(target, data, source)
    finally:
        shutil.rmtree(source, ignore_errors=True)


def _plan_merges(target: Path, data: dict[str, Any], source: Path) -> dict[str, Any]:
    """The merge plan, computed against an already-rendered fresh scaffold."""
    dependencies = pyproject_merge.merge_dependencies(target / "pyproject.toml", source / "pyproject.toml", apply=False)
    config = pyproject_merge.merge_tool_config(
        target / "pyproject.toml",
        source / "pyproject.toml",
        identity=_merge_identity(data, source),
        apply=False,
    )
    files = [
        file_merge.merge_text_file(target / name, source / name, kind, apply=False).as_dict()
        for name, kind in MERGE_KINDS.items()
        if (target / name).is_file() and (source / name).is_file()
    ]
    ci_plan = _plan_ci_jobs(target, source)
    if ci_plan is not None:
        files.append(ci_plan)
    return {"dependencies": dependencies.as_dict(), "tool_config": config.as_dict(), "files": files}


def render_fresh_source(data: dict[str, Any], ref: str) -> Path:
    """Render a *fresh* project into a temp dir and return where it landed.

    In adopt mode the template does not render the protected files at all, so
    asking what the template would have generated means asking for the fresh
    scaffold. The caller owns the returned directory's lifetime.
    """
    directory = Path(tempfile.mkdtemp(prefix="adopt-merge-"))
    fresh = {**data, "existing_project": False, "adopt_protect": []}
    with batch.report_stream_only():
        batch.render(str(top()), directory, fresh, ref)
    return directory


def _merge_identity(data: dict[str, Any], source: Path) -> tuple[str, ...]:
    """Tokens that mark a value as *this project's*, not a tool preference."""
    tokens = {
        str(data.get(key, ""))
        for key in ("package_name", "repo_name", "distribution_name", "github_org", "gitlab_group")
    }
    if (source / "pyproject.toml").is_file():
        with contextlib.suppress(tomllib.TOMLDecodeError, KeyError, OSError):
            tokens.add(str(tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))["project"]["name"]))
    return tuple(sorted(token for token in tokens if token))


def _merge_pyproject(run: _Run, adoption: Adoption, source: Path, approved: frozenset[str]) -> None:
    """Merge dependencies and tool configuration into pyproject.toml and check for corruption."""
    target_pyproject = run.target / "pyproject.toml"
    before_pyproject = run.backup.get("pyproject.toml") or (
        target_pyproject.read_bytes() if target_pyproject.is_file() else None
    )
    merged = pyproject_merge.merge_dependencies(target_pyproject, source / "pyproject.toml")
    adoption.deps = merged.as_dict()
    adoption.notes.extend(merged.notes)
    config = pyproject_merge.merge_tool_config(
        target_pyproject,
        source / "pyproject.toml",
        identity=_merge_identity(run.data, source),
        approved=approved,
    )
    adoption.tool_config = config.as_dict()
    adoption.notes.extend(config.notes)
    problem = merge_problem(target_pyproject, before_pyproject)
    if problem:
        raise _MergeError(problem)


def merge_generated_files(
    run: _Run,
    adoption: Adoption,
    *,
    approved: frozenset[str] = frozenset(),
    approved_files: frozenset[str] = frozenset(),
    source: Path | None = None,
) -> None:
    """Merge what the template generated into the files the adopter already had.

    `source` is a fresh scaffold the caller already rendered: a run renders one
    scaffold and the confirmation plan and this merge share it, because nothing
    between showing the plan and the human's answer can change the answers or
    the template tree. Without one, a scaffold is rendered here and removed
    afterwards, which is what a standalone call wants; the caller's scaffold is
    the caller's to free.
    """
    owned = source is None
    if source is None:
        source = render_fresh_source(run.data, run.ref)
    try:
        _merge_pyproject(run, adoption, source, approved)
        _merge_text_files(run, adoption, source, approved_files=approved_files)
        _merge_ci_caller(run, adoption, source, approved_files=approved_files)
    finally:
        if owned:
            shutil.rmtree(source, ignore_errors=True)


class _MergeError(Exception):
    """A merge broke the add-only contract; the caller rolls the run back."""


def _merge_text_files(
    run: _Run, adoption: Adoption, source: Path, *, approved_files: frozenset[str] = frozenset()
) -> None:
    """Append the missing entries of the line-oriented files, keeping backups."""
    for name, kind in MERGE_KINDS.items():
        target_file = run.target / name
        if not target_file.is_file() or not (source / name).is_file():
            continue
        before = run.backup.setdefault(name, target_file.read_bytes())
        result = file_merge.merge_text_file(target_file, source / name, kind, append=name in approved_files)
        adoption.files_merged.append(result.as_dict())
        adoption.notes.extend(result.notes)
        if result.applied and not file_merge.original_is_preserved(before, target_file.read_bytes()):
            msg = f"merging {name} rewrote existing content"
            raise _MergeError(msg)
    _note_runner_mismatch(run, adoption, source)


def _note_runner_mismatch(run: _Run, adoption: Adoption, source: Path) -> None:
    """Tell the adopter when their runner file is not the one the answers picked."""
    for name, kind in MERGE_KINDS.items():
        if kind == "gitignore" or not (run.target / name).is_file():
            continue
        if not (source / name).is_file():
            runners = [candidate for candidate, candidate_kind in MERGE_KINDS.items() if candidate_kind != "gitignore"]
            rendered = ", ".join(sorted(candidate for candidate in runners if (source / candidate).is_file()))
            adoption.notes.append(
                f"your {name} was kept, but these answers render {rendered or 'no task runner'}; "
                f"re-run with --data task_runner=<runner> for that runner's entries"
            )


def _merge_ci_caller(
    run: _Run, adoption: Adoption, source: Path, *, approved_files: frozenset[str] = frozenset()
) -> None:
    """Add the template's checks beside their workflow — or into it, when approved.

    The default is the non-destructive placement (`copier-ci.yml`). Appending
    to their ci.yml happens only for a plan entry the human approved; when the
    append turns out to be unsafe (or there was nothing to append), the run
    falls back to the placement, so the checks are offered either way.
    """
    target_ci = run.target / ".github/workflows/ci.yml"
    if not target_ci.is_file():
        return
    source_ci = source / ".github/workflows/ci.yml"
    if "ci.yml" in approved_files and source_ci.is_file():
        before = run.backup.setdefault(".github/workflows/ci.yml", target_ci.read_bytes())
        result = file_merge.merge_ci_jobs(target_ci, source_ci, append=True)
        adoption.files_merged.append(result.as_dict())
        adoption.notes.extend(result.notes)
        if result.applied:
            if not file_merge.original_is_preserved(before, target_ci.read_bytes()):
                msg = "merging .github/workflows/ci.yml rewrote existing content"
                raise _MergeError(msg)
            return
        if not result.reported:
            return  # nothing was missing: their workflow already carries the checks
        adoption.notes.append("your ci.yml could not take the jobs; copier-ci.yml was added alongside instead")
    result = file_merge.merge_ci_caller(run.target, source_ci)
    adoption.files_merged.append(result.as_dict())
    adoption.notes.extend(result.notes)


def _plan_ci_jobs(target: Path, source: Path) -> dict[str, Any] | None:
    """The plan for their ci.yml: the read-only jobs that could be appended to it."""
    target_ci = target / ".github/workflows/ci.yml"
    source_ci = source / ".github/workflows/ci.yml"
    if not target_ci.is_file() or not source_ci.is_file():
        return None
    return file_merge.merge_ci_jobs(target_ci, source_ci, append=False).as_dict()
