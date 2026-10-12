#!/usr/bin/env python3
"""Explain preset and answer choices from the questionnaire's own words (TODO §42-B2).

A first-time user should be able to judge one choice without reading the
whole feature catalogue. The single source of the explanation is the
questionnaire itself: `questions/*.yml` `help` text, the questions'
`choices` / `when` context, the preset files' leading comments, and
`support.yml`'s measured `why` lines. No explanation-only data file, no
second support table, no new choice catalogue -- the three public functions
below assemble prose from exactly those sources:

- `explain_preset`: one preset's answers, each with its "why this value".
- `explain_answer`: one question's help, its choices, and the `when` context
  that decides whether it is even asked.
- `explain_deviation`: "what changes if I pick something else" -- the
  dependents of the question, read from the question graph
  (`tools/question_graph.py`), never a hand-written branch.

The CLI (`tools/cli.py:explain`) and the MCP tool
(`tools/mcp_server.py:explain`) are thin shells over these functions; the
logic lives here so the wording has one owner.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import answers  # noqa: E402
from tools import question_graph  # noqa: E402
from tools import questionnaire  # noqa: E402
from tools import support_ledger  # noqa: E402

PRESETS = answers.PRESETS
"""The ready-made answer files `explain_preset` reads (same directory the CLI renders from)."""

#: Support-matrix rows worth flagging when an answer pair looks unsupported
#: (the one tiered-section list, shared with tools/suggest.py through
#: tools/support_ledger.py: the substring rule lives beside the scan).
SUPPORT_SECTIONS = support_ledger.TIERED_SECTIONS


class ExplainError(Exception):
    """The explanation cannot be given as asked (unknown preset, question, or value)."""


def available_presets() -> list[str]:
    """The names `--preset` accepts: the answer files under `presets/` (mirrors the CLI)."""
    return answers.preset_names(PRESETS)


def preset_description(name: str) -> str:
    """The preset file's leading comment (the family's one-line description)."""
    return answers.preset_description(name, PRESETS)


def preset_answers(name: str) -> dict[str, Any]:
    """The answers mapping of `presets/<name>.yml` (the same mapping a render uses)."""
    try:
        return answers.read_preset(name, PRESETS)
    except answers.PresetError as error:
        raise ExplainError(str(error)) from error


def _questions_by_name() -> dict[str, questionnaire.Question]:
    """The questionnaire keyed by question name, in ask order."""
    return questionnaire.questions_by_name()


def _question_or_raise(name: str) -> questionnaire.Question:
    """One question, or an error naming the closest valid names."""
    by_name = _questions_by_name()
    if name in by_name:
        return by_name[name]
    known = ", ".join(sorted(by_name))
    msg = f"unknown question {name!r}. Known questions: {known}"
    raise ExplainError(msg)


def _graph() -> question_graph.Graph:
    """The questionnaire dependency graph (the owner of when/default wiring)."""
    return question_graph.build_graph()


def _recommended_line(question: questionnaire.Question) -> str:
    """The question's `Recommended:` help line, or "" when it has none."""
    return next(
        (line.strip() for line in question.help.strip().splitlines() if line.strip().lower().startswith("recommended")),
        "",
    )


def _help_summary(question: questionnaire.Question) -> str:
    """The question's help, trimmed to its lead: the first line, plus a `Recommended:` line when present."""
    if not question.help.strip():
        return "(no help text)"
    first = question.help.strip().splitlines()[0].strip()
    recommended = _recommended_line(question)
    if recommended and recommended not in first:
        return f"{first} {recommended}"
    return first


def _choices_line(question: questionnaire.Question) -> str:
    """One line naming the valid values: static choices, or the template that narrows them."""
    if question.choices:
        return f"Valid values: {', '.join(str(choice) for choice in question.choices)}."
    if question.choices_template:
        return "Valid values: narrowed from earlier answers (a `choices:` template)."
    if question.type == "bool":
        return "Valid values: yes / no."
    return ""


