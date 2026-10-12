#!/usr/bin/env python3
"""Merge the template's dependencies and tool config into an adopter's pyproject.toml.

The template generates a `pyproject.toml` with the runtime and dev
dependencies a project needs, plus the tool config that makes its checks pass
(ruff, typos, pytest, coverage, ...); when it is adopted into an existing
project that file is protected (it is the adopter's), so all of it used to end
up only in the adoption report — "wire these up yourself". This module does
the additive half of that by hand instead:

- **add what is missing, never touch what is there.** A dependency the
  adopter already declares keeps its own specifier, even when the template
  would pin something different; the difference is reported, not resolved.
- **never reorder or reformat anything else.** The file is edited through
  tomlkit, which round-trips comments and layout.
- **report instead of guessing** when the file has no table to merge into
  (`[project]` for PEP 621, `[tool.poetry]` for the legacy Poetry layout),
  or when it does not parse.

For `[tool.*]` tables the same rule applies key by key, with one extra
exclusion: a value that names *this* project (a `src/<pkg>` path, the
package's import path, the distribution name) is not a setting to copy into
somebody else's file, so it is reported instead. That is what keeps
`basedpyright.include = ["src/probe"]` out of an adopter whose source lives
somewhere else, while `ruff.lint.select = ["ALL"]` still gets merged.

That is the boundary this stays on: no reconciliation of conflicting
constraints, no section-level rewriting of the adopter's configuration --
just the missing names and keys, appended.

Usage (normally through tools/adopt.py, which is the transactional caller):

    python tools/pyproject_merge.py --target /path/to/pyproject.toml --source generated/pyproject.toml
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from pathlib import Path
from typing import Any

import tomlkit

NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
REQUIREMENT = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?P<extras>\[[^\]]*\])?\s*(?P<spec>[^;]*?)(?P<marker>;.*)?$"
)


def canonical(spec: str) -> str:
    """The distribution name a requirement string refers to (PEP 503 style).

    `httpx>=0.27` -> `httpx`; `Foo_Bar[x,y]>=1` -> `foo-bar`. Used only to
    decide "is this already declared", so a false match costs a missing
    dependency (reported), never a modified one.
    """
    match = NAME.match(spec)
    if not match:
        return spec.strip()
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


@dataclass
class MergeResult:
    """What the merge added, kept, and refused to decide."""

    target: str
    style: str = "none"
    added: dict[str, list[str]] = field(default_factory=dict)
    kept: dict[str, list[str]] = field(default_factory=dict)
    differing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    applied: bool = False

    @property
    def added_names(self) -> list[str]:
        """Every dependency name that was added, in section order."""
        return [name for names in self.added.values() for name in names]

    def as_dict(self) -> dict[str, Any]:
        """Serializable form used by --json and tools/adopt.py."""
        return {
            "target": self.target,
            "style": self.style,
            "added": self.added,
            "kept": self.kept,
            "differing": self.differing,
            "notes": self.notes,
            "applied": self.applied,
        }


def _requirements(document: dict[str, Any], section: str) -> list[str]:
    """The PEP 508 requirement strings of one section of a parsed pyproject."""
    project = document.get("project")
    if not isinstance(project, dict):
        return []
    if section == "dependencies":
        entries = project.get("dependencies", [])
    elif section == "optional":
        return sorted(str(name) for name in project.get("optional-dependencies", {}))
    else:
        groups = document.get("dependency-groups")
        entries = groups.get(section, []) if isinstance(groups, dict) else []
    return [entry for entry in entries if isinstance(entry, str)]


def _source_requirements(source: dict[str, Any]) -> dict[str, list[str]]:
    """The template's dependencies, keyed by where they belong."""
    sections = {"runtime": _requirements(source, "dependencies"), "dev": _requirements(source, "dev")}
    return {name: entries for name, entries in sections.items() if entries}


def _to_poetry(requirement: str) -> tuple[str, str] | None:
    """`httpx>=0.27` -> `("httpx", ">=0.27")`, or None when that is not faithful.

    Poetry writes a plain specifier as the value; extras and environment
    markers need table syntax, so those requirements are reported instead of
    being guessed at.
    """
    match = REQUIREMENT.match(requirement)
    if not match or match.group("extras") or match.group("marker"):
        return None
    return match.group("name"), (match.group("spec").strip() or "*")


