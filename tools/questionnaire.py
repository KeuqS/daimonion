#!/usr/bin/env python3
"""Read this template's questionnaire as data.

Copier's questionnaire is YAML that only copier reads: fragments spliced in
with `!include`, block-scalar help text, defaults that are themselves Jinja
expressions, and a `when: false` marker that means "internal variable". Tools
that need to talk about the questionnaire -- the MCP server, the docs
generator, the witness matrix -- should not re-parse that by hand, and should
not guess the ask order.

This module resolves the includes in the same order copier merges them, so
the returned list *is* the ask order, and keeps the raw field values (the
defaults are templates; they are reported as written, not evaluated).

It is the one parser for this questionnaire: tools/when_model.py layers the
`when`-expression semantics on the raw view exposed here
(`load_raw_questions`), and copier's own `load_template_config` stays only a
differential oracle in tests (which pin that the two agree).

Usage:
    python tools/questionnaire.py           # one line per question
    python tools/questionnaire.py --json    # full records
    python tools/questionnaire.py --names   # just the ask order
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

TOP = Path(__file__).resolve().parent.parent
CONFIG = TOP / "copier.yml"
DOCUMENT_SPLIT = re.compile(r"(?m)^---\s*$")
INCLUDE_LINE = re.compile(r"^\s*!include\s+(\S+)\s*$")


def _significant_lines(chunk: str) -> list[str]:
    """Document lines that are neither blank nor comments."""
    return [line for line in chunk.splitlines() if line.strip() and not line.strip().startswith("#")]


def _include_target(chunk: str) -> str | None:
    """The path when a document is nothing but comments and one `!include`.

    The include is usually preceded by a comment explaining it (and comments
    elsewhere mention `!include` in prose), so this looks at the significant
    lines rather than at the first character or a substring search.
    """
    significant = _significant_lines(chunk)
    if len(significant) == 1:
        match = INCLUDE_LINE.match(significant[0])
        if match:
            return match.group(1)
    return None


class QuestionnaireError(Exception):
    """The questionnaire cannot be read as data."""


class TolerantLoader(yaml.SafeLoader):
    """SafeLoader that ignores copier's custom tags instead of failing.

    The one tolerant loader for the questionnaire's YAML: tools/detect.py's
    `_skip_if_exists` read uses it too.
    """


TolerantLoader.add_multi_constructor("!", lambda _loader, _suffix, _node: None)


@dataclass(frozen=True)
class Question:
    """One questionnaire entry, as written."""

    name: str
    type: str | None
    default: Any
    when: Any
    help: str
    choices: list[Any]
    labels: list[str] | None
    choices_template: str | None
    source: str

    @property
    def internal(self) -> bool:
        """True for `when: false` entries: derived variables, never asked."""
        return self.when is False

    def as_dict(self) -> dict[str, Any]:
        """Serializable form used by --json and the MCP tools."""
        return {
            "name": self.name,
            "type": self.type,
            "default": self.default,
            "when": self.when,
            "help": self.help,
            "choices": self.choices,
            "choice_labels": self.labels,
            "choices_template": self.choices_template,
            "source": self.source,
            "internal": self.internal,
        }


def _load_document(text: str, source: str) -> list[tuple[str, Any]]:
    """Top-level (key, value) pairs of one YAML document, in order."""
    try:
        data = yaml.load(text, Loader=TolerantLoader)  # noqa: S506  WHYNOT: TolerantLoader subclasses SafeLoader; it only stops copier's tags from raising.
    except yaml.YAMLError as exc:
        msg = f"{source}: cannot parse: {exc}"
        raise QuestionnaireError(msg) from exc
    if data is None:
        return []
    if not isinstance(data, dict):
        msg = f"{source}: expected a mapping at the top level"
        raise QuestionnaireError(msg)
    return [(str(key), value) for key, value in data.items()]


def _split_documents(text: str) -> list[str]:
    return [chunk for chunk in DOCUMENT_SPLIT.split(text) if chunk.strip()]


def _parse_fragment(path: Path) -> list[tuple[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if any(INCLUDE_LINE.match(line) for line in _significant_lines(text)):
        msg = f"{path}: nested !include is not supported (copier.yml owns the includes)"
        raise QuestionnaireError(msg)
    return [(name, details) for chunk in _split_documents(text) for name, details in _load_document(chunk, str(path))]


def _choice_values(details: dict[str, Any]) -> tuple[list[Any], list[str] | None, str | None]:
    """Normalise `choices` to the values an answer takes, plus labels.

    A block-scalar `choices` is a template that renders a YAML list once the
    earlier answers are known (`package_manager` narrows itself for ros2+apt,
    `oj_kind` depends on `oj_category`), so it cannot be resolved here: it is
    returned as `choices_template` instead of being dropped or guessed.
    """
    raw = details.get("choices")
    if raw is None:
        return [], None, None
    if isinstance(raw, dict):
        return list(raw.values()), [str(label) for label in raw], None
    if isinstance(raw, list):
        return list(raw), None, None
    if isinstance(raw, str):
        return [], None, raw.strip()
    msg = f"choices must be a list, a mapping or a template string, got {type(raw).__name__}"
    raise QuestionnaireError(msg)


def _read_entries(config: Path) -> tuple[list[tuple[str, Any, str]], dict[str, Any]]:
    """One parsing pass: ((name, raw value, source) triples in ask order, settings).

    The shared pass both views project: `load_questions` builds its Question
    records from it and `load_raw_questions` takes the raw values verbatim.
    A source names the document a question came from (`a.yml` for an included
    fragment, `copier.yml#3` for an inline one); settings are the
    underscore-prefixed keys (`_subdirectory`, `_tasks`, `_migrations`, ...),
    which are not questions.
    """
    entries: list[tuple[str, Any, str]] = []
    for index, chunk in enumerate(_split_documents(config.read_text(encoding="utf-8"))):
        included = _include_target(chunk)
        if included:
            target = (config.parent / included).resolve()
            if not target.is_file():
                msg = f"{config}: included file not found: {included}"
                raise QuestionnaireError(msg)
            entries.extend((name, details, target.name) for name, details in _parse_fragment(target))
            continue
        if any(INCLUDE_LINE.match(line) for line in _significant_lines(chunk)):
            msg = f"{config.name}: !include must be the only content of its document"
            raise QuestionnaireError(msg)
        source = f"{config.name}#{index + 1}"
        entries.extend((name, details, source) for name, details in _load_document(chunk, source))

    settings: dict[str, Any] = {name: raw for name, raw, _source in entries if name.startswith("_")}
    return entries, settings


def load_questions(config: Path | None = None) -> tuple[list[Question], dict[str, Any]]:
    """Return (questions in ask order, template settings).

    Settings are the underscore-prefixed keys (`_subdirectory`, `_tasks`,
    `_migrations`, ...); they are not questions and are kept separate.
    """
    config = config or CONFIG
    entries, settings = _read_entries(config)

    questions: list[Question] = []
    for name, raw, source in entries:
        if name.startswith("_"):
            continue  # already collected into settings
        details: dict[str, Any] = raw if isinstance(raw, dict) else {}
        choices, labels, choices_template = _choice_values(details)
        questions.append(
            Question(
                name=name,
                type=details.get("type"),
                default=details.get("default"),
                when=details.get("when"),
                help=str(details.get("help", "")).strip(),
                choices=choices,
                labels=labels,
                choices_template=choices_template,
                source=source,
            )
        )
    if not questions:
        msg = f"{config}: no questions found"
        raise QuestionnaireError(msg)
    return questions, settings


def load_raw_questions(config: Path | None = None) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return ({question-name: raw-details}, question names in ask order).

    The raw view of the same parse `load_questions` runs: non-underscore,
    dict-valued top-level entries with their details exactly as written, in
    ask order -- the resolved shape copier itself asks in. This is the view
    tools/when_model.py serves to its callers (its `when` semantics are
    layered on it), so the `!include` chain is resolved in exactly one place.
    """
    entries, _settings = _read_entries(config or CONFIG)
    questions = {name: raw for name, raw, _source in entries if not name.startswith("_") and isinstance(raw, dict)}
    return questions, list(questions)