def _support_notes(question: str, value: str | None) -> list[str]:
    """Support-matrix rows touching this question, with their measured `why`.

    Matches are textual (`name` and `value` both in the combination): the
    rows are prose, not a second machine, and `tools/gen_docs.py` already
    renders them the same way. `value=None` matches rows naming the question
    at all (the "which combinations involve this question" reading).
    """
    return support_ledger.rows_naming(question, value)


def _gate_line(question: questionnaire.Question) -> str:
    """When the question is asked, in words (its raw `when`, plus the gate it sits under)."""
    if question.internal:
        return "Derived internally (never asked; computed at render time)."
    if not question.when:
        return "Always asked."
    return f"Asked when `{question.when}`."


def _dependents_lines(question: str, graph: question_graph.Graph) -> list[str]:
    """The definitions reading `question`, grouped by question vs internal."""
    dependents = graph.dependents().get(question, [])
    if not dependents:
        return []
    by_name = graph.by_name
    asked = [name for name in dependents if by_name[name].kind == question_graph.QUESTION]
    derived = [name for name in dependents if by_name[name].kind == question_graph.INTERNAL]
    lines = [f"Affects {len(dependents)} definition(s):"]
    if asked:
        lines.append(f"  questions gated on it: {', '.join(asked)}")
    if derived:
        lines.append(f"  derived internals reading it: {', '.join(derived)}")
    return lines


def _edges_into(graph: question_graph.Graph, name: str) -> list[question_graph.Edge]:
    """Every when/default reference INTO `name` (what reads it, and through which field)."""
    return [edge for edge in graph.edges if edge.target == name]


def _choice_note(question: questionnaire.Question, value: str) -> str:
    """The warning when `value` is not among the question's listed choices, else ""."""
    if question.choices and value not in [str(choice) for choice in question.choices]:
        return f"Note: {value!r} is not among the listed choices -- copier would reject it."
    return ""


def _default_line(question: questionnaire.Question, value: str) -> str:
    """How `value` relates to the question's written default, or "" when there is none."""
    default = question.default
    if isinstance(default, str) and value == default:
        return f"{value!r} is the written default."
    if default is True and value in ("true", "yes"):
        return "`yes` is the written default (the recommended path)."
    if default is False and value in ("false", "no"):
        return "`no` is the written default."
    if default is not None and not isinstance(default, bool):
        return f"Written default: `{default}`."
    return ""


def _gated_lines(gated: list[str], by_name: dict[str, questionnaire.Question]) -> list[str]:
    """Each gated question with the `when` that reads the deviated answer."""
    lines: list[str] = []
    for source in gated:
        other = by_name.get(source)
        if other is not None and isinstance(other.when, str) and other.when.strip():
            lines.append(f"  - {source}: asked when `{other.when.strip()}`")
    return lines


def _impact_lines(question: str, graph: question_graph.Graph, by_name: dict[str, questionnaire.Question]) -> list[str]:
    """Which definitions read the deviated answer: gated questions and derived defaults."""
    edges = _edges_into(graph, question)
    if not edges:
        return ["No other question or internal reads this answer -- the change is local."]
    lines: list[str] = []
    gated = sorted({edge.source for edge in edges if edge.field == "when"})
    derived = sorted({edge.source for edge in edges if edge.field == "default"})
    if gated:
        lines.append(f"Questions asked / skipped because of it ({len(gated)}): {', '.join(gated)}")
        lines.extend(_gated_lines(gated, by_name))
    if derived:
        lines.append(f"Defaults derived from it ({len(derived)}): {', '.join(derived)}")
    return lines


def _support_block(question: str, value: str) -> list[str]:
    """The support verdict for a deviated pair: naming rows, or the honest absence."""
    notes = _support_notes(question, value)
    if notes:
        return ["Support rows naming this combination:", *(f"  - {note}" for note in notes)]
    return ["No support.yml row names this exact combination -- it renders, but no tier is promised."]


