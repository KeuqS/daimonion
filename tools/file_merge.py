#!/usr/bin/env python3
"""Append-only merge for the template's text files.

`.gitignore`, `justfile` and `Makefile` are the files an adopter almost always
already has, and they are line-oriented: appending the entries the template
has and they do not is safe, and their own lines are never rewritten. The
`pyproject.toml` merge (tools/pyproject_merge.py) is a different problem —
structured, and edited with a round-trip parser — so it lives in its own
module.

The rule for every kind is the same: **read what the target already declares,
append only what is missing, and report anything that cannot be appended
safely** (a `Taskfile.yml` is YAML, where appending text is not a thing;
Python task files need imports). Verification is the same for all of them:
the original content must still be a prefix of the new content.

The CI workflow is the one kind with two destinations: `ci_caller` builds a
side-by-side `copier-ci.yml` (the default), and `merge_ci_jobs` appends the
template's read-only jobs into the adopter's own `ci.yml` when approved.

Usage:
    python tools/file_merge.py --target .gitignore --source generated/.gitignore --kind gitignore
    python tools/file_merge.py --target Makefile --source generated/Makefile --kind makefile --dry-run
"""

from __future__ import annotations

import argparse
import ast
import builtins
import json
import re
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any

import yaml

TOP = Path(__file__).resolve().parent.parent

GITIGNORE_HEADER = "# Added by daimonion (tools/adopt.py)"
MAKEFILE_TARGET = re.compile(r"^(?P<name>[A-Za-z0-9_.][A-Za-z0-9_.-]*)\s*:(?!=)")
JUST_RECIPE = re.compile(r"^(?P<name>[a-zA-Z_][a-zA-Z0-9_-]*)(?P<rest>\s+[^:]*)?:")
IGNORED_JUST_NAMES = frozenset({"alias", "export", "import", "mod", "set", "unexport"})


class FileMergeError(Exception):
    """The merge cannot be carried out for this kind."""


@dataclass
class TextMerge:
    """What was appended, and what was left for the adopter."""

    path: str
    kind: str
    added: list[str] = field(default_factory=list)
    reported: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    applied: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serializable form used by --json and tools/adopt.py."""
        return {
            "path": self.path,
            "kind": self.kind,
            "added": self.added,
            "reported": self.reported,
            "notes": self.notes,
            "applied": self.applied,
        }


def _prefix(existing_text: str) -> str:
    """The original content, newline-terminated, plus a blank line if non-empty."""
    if not existing_text:
        return ""
    return existing_text if existing_text.endswith("\n") else existing_text + "\n"


def _lines(entries: list[str]) -> str:
    return "\n".join(entries) + "\n"


def _non_comment_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def _declared_gitignore(text: str) -> set[str]:
    return {line.strip() for line in _non_comment_lines(text)}


def _recipe_blocks(text: str, pattern: re.Pattern[str], *, skip: frozenset[str] = frozenset()) -> dict[str, str]:
    """Named block of a line-oriented build file: name -> the block's text.

    A block runs from its name line to the line before the next name line, so
    appending it keeps its body (commands, dependencies) intact.
    """
    lines = text.splitlines()
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match and match.group("name") not in skip:
            starts.append((index, match.group("name")))
    blocks: dict[str, str] = {}
    for position, (index, name) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        blocks.setdefault(name, "\n".join(lines[index:end]).rstrip("\n"))
    return blocks


def merge_gitignore(target_path: Path, source_path: Path, *, apply: bool = True) -> TextMerge:
    """Append the ignore patterns the target does not already have."""
    result = TextMerge(path=str(target_path), kind="gitignore")
    if not source_path.is_file():
        result.notes.append(f"{source_path} does not exist; nothing to merge")
        return result
    existing_text = target_path.read_text(encoding="utf-8") if target_path.is_file() else ""
    declared = _declared_gitignore(existing_text)
    missing = [line.strip() for line in _non_comment_lines(source_path.read_text(encoding="utf-8"))]
    result.added = [line for line in missing if line not in declared]
    if not result.added:
        result.notes.append("every template ignore pattern is already present")
        return result
    if apply:
        target_path.write_text(f"{_prefix(existing_text)}{GITIGNORE_HEADER}\n{_lines(result.added)}", encoding="utf-8")
        result.applied = True
    return result


def merge_recipes(target_path: Path, source_path: Path, kind: str, *, apply: bool = True) -> TextMerge:
    """Append the build-file recipes (make target / just recipe) that are missing."""
    result = TextMerge(path=str(target_path), kind=kind)
    if not source_path.is_file():
        result.notes.append(f"{source_path} does not exist; nothing to merge")
        return result
    pattern = MAKEFILE_TARGET if kind == "makefile" else JUST_RECIPE
    skip = frozenset() if kind == "makefile" else IGNORED_JUST_NAMES
    existing_text = target_path.read_text(encoding="utf-8") if target_path.is_file() else ""
    declared = set(_recipe_blocks(existing_text, pattern, skip=skip))
    blocks = _recipe_blocks(source_path.read_text(encoding="utf-8"), pattern, skip=skip)
    missing = {name: block for name, block in blocks.items() if name not in declared}
    if not missing:
        result.notes.append(f"every template {kind} entry is already present")
        return result
    result.added = sorted(missing)
    if apply:
        header = "# Added by daimonion (tools/adopt.py)"
        body = "\n\n".join(missing[name] for name in sorted(missing))
        target_path.write_text(f"{_prefix(existing_text)}{header}\n\n{body}\n", encoding="utf-8")
        result.applied = True
    return result


def _last_top_level_key(target_text: str) -> str | None:
    """The file's final top-level key, or None: a block can only be appended under it."""
    top_level = [line for line in target_text.splitlines() if line and not line[0].isspace() and ":" in line]
    return top_level[-1].split(":")[0].strip() if top_level else None