def _hand_wiring_note(label: str, section: Any, entries: Iterable[str]) -> str:
    """The note for a section whose shape the merge cannot add to.

    A parseable but malformed file (`dependencies = "httpx"`, `= 5`) must be a
    clean refusal - the append loop would otherwise raise AttributeError or
    TypeError from inside the merge.
    """
    return f"{label} is not a list or table ({type(section).__name__}); add these by hand: {', '.join(sorted(entries))}"


def _add_missing_to_mapping(
    target_section: Any,
    entries: dict[str, str],
    section: str,
    label: str | None,
    result: MergeResult,
) -> None:
    """Append missing mapping requirements to a table (e.g. Poetry style)."""
    if not isinstance(target_section, dict):
        result.notes.append(_hand_wiring_note(label or f"[{section}]", target_section, entries))
        return
    kept: list[str] = []
    added: list[str] = []
    present = {canonical(str(name)) for name in target_section}
    for name, value in entries.items():
        key = canonical(str(name))
        if key in present:
            kept.append(str(name))
            continue
        target_section[str(name)] = value
        present.add(key)
        added.append(str(name))
    if added:
        result.added[section] = added
    if kept:
        result.kept[section] = kept


def _add_missing_to_sequence(
    target_section: Any,
    entries: list[str],
    section: str,
    label: str | None,
    result: MergeResult,
) -> None:
    """Append missing string requirements to a list (PEP 621 style)."""
    if not isinstance(target_section, list):
        result.notes.append(_hand_wiring_note(label or f"[{section}]", target_section, entries))
        return
    kept: list[str] = []
    added: list[str] = []
    present = {canonical(str(item)) for item in target_section}
    for entry in entries:
        key = canonical(entry)
        if key in present:
            kept.append(entry)
            continue
        target_section.append(entry)
        present.add(key)
        added.append(entry)
    if added:
        result.added[section] = added
    if kept:
        result.kept[section] = kept


def _add_missing(
    target_section: Any,
    entries: list[str] | dict[str, str],
    result: MergeResult,
    section: str,
    label: str | None = None,
) -> None:
    """Append requirements the target does not declare; record what was kept."""
    if isinstance(entries, dict):
        _add_missing_to_mapping(target_section, entries, section, label, result)
    else:
        _add_missing_to_sequence(target_section, entries, section, label, result)


def _differing(target_section: Any, template: list[str]) -> list[str]:
    """Names declared by both sides with a different requirement string.

    A section that is not an array has no comparable names (the caller has
    already refused it with a note), so there is nothing to report.
    """
    if not isinstance(target_section, list):
        return []
    declared = {canonical(str(item)): str(item) for item in target_section}
    out = []
    for entry in template:
        name = canonical(entry)
        if name in declared and declared[name].strip() != entry.strip():
            out.append(f"{name}: kept {declared[name]!r}, template wanted {entry!r}")
    return out


def _merge_pep621(document: Any, source: dict[str, Any], result: MergeResult) -> None:
    """PEP 621: `[project].dependencies` plus a PEP 735 dev group."""
    result.style = "pep621"
    project = document["project"]
    template = _source_requirements(source)
    runtime = template.get("runtime", [])
    if runtime:
        if "dependencies" not in project:
            project["dependencies"] = tomlkit.array()
        _add_missing(project["dependencies"], runtime, result, "runtime", "[project] dependencies")
        result.differing += _differing(project["dependencies"], runtime)
    dev = template.get("dev", [])
    if dev:
        groups = document.get("dependency-groups")
        if groups is None:
            groups = tomlkit.table()
            document["dependency-groups"] = groups
            result.notes.append("created [dependency-groups] to hold the dev dependencies")
        if "dev" not in groups:
            groups["dev"] = tomlkit.array()
        _add_missing(groups["dev"], dev, result, "dev", "[dependency-groups] dev")
        result.differing += _differing(groups["dev"], dev)
    optional = _requirements(source, "optional")
    if optional:
        result.notes.append(f"optional extras not merged (opt in per project): {', '.join(optional)}")