def explain_answer(question: str, value: str | None = None) -> str:
    """Why this question has this value: help, valid values, ask context, support rows.

    `value=None` explains the question itself (its recommended/default
    setting); a value adds the "why this value" reading: whether it is the
    default, whether it is a valid choice, and which support rows name it.
    """
    asked = _question_or_raise(question)
    lines = [f"{question}: {_help_summary(asked)}"]
    lines.append(_gate_line(asked))
    choices_line = _choices_line(asked)
    if choices_line:
        lines.append(choices_line)
    if value is not None:
        choice_note = _choice_note(asked, value)
        if choice_note:
            lines.append(choice_note)
        default_line = _default_line(asked, value)
        if default_line:
            lines.append(default_line)
    lines.extend(_support_notes(question, value))
    return "\n".join(lines)


def explain_deviation(question: str, value: str) -> str:
    """What changes when `question` takes `value` instead of the recommended one.

    The impact list is derived, not written: every definition whose `when` or
    `default` reads the question (the question graph's edges into it), split
    into asked questions (new prompts appear / disappear) and derived
    internals (render-time behaviour changes). Support rows naming the pair
    say whether the combination stays supported.
    """
    asked = _question_or_raise(question)
    graph = _graph()
    lines = [f"If {question} is {value!r} instead of the recommended setting:"]
    lines.append(f"Recommendation context: {_help_summary(asked)}")
    lines.extend(_impact_lines(question, graph, _questions_by_name()))
    lines.extend(_support_block(question, value))
    return "\n".join(lines)


def _preset_entry(
    key: str, pinned: Any, by_name: dict[str, questionnaire.Question], graph: question_graph.Graph
) -> list[str]:
    """One pinned answer with its reason: help, ask context, dependents, support rows."""
    lines = [f"{key} = {pinned!r}"]
    asked = by_name.get(key)
    if asked is None:
        return [*lines, "  (not a current questionnaire question -- kept for `copier update` stability)"]
    lines.append(f"  Why: {_help_summary(asked)}")
    lines.append(f"  {_gate_line(asked)}")
    lines.extend(f"  {line}" for line in _dependents_lines(key, graph))
    lines.extend(f"  {note}" for note in _support_notes(key, str(pinned)))
    lines.append("")
    return lines


def explain_preset(name: str) -> str:
    """Why this preset picks what it picks: each pinned answer with its reason.

    The answers are the `presets/<name>.yml` mapping (the same mapping a
    render uses); each answer's reason is its question's help plus the
    preset file's own leading comment (the file's one-line description of
    the family). Support rows naming the pinned pairs close each section.
    """
    answers = preset_answers(name)
    by_name = _questions_by_name()
    graph = _graph()
    lines = [f"Preset `{name}`: {preset_description(name)}", ""]
    for key, pinned in answers.items():
        lines.extend(_preset_entry(key, pinned, by_name, graph))
    left_default = [qname for qname in by_name if qname not in answers and not by_name[qname].internal]
    if left_default:
        lines.append(f"All other asked questions ({len(left_default)}) keep their copier defaults.")
    return "\n".join(lines).rstrip() + "\n"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """The `explain` argument shape (also used through the `daimonion explain` subcommand)."""
    parser = argparse.ArgumentParser(prog="daimonion explain", description=__doc__)
    parser.add_argument("--preset", default=None, help="explain one preset (e.g. --preset web-api)")
    parser.add_argument("question", nargs="?", default=None, help="question to explain (e.g. project_type)")
    parser.add_argument("value", nargs="?", default=None, help="value to explain (e.g. cli)")
    parser.add_argument(
        "--deviate",
        nargs=2,
        default=None,
        metavar=("QUESTION", "VALUE"),
        help="explain what changes if QUESTION takes VALUE (e.g. --deviate project_type web_api)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: print the requested explanation (exit 2 on unknown names)."""
    args = _parse_args(argv)
    try:
        if args.deviate:
            print(explain_deviation(args.deviate[0], args.deviate[1]))
        elif args.preset:
            print(explain_preset(args.preset))
        elif args.question:
            print(explain_answer(args.question, args.value))
        else:
            print("usage: daimonion explain --preset NAME | QUESTION [VALUE] | --deviate QUESTION VALUE")
            return 2
    except ExplainError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