def _tasks_are_the_last_block(target_text: str) -> bool:
    """True when `tasks:` is the final top-level key, so blocks can be appended."""
    return _last_top_level_key(target_text) == "tasks"


def _taskfile_tasks(text: str) -> dict[str, Any]:
    try:
        document = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return {}
    tasks = document.get("tasks") if isinstance(document, dict) else None
    return tasks if isinstance(tasks, dict) else {}


def _parses_as_mapping(text: str) -> bool:
    """True when `text` is YAML that reads back as a mapping (or empty).

    `_taskfile_tasks` deliberately swallows a parse error (an unparsable
    target simply has no *known* tasks), which would make a "were the old
    tasks kept?" check vacuously true on a file that does not parse at all.
    The append path needs the stricter question.
    """
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    return document is None or isinstance(document, dict)


def _apply_taskfile_append(
    target_path: Path,
    target_text: str,
    blocks: dict[str, str],
    missing: dict[str, str],
    result: TextMerge,
) -> TextMerge:
    """Safely append missing task blocks to a Taskfile and rollback if corrupt."""
    before = _taskfile_tasks(target_text)
    appended = target_text if target_text.endswith("\n") else target_text + "\n"
    appended += "\n".join(blocks[name] for name in sorted(missing)) + "\n"
    target_path.write_text(appended, encoding="utf-8")
    after = _taskfile_tasks(appended)
    kept = all(name in after and after[name] == value for name, value in before.items())
    # An empty `before` makes `kept` vacuously true, so the append must also be
    # re-parseable and must actually carry the tasks it claims: a target with
    # `tasks: {}` (or one that does not parse at all) would otherwise take the
    # indented blocks, fail to parse, and still be reported as applied.
    if not (_parses_as_mapping(appended) and kept and all(name in after for name in missing)):
        target_path.write_text(target_text, encoding="utf-8")
        result.notes.append("appending the tasks produced a task list that does not hold them; undone")
        result.reported = sorted(missing)
        return result
    result.added = sorted(missing)
    result.applied = True
    return result