def _merge_poetry(document: Any, source: dict[str, Any], result: MergeResult) -> None:
    """Legacy Poetry layout: dependencies live under `[tool.poetry]`."""
    result.style = "poetry"
    poetry = document["tool"]["poetry"]
    template = _source_requirements(source)
    translated: dict[str, dict[str, str]] = {"runtime": {}, "dev": {}}
    for section, table in translated.items():
        for requirement in template.get(section, []):
            converted = _to_poetry(requirement)
            if converted is None:
                result.notes.append(f"needs manual wiring (Poetry table syntax): {requirement}")
                continue
            table[converted[0]] = converted[1]
    if translated["runtime"]:
        if "dependencies" not in poetry:
            poetry["dependencies"] = tomlkit.table()
        _add_missing(poetry["dependencies"], translated["runtime"], result, "runtime", "[tool.poetry.dependencies]")
    if translated["dev"]:
        group = poetry.get("group", {}).get("dev", {})
        table = group.get("dependencies") if isinstance(group, dict) else None
        if table is None:
            table = poetry.get("dev-dependencies")
        if table is None:
            result.notes.append("no [tool.poetry.group.dev.dependencies]; dev dependencies not merged")
        else:
            _add_missing(table, translated["dev"], result, "dev", "[tool.poetry.group.dev.dependencies]")