def questions_by_name(config: Path | None = None) -> dict[str, Question]:
    """The questionnaire keyed by question name, in ask order."""
    questions, _settings = load_questions(config)
    return {question.name: question for question in questions}


def counts(config: Path | None = None) -> tuple[int, int, list[str]]:
    """(question count, asked-question count, sorted setting names), in one parse."""
    questions, settings = load_questions(config)
    return len(questions), sum(1 for question in questions if not question.internal), sorted(settings)


def schema_entries(*, asked_only: bool = False, config: Path | None = None) -> list[dict[str, Any]]:
    """The questions a proposal may answer, as serializable records in ask order.

    The same records `load_questions` parses -- the one parser, no second
    loader. `asked_only=True` drops the `when: false` derived variables an
    answer set must never name; the default keeps them, marked
    `internal: true`, so a client can tell "unknown question" from "derived
    variable you must not answer".
    """
    questions, _settings = load_questions(config)
    return [question.as_dict() for question in questions if not (asked_only and question.internal)]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read the questionnaire as data.")
    parser.add_argument("--config", type=Path, default=CONFIG, help="copier.yml to read")
    parser.add_argument("--json", action="store_true", help="print full records as JSON")
    parser.add_argument("--names", action="store_true", help="print only the ask order")
    parser.add_argument("--asked", action="store_true", help="skip internal (when: false) variables")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: print the questionnaire in the requested shape."""
    args = _parse_args(argv)
    try:
        questions, settings = load_questions(args.config)
    except (QuestionnaireError, OSError) as exc:
        print(f"cannot read questionnaire: {exc}", file=sys.stderr)
        return 2
    if args.asked:
        questions = [question for question in questions if not question.internal]

    if args.json:
        print(json.dumps({"questions": [q.as_dict() for q in questions], "settings": settings}, indent=2, default=str))
    elif args.names:
        print("\n".join(question.name for question in questions))
    else:
        for question in questions:
            kind = "internal" if question.internal else str(question.type)
            default = f" = {question.default!r}" if question.default is not None else ""
            print(f"{question.name:<28} {kind:<10} {question.source}{default}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