def merge_taskfile(target_path: Path, source_path: Path, *, append: bool = False) -> TextMerge:
    """Report the tasks a YAML task file is missing — and append them when asked.

    YAML is not append-friendly in general, so this is report-only unless the
    caller approves: `tasks:` must be the target's last top-level key, and the
    edit is verified by re-parsing (every task that was there must still be
    there, unchanged, and the new ones must parse). Anything else stays a
    report.
    """
    result = TextMerge(path=str(target_path), kind="taskfile")
    if not source_path.is_file():
        result.notes.append(f"{source_path} does not exist; nothing to merge")
        return result
    pattern = re.compile(r"^  (?P<name>[A-Za-z0-9_.-]+):")
    target_text = target_path.read_text(encoding="utf-8") if target_path.is_file() else ""
    declared = set(_recipe_blocks(target_text, pattern))
    blocks = _recipe_blocks(source_path.read_text(encoding="utf-8"), pattern)
    missing = {name: block for name, block in blocks.items() if name not in declared}
    if not missing:
        result.notes.append("every template task is already present")
        return result
    if not append or not _tasks_are_the_last_block(target_text):
        result.reported = sorted(missing)
        reason = (
            "reported rather than appended" if not append else "not appended: tasks: is not the last block in the file"
        )
        result.notes.append(f"these are YAML tasks, {reason}; copy the ones you want from the generated Taskfile.yml")
        return result
    return _apply_taskfile_append(target_path, target_text, blocks, missing, result)


PYTHON_TASK_DECORATORS = frozenset({"task", "duty"})


def _python_fragments(text: str, tree: ast.Module) -> list[tuple[str, str]]:
    """(name, source fragment) of every top-level function, decorators included."""
    lines = text.splitlines()
    fragments: list[tuple[str, str]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = min(node.lineno, *(decorator.lineno for decorator in node.decorator_list))
            fragments.append((node.name, "\n".join(lines[start - 1 : node.end_lineno]).rstrip("\n")))
    return fragments


def _task_decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """The plain names a function is decorated with: `@task`, `@task(deps)`, `invoke.tasks.task`."""
    names: set[str] = set()
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)
    return names


def _definition_time_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Names the `def` statement itself evaluates: decorators, defaults, annotations.

    A function whose annotations name something the module does not define fails
    at import, which is exactly what appending must never cause.
    """
    arguments = node.args
    expressions: list[ast.expr | None] = [
        *node.decorator_list,
        *arguments.defaults,
        *(default for default in arguments.kw_defaults if default is not None),
        *(argument.annotation for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)),
        arguments.vararg.annotation if arguments.vararg else None,
        arguments.kwarg.annotation if arguments.kwarg else None,
        node.returns,
    ]
    names: set[str] = set()
    for expression in expressions:
        if expression is not None:
            names.update(item.id for item in ast.walk(expression) if isinstance(item, ast.Name))
    return names


def _bound_names(tree: ast.Module) -> set[str]:
    """Every name the module binds at top level: imports, functions, classes, assignments."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _imported_bindings(tree: ast.Module) -> dict[str, str]:
    """Imported name -> the import statement that binds it (to suggest, not to copy)."""
    bindings: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bindings.setdefault((alias.asname or alias.name).split(".")[0], ast.unparse(node))
    return bindings


def _load_and_parse_task_trees(
    source_path: Path, target_path: Path, result: TextMerge
) -> tuple[tuple[str, ast.Module], tuple[str, ast.Module]] | None:
    """Load and parse source and target Python task files; returns None on failure."""
    if not source_path.is_file():
        result.notes.append(f"{source_path} does not exist; nothing to merge")
        return None
    source_text = source_path.read_text(encoding="utf-8")
    try:
        source_tree = ast.parse(source_text)
    except SyntaxError:
        result.notes.append(f"{source_path} does not parse; nothing to merge")
        return None
    target_text = target_path.read_text(encoding="utf-8") if target_path.is_file() else ""
    try:
        target_tree = ast.parse(target_text)
    except SyntaxError:
        result.notes.append(f"{target_path} does not parse; nothing appended")
        return None
    return (source_text, source_tree), (target_text, target_tree)


def _report_unimported_task_deps(
    missing: list[ast.FunctionDef | ast.AsyncFunctionDef],
    unimported: list[str],
    source_tree: ast.Module,
    result: TextMerge,
) -> None:
    """Record missing tasks and their unimported bindings as notes."""
    result.reported = sorted(node.name for node in missing)
    bindings = _imported_bindings(source_tree)
    for name in unimported:
        suggestion = f"; the generated file imports it as `{bindings[name]}`" if name in bindings else ""
        result.notes.append(f"not appended: `{name}` is not defined in your file{suggestion}")