def _load_pyproject_merge_documents(
    target_path: Path, source_path: Path, result: MergeResult
) -> tuple[tomlkit.TOMLDocument | None, dict[str, Any] | None]:
    """Load and parse target and source pyproject files, recording notes on failure."""
    if not target_path.is_file():
        result.notes.append(f"{target_path} does not exist; nothing to merge")
        return None, None
    if not source_path.is_file():
        result.notes.append(f"{source_path} does not exist; nothing to merge")
        return None, None
    try:
        document = tomlkit.parse(target_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001  WHYNOT: tomlkit raises its own parse errors; the caller reports them.
        result.notes.append(f"{target_path} does not parse ({exc}); left untouched")
        return None, None
    try:
        source = tomllib.loads(source_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        result.notes.append(f"{source_path} does not parse ({exc}); nothing to merge")
        return None, None
    return document, source


def _dispatch_dependency_merge(document: tomlkit.TOMLDocument, source: dict[str, Any], result: MergeResult) -> bool:
    """Merge dependencies according to target style (PEP 621 or Poetry); return True if recognized."""
    if isinstance(document.get("project"), dict):
        _merge_pep621(document, source, result)
        return True
    if isinstance(document.get("tool"), dict) and "poetry" in document["tool"]:
        _merge_poetry(document, source, result)
        return True
    result.style = "none"
    template = _source_requirements(source)
    result.notes.append(
        "no [project] or [tool.poetry] table to merge into; add these by hand: "
        + ", ".join(template.get("runtime", []) + template.get("dev", []))
    )
    return False


def merge_dependencies(target_path: Path, source_path: Path, *, apply: bool = True) -> MergeResult:
    """Add the template's missing dependencies to `target_path`.

    `apply=False` computes exactly the same result without writing; the caller
    (tools/adopt.py) uses that for its dry run and for its report.
    """
    result = MergeResult(target=str(target_path))
    document, source = _load_pyproject_merge_documents(target_path, source_path, result)
    if document is None or source is None:
        return result

    if not _dispatch_dependency_merge(document, source, result):
        return result

    if not result.added_names:
        result.notes.append("every template dependency is already declared")
    if apply and (result.added_names or result.notes):
        target_path.write_text(tomlkit.dumps(document), encoding="utf-8")
        result.applied = True
    return result


BUILD_TOOLS = frozenset(
    {
        "setuptools",
        "setuptools_scm",
        "uv",
        "pixi",
        "poetry",
        "pdm",
        "hatch",
        "flit",
        "maturin",
        "cibuildwheel",
    }
)


@dataclass
class ConfigMerge:
    """What the tool-config merge added, kept, and refused to copy."""

    added: dict[str, list[str]] = field(default_factory=dict)
    kept: list[str] = field(default_factory=list)
    needs_your_value: list[str] = field(default_factory=list)
    skipped_tables: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    applied: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serializable form used by --json and tools/adopt.py."""
        return {
            "added": self.added,
            "kept": self.kept,
            "needs_your_value": self.needs_your_value,
            "skipped_tables": self.skipped_tables,
            "notes": self.notes,
            "applied": self.applied,
        }


def _mentions_identity(text: str, identity: tuple[str, ...]) -> bool:
    return any(token and token in text for token in identity)


def _is_project_specific(key: str, value: Any, identity: tuple[str, ...]) -> bool:
    """True when a value describes the generated project rather than the tool."""
    if _mentions_identity(key, identity):
        return True
    items = value if isinstance(value, list) else [value]
    for item in items:
        if not isinstance(item, str):
            continue
        if _mentions_identity(item, identity) or "/" in item:
            return True
    return False


def _leaf_items(table: Any) -> list[tuple[str, Any]]:
    return [(str(key), value) for key, value in table.items()]


@dataclass(frozen=True)
class _ConfigContext:
    """What the recursion needs to know about the adopter's project."""

    table_path: str
    identity: tuple[str, ...]
    result: ConfigMerge
    approved: frozenset[str] = frozenset()


def _merge_config_table(target_table: Any, source_table: Any, path: str, context: _ConfigContext) -> None:
    for key, value in _leaf_items(source_table):
        key_path = f"{path}.{key}"
        if isinstance(value, dict):
            if key in BUILD_TOOLS:
                if path == "tool":
                    context.result.skipped_tables.append(key_path)
                continue
            if key not in target_table:
                target_table[key] = tomlkit.table()
            _merge_config_table(target_table[key], value, key_path, replace(context, table_path=key_path))
            continue
        _merge_config_key(target_table, key, value, key_path, context)


def _merge_config_key(target_table: Any, key: str, value: Any, key_path: str, context: _ConfigContext) -> None:
    """Add one leaf key, or explain why it was not copied."""
    if key_path not in context.approved and _is_project_specific(key_path, value, context.identity):
        context.result.needs_your_value.append(f"{key_path} (template: {value!r})")
        return
    if key not in target_table:
        target_table[key] = value
        context.result.added.setdefault(context.table_path, []).append(key)
        return
    existing = target_table[key]
    if repr(existing) == repr(value):
        return
    if isinstance(existing, list) and isinstance(value, list):
        extra = [str(item) for item in value if item not in existing]
        detail = f"{key_path}: kept yours; template also has {extra}"
        missing = [str(item) for item in existing if item not in value]
        if missing:
            detail += f"; yours only: {missing}"
        context.result.kept.append(detail)
        return
    context.result.kept.append(f"{key_path}: kept {existing!r} (template: {value!r})")


def _load_tool_documents(
    target_path: Path, source_path: Path, result: ConfigMerge
) -> tuple[tomlkit.TOMLDocument | None, dict[str, Any] | None]:
    """Load and parse target and source documents for tool config merging."""
    if not target_path.is_file() or not source_path.is_file():
        return None, None
    try:
        document = tomlkit.parse(target_path.read_text(encoding="utf-8"))
        source = tomllib.loads(source_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001  WHYNOT: tomlkit and tomllib raise their own parse errors; the caller reports them.
        result.notes.append(f"tool config not merged ({exc})")
        return None, None
    return document, source


def _finalize_tool_merge_notes(result: ConfigMerge) -> None:
    """Add explanatory notes for skipped tables and no-op merges."""
    if result.skipped_tables:
        result.notes.append(
            "not merged (build/environment config; wire by hand if you want it): " + ", ".join(result.skipped_tables)
        )
    if not result.added and not result.kept and not result.needs_your_value:
        result.notes.append("no tool config to add")


def merge_tool_config(
    target_path: Path,
    source_path: Path,
    *,
    identity: tuple[str, ...] = (),
    approved: frozenset[str] = frozenset(),
    apply: bool = True,
) -> ConfigMerge:
    """Add the template's missing `[tool.*]` keys to `target_path`.

    Only keys the target does not have are written; a key it does have is
    reported, never rewritten. Values that name the generated project are
    reported too (see `_is_project_specific`), and tables that describe how a
    project is built or resolved are skipped: their values encode this
    template's layout and index choices, not a lint preference.
    """
    result = ConfigMerge()
    document, source = _load_tool_documents(target_path, source_path, result)
    if document is None or source is None:
        return result
    source_tool = source.get("tool")
    if not isinstance(source_tool, dict) or not source_tool:
        return result
    if not isinstance(document.get("tool"), dict):
        document["tool"] = tomlkit.table()
    _merge_config_table(
        document["tool"],
        source_tool,
        "tool",
        _ConfigContext(table_path="tool", identity=tuple(identity), result=result, approved=approved),
    )
    _finalize_tool_merge_notes(result)
    if apply and (result.added or result.notes):
        target_path.write_text(tomlkit.dumps(document), encoding="utf-8")
        result.applied = True
    return result


def declared_values(document: dict[str, Any]) -> dict[str, str]:
    """Every requirement and `[tool.*]` leaf value, as path -> repr.

    Used to verify an edit: everything in here must still be there, unchanged,
    after the merge.
    """
    found: dict[str, str] = {}
    for keys in (
        ("project", "dependencies"),
        ("dependency-groups", "dev"),
        ("tool", "poetry", "dependencies"),
        ("tool", "poetry", "dev-dependencies"),
    ):
        node: Any = document
        for key in keys:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, list):
            for entry in node:
                if isinstance(entry, str):
                    found.setdefault(f"{'.'.join(keys)}::{canonical(entry)}", entry)
        elif isinstance(node, dict):
            for name, value in node.items():
                found.setdefault(f"{'.'.join(keys)}::{canonical(str(name))}", repr(value))

    tool = document.get("tool")
    if isinstance(tool, dict):
        _collect_leaves(tool, "tool", found)
    return found


def _collect_leaves(table: dict[str, Any], path: str, found: dict[str, str]) -> None:
    for key, value in table.items():
        key_path = f"{path}.{key}"
        if isinstance(value, dict):
            _collect_leaves(value, key_path, found)
        else:
            found.setdefault(key_path, repr(value))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add the template's missing dependencies to a pyproject.toml.")
    parser.add_argument("--target", type=Path, required=True, help="the adopter's pyproject.toml")
    parser.add_argument(
        "--source", type=Path, required=True, help="the generated pyproject.toml to take dependencies from"
    )
    parser.add_argument(
        "--identity", action="append", default=None, help="name/path token to treat as project-specific"
    )
    parser.add_argument("--tool-config", action="store_true", help="merge [tool.*] keys as well as dependencies")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: merge (or report) and print what happened."""
    args = _parse_args(argv)
    result = merge_dependencies(args.target, args.source, apply=not args.dry_run)
    config = None
    if args.tool_config:
        config = merge_tool_config(
            args.target, args.source, identity=tuple(args.identity or ()), apply=not args.dry_run
        )
    if args.json:
        payload = result.as_dict()
        if config is not None:
            payload["tool_config"] = config.as_dict()
        print(json.dumps(payload, indent=2))
        return 0
    print(f"{args.target}: {result.style}")
    for section, names in result.added.items():
        print(f"  added {section}: {', '.join(names)}")
    for section, names in result.kept.items():
        print(f"  kept  {section}: {', '.join(names)}")
    for line in result.differing:
        print(f"  differs: {line}")
    for note in result.notes:
        print(f"  note: {note}")
    _print_config(config)
    return 0


def _print_config(config: ConfigMerge | None) -> None:
    if config is None:
        return
    for table, keys in config.added.items():
        print(f"  added [{table}]: {', '.join(keys)}")
    for line in config.kept:
        print(f"  kept: {line}")
    for line in config.needs_your_value:
        print(f"  needs your value: {line}")
    for note in config.notes:
        print(f"  note: {note}")


if __name__ == "__main__":
    raise SystemExit(main())
