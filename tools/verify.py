#!/usr/bin/env python3
"""Verify a generated project's composition contract (TODO §42-A2).

The manifest (`.daimonion-manifest.yml`, rendered from
`template/.daimonion-manifest.yml.jinja`) is the public record of a
generation: the template ref, the answers file it describes, and the ethics
sections the render distributed -- never answer values (those live in
`.copier-answers.yml`, which copier already records). `verify` reads both
files and checks the three claims the record makes:

(a) the manifest's schema version is one this tool knows;
(b) the manifest's ref agrees with the answers file's `_commit` stamp;
(c) optionally (`--against`), the composition drift between two trees: which
    ref, answers, and distributed sections changed.

Answer values are compared as a SET -- copier records only the asked
questions, so a key present on one side and absent on the other is a
rendered-vs-defaulted difference, not noise. Per-render stamps (`_commit`,
`_src_path`) are masked the way tools/batch.py compares renders: they name
the run, not the composition.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any

import yaml

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import batch  # noqa: E402
from tools.render_inputs import read_yaml_mapping  # noqa: E402

MANIFEST_NAME = batch.MANIFEST_FILE
ANSWERS_NAME = batch.ANSWERS_FILE

#: Manifest schema versions this tool reads. The template stamps
#: `manifest_schema_version: 1`; a manifest from a newer template is refused
#: loudly rather than half-read.
SUPPORTED_SCHEMA_VERSIONS = (1,)

OK = 0
FAILED = 1
INVALID = 2


class VerifyError(Exception):
    """The target cannot be verified as asked."""


def _load_yaml(path: Path, what: str) -> dict[str, Any]:
    """One YAML mapping from `path`, or a loud error naming what it should be."""
    try:
        return read_yaml_mapping(path)
    except OSError as exc:
        msg = f"cannot read {what} {path}: {exc}"
        raise VerifyError(msg) from exc
    except (TypeError, ValueError) as exc:
        msg = f"cannot parse {what} {path}: {exc}"
        raise VerifyError(msg) from exc


def load_manifest(target: Path) -> dict[str, Any]:
    """The composition record of the generated project at `target`."""
    manifest = target / MANIFEST_NAME
    if not manifest.is_file():
        msg = (
            f"{manifest} not found -- this project was generated before the composition "
            "contract existed (TODO §42-A2); regenerate it with `copier recopy --overwrite` "
            "to record one"
        )
        raise VerifyError(msg)
    return _load_yaml(manifest, "the composition manifest")


def load_answers(target: Path) -> dict[str, Any]:
    """The recorded answers of the generated project at `target`."""
    answers = target / ANSWERS_NAME
    if not answers.is_file():
        msg = f"{answers} not found -- not a generated project"
        raise VerifyError(msg)
    return _load_yaml(answers, "the answers file")


@dataclass
class Report:
    """The verdict of verifying one tree (and, with `--against`, its drift)."""

    target: Path
    ok: bool = True
    lines: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        """Record one failed check: it prints, and the exit code follows."""
        self.ok = False
        self.failures.append(message)
        self.lines.append(f"FAIL: {message}")

    def say(self, message: str) -> None:
        """Record one passing observation."""
        self.lines.append(message)

    def render(self) -> str:
        """The human-readable verification report."""
        verdict = "verify: ok" if self.ok else "verify: FAILED"
        return "\n".join([verdict, *self.lines])


def check_schema(manifest: dict[str, Any], report: Report) -> None:
    """Check (a): the manifest's schema version is one this tool reads."""
    version = manifest.get("manifest_schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        report.fail(
            f"manifest schema version {version!r} is not supported "
            f"(this tool reads {list(SUPPORTED_SCHEMA_VERSIONS)}) -- "
            "regenerate the project with a matching template"
        )


def _sections(manifest: dict[str, Any]) -> dict[str, str]:
    """The distributed sections as id -> version."""
    entries = manifest.get("ethics_sections") or []
    return {str(entry.get("id")): str(entry.get("version")) for entry in entries if isinstance(entry, dict)}


def check_ref(manifest: dict[str, Any], answers: dict[str, Any], report: Report) -> None:
    """Check (b): the manifest's ref agrees with the answers' `_commit` stamp."""
    ref = manifest.get("template_ref")
    commit = answers.get("_commit")
    if not ref:
        report.fail("the manifest records no template_ref -- regenerate the project")
        return
    if not commit:
        report.fail("the answers file records no _commit -- regenerate the project")
        return
    if str(ref) != str(commit):
        report.fail(f"template ref mismatch: manifest records {ref!r}, answers record {commit!r}")
        return
    report.say(f"template ref: {ref} (manifest and answers agree)")