def merge_python_tasks(  # noqa: PLR0911  WHYNOT: each return is one guard of the report-vs-append decision, the shape the other merges share.
    target_path: Path, source_path: Path, *, append: bool = False
) -> TextMerge:
    """Report the task functions a Python task file is missing — and append them when asked.

    The `tasks.py`/`duties.py` companion to the Taskfile merge: the missing
    task functions are appended, whole, at the end of the file; nothing already
    there is rewritten. One Python-specific guard: a task function only works
    when the names its `def` evaluates (the `@task`/`@duty` decorator, but also
    annotations and defaults) are already defined in the file — adding imports
    by hand is how the file breaks at runtime — so such a file is reported with
    the imports to add, never extended.
    """
    result = TextMerge(path=str(target_path), kind="python_tasks")
    parsed = _load_and_parse_task_trees(source_path, target_path, result)
    if parsed is None:
        return result
    (source_text, source_tree), (target_text, target_tree) = parsed
    missing, unimported = _find_missing_python_tasks(source_tree, target_tree)
    if not missing:
        result.notes.append("every template task is already present")
        return result
    if unimported:
        _report_unimported_task_deps(missing, unimported, source_tree, result)
        return result
    if not append:
        result.reported = sorted(node.name for node in missing)
        result.notes.append(
            "these are Python tasks, reported rather than appended; "
            f"copy the ones you want from the generated {source_path.name}"
        )
        return result
    return _apply_python_tasks_append(
        target_path, (target_text, target_tree), (source_text, source_tree), missing, result
    )


def _find_missing_python_tasks(
    source_tree: ast.Module,
    target_tree: ast.Module,
) -> tuple[list[ast.FunctionDef | ast.AsyncFunctionDef], list[str]]:
    """Return (missing_task_nodes, unimported_dependency_names)."""
    source_tasks = [
        node
        for node in source_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _task_decorator_names(node) & PYTHON_TASK_DECORATORS
    ]
    declared = _bound_names(target_tree)
    missing = [node for node in source_tasks if node.name not in declared]
    if not missing:
        return [], []
    needed = set().union(*(_definition_time_names(node) for node in missing))
    available = declared | set(dir(builtins)) | {node.name for node in missing}
    unimported = sorted(name for name in needed if name not in available)
    return missing, unimported


def _apply_python_tasks_append(
    target_path: Path,
    target: tuple[str, ast.Module],
    source: tuple[str, ast.Module],
    missing: list[ast.FunctionDef | ast.AsyncFunctionDef],
    result: TextMerge,
) -> TextMerge:
    """Append missing Python task functions to target_path and rollback if AST corrupts."""
    target_text, target_tree = target
    source_text, source_tree = source
    before = _python_fragments(target_text, target_tree)
    fragments = dict(_python_fragments(source_text, source_tree))
    header = "# Added by daimonion (tools/adopt.py)"
    appended = (
        _prefix(target_text)
        + header
        + "\n\n"
        + "\n\n".join(fragments[node.name] for node in sorted(missing, key=lambda node: node.name))
        + "\n"
    )
    target_path.write_text(appended, encoding="utf-8")
    try:
        after_tree = ast.parse(appended)
    except SyntaxError:
        after_tree = None
    if after_tree is None or _python_fragments(appended, after_tree)[: len(before)] != before:
        target_path.write_text(target_text, encoding="utf-8")
        result.notes.append("appending the tasks changed an existing function; undone")
        result.reported = sorted(node.name for node in missing)
        return result
    result.added = sorted(node.name for node in missing)
    result.applied = True
    return result


CI_JOB = re.compile(r"^  (?P<name>[A-Za-z0-9_.-]+):")
CI_CALLER_NAME = "copier-ci.yml"
CI_SAFE_REUSABLES = ("_tasks.yml", "_test.yml", "_hygiene.yml")
CI_EXCLUDED_NOTE = (
    "the dist/release/pypi and docs jobs are not copied: they publish artifacts, releases or "
    "GitHub Pages, and a second publisher is the one thing worse than none"
)


def ci_caller(source_text: str) -> tuple[str, list[str], list[str]]:
    """(caller workflow, kept jobs, dropped jobs) for an adopter who has their own ci.yml.

    Built by textual surgery on the generated workflow rather than a YAML
    round-trip: PyYAML (YAML 1.1) reads the `on:` key as the boolean true, so
    re-dumping it produces `true:` and an invalid workflow. Cutting job blocks
    out of the original text also keeps the generated formatting intact.
    """
    head, separator, rest = source_text.partition("\njobs:\n")
    if not separator:
        msg = "the generated ci.yml has no jobs: block"
        raise FileMergeError(msg)
    blocks = _recipe_blocks(rest, CI_JOB, skip=frozenset({"required-checks-passed"}))
    kept = [
        name
        for name, block in blocks.items()
        if any(f"uses: ./.github/workflows/{reusable}" in block for reusable in CI_SAFE_REUSABLES)
    ]
    dropped = sorted(name for name in blocks if name not in kept)
    caller = "\n".join([head.replace("name: CI", "name: Copier CI", 1), "jobs:", ""])
    caller += "\n\n".join(blocks[name] for name in sorted(kept)) + "\n"
    return caller, sorted(kept), dropped


def merge_ci_caller(target: Path, source_ci: Path, *, apply: bool = True) -> TextMerge:
    """Add the template's checks as a second workflow, leaving theirs alone.

    A separate file rather than an edit of theirs: workflow files are YAML
    with comments, and the template's jobs cannot be merged into a workflow
    that already exists without either reformatting it or guessing which
    triggers should run them.
    """
    result = TextMerge(path=str(target / ".github" / "workflows" / CI_CALLER_NAME), kind="ci")
    if not source_ci.is_file():
        result.notes.append(f"{source_ci} does not exist; no CI caller added")
        return result
    try:
        caller, kept, dropped = ci_caller(source_ci.read_text(encoding="utf-8"))
    except FileMergeError as exc:
        result.notes.append(str(exc))
        return result
    destination = target / ".github" / "workflows" / CI_CALLER_NAME
    if destination.exists():
        result.notes.append(f"{destination.name} already exists; left alone")
        return result
    result.added = kept
    result.reported = dropped
    result.notes.append(CI_EXCLUDED_NOTE)
    result.notes.append(f"runs alongside your own ci.yml; delete whichever you do not want ({destination.name})")
    if apply:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(caller, encoding="utf-8")
        result.applied = True
    return result


def _jobs_are_the_last_block(target_text: str) -> bool:
    """True when `jobs:` is the final top-level key, so job blocks can be appended."""
    return _last_top_level_key(target_text) == "jobs"


def _workflow_jobs(text: str) -> dict[str, Any] | None:
    """The `jobs:` mapping of a workflow, or None when the text is not valid YAML."""
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    jobs = document.get("jobs") if isinstance(document, dict) else None
    return jobs if isinstance(jobs, dict) else {}


def _find_missing_ci_jobs(kept: list[str], dropped: list[str], target_text: str, result: TextMerge) -> list[str]:
    """Identify read-only CI jobs absent from the target workflow, recording status notes."""
    declared = set(_recipe_blocks(target_text, CI_JOB))
    missing = [name for name in kept if name not in declared]
    present = sorted(name for name in kept if name in declared)
    if present:
        result.notes.append(f"already in your workflow, left alone: {', '.join(present)}")
    if dropped:
        result.notes.append(CI_EXCLUDED_NOTE)
    if not missing:
        result.notes.append(
            "every read-only template job is already present"
            if kept
            else "the generated workflow has no read-only jobs to add"
        )
    return missing