def check_answers_pointer(manifest: dict[str, Any], target: Path, report: Report) -> None:
    """The manifest's answers_file names the answers record beside it."""
    pointer = manifest.get("answers_file", ANSWERS_NAME)
    if not (target / str(pointer)).is_file():
        report.fail(f"the manifest points at {pointer!r}, which is not in {target}")
        return
    report.say(f"answers file: {pointer}")


def _answers_body(answers: dict[str, Any]) -> dict[str, Any]:
    """The answers without copier's per-render stamps (tools/batch.py's set)."""
    return batch.answers_body(answers)


def _diff_lines(before: list[str], after: list[str]) -> list[str]:
    """The unified diff of two sorted line sets, without file headers."""
    return list(difflib.unified_diff(before, after, lineterm=""))[2:]


def _section_drift_lines(before: dict[str, str], after: dict[str, str], *, label: str) -> list[str]:
    """Added, removed and changed ethics sections between two compositions, in words."""
    lines = [
        f"{label} ethics section {'added' if section in after else 'removed'}: "
        f"{section} ({after.get(section, before.get(section))})"
        for section in sorted(set(before) ^ set(after))
    ]
    lines.extend(
        f"{label} ethics section changed: {section} {before[section]} -> {after[section]}"
        for section in sorted(set(before) & set(after))
        if before[section] != after[section]
    )
    return lines


def _answer_drift_lines(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """The unified diff of two answer sets (stamps excluded), indented for the report."""
    old_answers = yaml.safe_dump(_answers_body(before.pop("_answers", {})), sort_keys=True).splitlines()
    new_answers = yaml.safe_dump(_answers_body(after.pop("_answers", {})), sort_keys=True).splitlines()
    return [f"  {line}" for line in _diff_lines(old_answers, new_answers)]


def compare(before: dict[str, Any], after: dict[str, Any], *, label: str, report: Report) -> None:
    """Check (c): what changed between two manifests / answer sets.

    `label` names the comparison direction for the reader (e.g. "old -> new").
    An identical composition is reported as such -- silence would read as an
    unchecked step.
    """
    drifted = False
    if before.get("template_ref") != after.get("template_ref"):
        report.say(f"{label} template ref: {before.get('template_ref')} -> {after.get('template_ref')}")
        drifted = True
    section_lines = _section_drift_lines(_sections(before), _sections(after), label=label)
    for line in section_lines:
        report.say(line)
    drifted = drifted or bool(section_lines)
    answer_diff = _answer_drift_lines(before, after)
    if answer_diff:
        report.say(f"{label} answers changed:")
        report.lines.extend(answer_diff)
        drifted = True
    if not drifted:
        report.say(f"{label} no composition drift: same ref, answers and sections")


def verify(target: Path, *, against: Path | None = None) -> Report:
    """Verify the generated project at `target`, diffing against `against`.

    Raises `VerifyError` when a file the verification needs is missing or
    unreadable; check failures land on the report (exit 1), not in an
    exception.
    """
    report = Report(target=target)
    manifest = load_manifest(target)
    answers = load_answers(target)
    check_schema(manifest, report)
    check_ref(manifest, answers, report)
    check_answers_pointer(manifest, target, report)
    sections = _sections(manifest)
    report.say(f"ethics sections: {len(sections)} distributed ({', '.join(sorted(sections)) or 'none'})")
    if against is not None:
        other_manifest = load_manifest(against)
        other_answers = load_answers(against)
        compare(
            {**other_manifest, "_answers": other_answers},
            {**manifest, "_answers": answers},
            label=f"{against} -> {target}",
            report=report,
        )
    return report


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="daimonion verify",
        description="Verify a generated project's composition contract.",
    )
    parser.add_argument("dir", type=Path, help="generated project to verify")
    parser.add_argument(
        "--against",
        type=Path,
        default=None,
        help="compare against another generated project (reports what changed)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: verify one tree, optionally diffing it against another."""
    args = _parse_args(argv)
    try:
        report = verify(args.dir, against=args.against)
    except VerifyError as exc:
        print(str(exc), file=sys.stderr)
        return INVALID
    except OSError as exc:
        print(f"cannot verify {args.dir}: {exc}", file=sys.stderr)
        return INVALID
    print(report.render())
    return OK if report.ok else FAILED


if __name__ == "__main__":
    raise SystemExit(main())