def merge_ci_jobs(  # noqa: PLR0911  WHYNOT: each return is one guard of the report-vs-append decision, the shape the other merges share.
    target_ci: Path, source_ci: Path, *, append: bool = False
) -> TextMerge:
    """Report the read-only jobs the target's ci.yml is missing — and append them when asked.

    The other half of `ci_caller`: instead of a second workflow, the template's
    read-only jobs go straight into the adopter's own `jobs:` — only under the
    same safety rule as the Taskfile merge (`jobs:` must be the target's last
    top-level key) and verified by re-parsing (every job that was there must
    still be there, unchanged). Job names that already exist are theirs and are
    left alone; the publish jobs `ci_caller` drops are never appended either.
    """
    result = TextMerge(path=str(target_ci), kind="ci_jobs")
    if not source_ci.is_file():
        result.notes.append(f"{source_ci} does not exist; nothing to merge")
        return result
    if not target_ci.is_file():
        result.notes.append(f"{target_ci} does not exist; nothing to merge into")
        return result
    source_text = source_ci.read_text(encoding="utf-8")
    try:
        _, kept, dropped = ci_caller(source_text)
    except FileMergeError as exc:
        result.notes.append(str(exc))
        return result
    target_text = target_ci.read_text(encoding="utf-8")
    if _workflow_jobs(target_text) is None:
        result.notes.append(f"{target_ci} does not parse; nothing appended")
        return result
    missing = _find_missing_ci_jobs(kept, dropped, target_text, result)
    if not missing:
        return result
    if not append or not _jobs_are_the_last_block(target_text):
        result.reported = sorted(missing)
        reason = (
            "reported rather than appended" if not append else "not appended: jobs: is not the last block in the file"
        )
        result.notes.append(
            f"these are workflow jobs, {reason}; copy the ones you want from the generated ci.yml "
            "or keep copier-ci.yml alongside"
        )
        return result
    return _apply_ci_jobs_append(target_ci, target_text, source_text, missing, result)


def _apply_ci_jobs_append(
    target_ci: Path,
    target_text: str,
    source_text: str,
    missing: list[str],
    result: TextMerge,
) -> TextMerge:
    """Append missing CI jobs to target_ci and rollback if YAML structure alters."""
    blocks = _recipe_blocks(source_text, CI_JOB)
    before = _workflow_jobs(target_text) or {}
    appended = target_text if target_text.endswith("\n") else target_text + "\n"
    appended += "\n\n".join(blocks[name] for name in sorted(missing)) + "\n"
    target_ci.write_text(appended, encoding="utf-8")
    after = _workflow_jobs(appended)
    if (
        after is None
        or not all(name in after for name in missing)
        or not all(name in after and repr(after[name]) == repr(value) for name, value in before.items())
    ):
        target_ci.write_text(target_text, encoding="utf-8")
        result.notes.append("appending the jobs changed an existing one; undone")
        result.reported = sorted(missing)
        return result
    result.added = sorted(missing)
    result.applied = True
    return result


def merge_text_file(
    target_path: Path,
    source_path: Path,
    kind: str,
    *,
    apply: bool = True,
    append: bool = False,
) -> TextMerge:
    """Dispatch to the merge for `kind` (`gitignore`, `makefile`, `justfile`, `taskfile`, `python_tasks`)."""
    if kind == "gitignore":
        return merge_gitignore(target_path, source_path, apply=apply)
    if kind in ("makefile", "justfile"):
        return merge_recipes(target_path, source_path, kind, apply=apply)
    if kind == "taskfile":
        return merge_taskfile(target_path, source_path, append=append and apply)
    if kind == "python_tasks":
        return merge_python_tasks(target_path, source_path, append=append and apply)
    msg = f"unknown kind: {kind!r}"
    raise FileMergeError(msg)


def original_is_preserved(before: bytes, after: bytes) -> bool:
    """The invariant of every kind here: the old content is still a prefix."""
    return after.startswith(before)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append the missing entries of a template text file.")
    parser.add_argument("--target", type=Path, required=True, help="the adopter's file")
    parser.add_argument("--source", type=Path, required=True, help="the generated file to take entries from")
    parser.add_argument(
        "--kind",
        required=True,
        choices=["gitignore", "makefile", "justfile", "taskfile", "python_tasks", "ci_jobs"],
    )
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: merge (or report) and print what happened."""
    args = _parse_args(argv)
    result = merge_text_file(args.target, args.source, args.kind, apply=not args.dry_run)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
        return 0
    print(f"{args.target}: {result.kind}")
    if result.added:
        print(f"  added: {', '.join(result.added)}")
    if result.reported:
        print(f"  reported: {', '.join(result.reported)}")
    for note in result.notes:
        print(f"  note: {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
