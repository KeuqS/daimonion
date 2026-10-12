#!/usr/bin/env python3
"""A constrained configuration assistant: propose presets and answers, validate them mechanically.

TODO §42-B1. A user (or an LLM agent) says what the project needs --
"an internal API with Postgres on GitHub Actions" -- and proposes an answer
set for the questionnaire. This module is the gate that proposal passes
through, and it never invents answers of its own:

- `questionnaire_schema` publishes the questions (and only the questions) a
  proposal may answer: name, type, choices, help, when, default.
- `validate_answers` runs a proposed answer set through copier's OWN
  questionnaire pass (`Worker._ask`, the tests/test_when_model.py oracle
  pattern) instead of re-implementing validation: an unknown question, a
  value outside the choices, a validator failure, an answer to a question
  copier would never ask, or a layer include on a base that cannot carry it
  is rejected with a machine-readable {question, reason} list.
- `suggest_presets` is the deterministic, model-free half: keyword matches
  of the requirement words against each preset's pinned-answer signals
  (`_preset_signals`, never comment prose). No LLM, no network, no render --
  just a ranking with reasons.

The CLI (`tools/cli.py:suggest`) and the two MCP tools
(`tools/mcp_server.py:suggest_config`, `:validate_answers`) are thin shells
over these three functions; the logic lives here so the wording has one
owner (the tools/explain.py precedent).

The questionnaire itself is untouched: copier's ask-time `when` semantics,
the `combinable` / `has_*` render-time guards (questions/_combo.yml) and the
support.yml refusal rules are reused, never re-spelled. The question order
and the no-model CLI/questionnaire path keep working exactly as before.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any

from copier._main import Worker
from copier._user_data import Question

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import answers  # noqa: E402
from tools import questionnaire  # noqa: E402
from tools import support_ledger  # noqa: E402
from tools.render_inputs import read_yaml_mapping  # noqa: E402

PRESETS = answers.PRESETS
"""The ready-made answer files `suggest_presets` ranks (same directory the CLI renders from)."""


_TOKEN = re.compile(r"[a-z0-9]+")
"""Word tokens of a requirement string: lowercased alphanumerics."""

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "the",
        "with",
        "for",
        "our",
        "team",
        "needs",
        "need",
        "want",
        "wants",
        "project",
        "internal",
        "company",
        "please",
        "new",
        "using",
        "use",
        "plus",
        "that",
        "this",
        "build",
        "create",
        "make",
        "app",
    }
)
"""Filler words that would otherwise match every preset's comment."""

#: Requirement token -> (preset signal, human reason). Each key is matched
#: against the token set of the requirement words; the value names what the
#: preset must carry for the weight to count, and the reason the report shows.
#: Kept minimal on purpose: these are the families presets/*.yml pins, not a
#: feature catalogue.
_KEYWORDS: dict[str, tuple[str, str]] = {
    "api": ("web_api", "serves an API (web-api scaffold)"),
    "rest": ("web_api", "serves an API (web-api scaffold)"),
    "fastapi": ("web_api", "serves an API (web-api scaffold)"),
    "service": ("web_api", "runs as a service (web-api scaffold)"),
    # The web-api family is the database-backed stack (SQLAlchemy + Alembic
    # per support.yml's measured `why`): a Postgres requirement names it,
    # not a new catalogue entry.
    "postgres": ("web_api", "needs Postgres (the web-api stack's database)"),
    "database": ("web_api", "needs a database (the web-api stack's database)"),
    "sql": ("web_api", "needs a database (the web-api stack's SQL layer)"),
    "data": ("data", "works with datasets (data-science layout)"),
    "analysis": ("data", "works with datasets (data-science layout)"),
    "notebook": ("data", "works with notebooks (data-science layout)"),
    "ml": ("data", "works with datasets (data-science layout)"),
    "bot": ("bot", "runs a chat bot (bot layer)"),
    "discord": ("bot", "runs a Discord bot (bot layer)"),
    "slack": ("bot", "runs a Slack bot (bot layer)"),
    "chat": ("bot", "runs a chat bot (bot layer)"),
    "mcp": ("mcp", "serves MCP tools (mcp layer)"),
    "cli": ("cli", "ships a command-line entry point"),
    "command": ("cli", "ships a command-line entry point"),
    "tool": ("cli", "ships a command-line entry point"),
    "firmware": ("micropython", "targets microcontroller firmware"),
    "esp32": ("micropython", "targets microcontroller firmware"),
    "micropython": ("micropython", "targets microcontroller firmware"),
    "ros": ("ros2", "integrates with ROS 2"),
    "robot": ("ros2", "integrates with ROS 2"),
    "judge": ("oj", "is a competitive-programming workspace"),
    "atcoder": ("oj:atcoder", "targets AtCoder"),
    "codeforces": ("oj:codeforces", "targets Codeforces"),
    "kattis": ("oj:kattis", "targets Kattis"),
    # scraping/ctf keywords were removed: no preset pins include_scraping or
    # include_ctf, so those signals could never rank a preset (TODO review).
    "library": ("library", "ships as an importable library"),
    "package": ("library", "ships as an importable library"),
}


def questionnaire_schema(*, asked_only: bool = False) -> dict[str, Any]:
    """The questions a proposal may answer, as {name, type, choices, help, when, default}.

    The same records tools/questionnaire.py parses from copier.yml plus
    questions/*.yml -- the one parser, no second loader. `asked_only=True`
    keeps the MCP's working set small (drops the `when: false` derived
    variables an answer set must never name); the default keeps them, marked
    `internal: true`, so a client can tell "unknown question" from "derived
    variable you must not answer".
    """
    entries = questionnaire.schema_entries(asked_only=asked_only)
    return {"count": len(entries), "questions": entries}


@dataclass
class ValidationResult:
    """The verdict of `validate_answers`: accepted or not, with per-question reasons."""

    ok: bool
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """The MCP/JSON payload: {"ok", "errors"} with errors in questionnaire order."""
        return {"ok": self.ok, "errors": list(self.errors)}


def _closest(name: str, known: list[str], limit: int = 3) -> list[str]:
    """The closest known question names, for the unknown-question hint."""
    return difflib.get_close_matches(name, known, n=limit, cutoff=0.5)


def _base_is_promised(support: dict[str, Any], project_type: str) -> bool:
    """Whether any support.yml row carries the `project_type` base to a tier."""
    return support_ledger.base_is_promised(support, project_type)


def _support_note(answers: dict[str, Any]) -> str | None:
    """The support.yml row the answer set names without a tier promise, if any.

    Matches textually (the tools/explain.py precedent): a row is "named" when
    the combination mentions the project_type value, and no row carries the
    stated pair to a tier. Returns the warning line, or None when some row
    does promise the combination.
    """
    try:
        support = support_ledger.load_support()
    except (OSError, support_ledger.SupportLedgerError):
        return None
    project_type = str(answers.get("project_type") or "")
    if not project_type or _base_is_promised(support, project_type):
        return None  # some tier promises this base; not our warning to give
    return (
        f"project_type {project_type!r} is not named by any support.yml row: "
        "it renders, but no tier is promised (see docs/reference/support.md)"
    )


def _unknown_errors(answers: dict[str, Any], by_name: dict[str, questionnaire.Question]) -> list[dict[str, str]]:
    """One rejection per key no question declares (copier would silently render the default)."""
    errors: list[dict[str, str]] = []
    for name in sorted(set(answers) - set(by_name)):
        hint = _closest(name, sorted(by_name))
        reason = f"unknown question {name!r}: copier would ignore it and render the default"
        if hint:
            reason += f"; did you mean {', '.join(hint)}?"
        errors.append({"question": name, "reason": reason})
    return errors


def _internal_errors(answers: dict[str, Any], by_name: dict[str, questionnaire.Question]) -> list[dict[str, str]]:
    """One rejection per key naming a derived (`when: false`) internal."""
    return [
        {
            "question": name,
            "reason": (
                f"{name!r} is a derived internal (when: false): it is computed at render time and must not be answered"
            ),
        }
        for name in sorted(set(answers) & set(by_name), key=list(by_name).index)
        if by_name[name].internal
    ]


def _copier_pass(
    known: dict[str, Any], by_name: dict[str, questionnaire.Question], order: dict[str, int]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Run copier's own questionnaire pass: (fatal verdicts, ask-time rejections).

    Fatal verdicts are copier's own choice/validator rejections from `_ask`
    (non-empty means the pass stopped: no ask-time checks run). Ask-time
    rejections are the unasked-question and non-combinable errors read off
    the completed pass.
    """
    fatal: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="suggest-validate-") as dst:
        worker = Worker(src_path=str(TOP), dst_path=Path(dst), defaults=True, quiet=True, vcs_ref="HEAD")
        worker.data = dict(known)
        try:
            worker._ask()  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]  WHYNOT: copier exposes no other way to run its questionnaire pass (tests/test_when_model.py precedent).
        except (ValueError, TypeError) as exc:
            fatal.append({"question": _question_of(str(exc)), "reason": str(exc)})
            return fatal, []
        context = worker._render_context()  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]  WHYNOT: same.
        ask_time = _unasked_errors(worker, context, known, by_name, order)
        if not bool(context.get("combinable", True)):
            ask_time.extend(_non_combinable_errors(known, order))
    return fatal, ask_time


def _ask_question(worker: Any, context: Any, name: str) -> Question | None:
    """The copier question for `name` in this pass, or None when copier dropped it."""
    details = worker.template.questions_data.get(name)
    if not isinstance(details, dict):
        return None
    return Question(
        answers=worker.answers,
        context=context,
        jinja_env=worker.jinja_env,
        settings=worker.settings,
        var_name=name,
        **details,
    )


def _unasked_errors(
    worker: Any, context: Any, known: dict[str, Any], by_name: dict[str, questionnaire.Question], order: dict[str, int]
) -> list[dict[str, str]]:
    """One rejection per answer whose question copier would never ask here."""
    errors: list[dict[str, str]] = []
    for name in sorted(known, key=lambda key: order[key]):
        question = _ask_question(worker, context, name)
        if question is not None and not question.get_when():
            errors.append(
                {
                    "question": name,
                    "reason": (
                        f"{name!r} is not asked for these answers "
                        f"(its when {by_name[name].when!r} holds false): "
                        "copier keeps the value but the render discards it"
                    ),
                }
            )
    return errors


def _non_combinable_errors(known: dict[str, Any], order: dict[str, int]) -> list[dict[str, str]]:
    """One rejection per layer include on a base that cannot carry it."""
    return [
        {
            "question": name,
            "reason": (
                f"{name!r} is true on a non-combinable base "
                f"(project_type={known.get('project_type')!r}): "
                "the has_* guard drops the layer at render time"
            ),
        }
        for name in sorted(known, key=lambda key: order[key])
        if name.startswith("include_") and bool(known[name])
    ]


def _question_of(message: str) -> str:
    """The question name a copier error message carries, or "" when it names none."""
    match = re.search(r"'([A-Za-z_][A-Za-z0-9_]*)'", message)
    return match.group(1) if match else ""


def _ordered(errors: list[dict[str, str]], order: dict[str, int]) -> list[dict[str, str]]:
    """Errors in questionnaire (ask) order; unnamed errors trail behind."""
    return sorted(errors, key=lambda error: (order.get(error["question"], len(order)), error["question"]))


def _copier_verdicts(
    known: dict[str, Any], by_name: dict[str, questionnaire.Question], order: dict[str, int]
) -> tuple[list[dict[str, str]], bool]:
    """Copier's own verdicts on the known answers, plus whether the pass stopped (fatal)."""
    fatal, ask_time = _copier_pass(known, by_name, order)
    return (fatal, True) if fatal else (ask_time, False)


def _support_warning(known: dict[str, Any], errors: list[dict[str, str]]) -> dict[str, str] | None:
    """The advisory support.yml warning, or None when nothing is owed."""
    if not known or any("unknown question" in error["reason"] for error in errors):
        return None
    note = _support_note(known)
    return {"question": "project_type", "reason": note} if note is not None else None


def _read_answers_file(path: Path) -> dict[str, Any] | None:
    """The answers mapping at `path`, or None after reporting why it cannot be read."""
    try:
        loaded = read_yaml_mapping(path)
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return None
    except (TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return None
    return {str(key): value for key, value in loaded.items()}


def _report_validation(result: ValidationResult, *, as_json: bool) -> None:
    """Print the verdict of a `--validate` run: JSON, acceptance, or one line per error."""
    if as_json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True, default=str))
    elif result.ok:
        print("answers accepted: every key is asked and copier validates every value")
    else:
        for error in result.errors:
            print(f"{error['question'] or '(general)'}: {error['reason']}")


def _report_matches(matches: list[Match], requirements: list[str], *, as_json: bool) -> None:
    """Print the ranking of a suggestion run: the JSON payload or the human report."""
    if as_json:
        payload = {"requirements": list(requirements), "matches": [m.as_dict() for m in matches]}
        print(json.dumps(payload, indent=2))
    else:
        print(_format_matches(matches, list(requirements)))


def validate_answers(answers: dict[str, Any]) -> ValidationResult:
    """Check a proposed answer set against the questionnaire's own machinery.

    The proposal runs through copier's own questionnaire pass (`Worker._ask`
    with the answers as data, the tests/test_when_model.py oracle pattern):
    choice membership, multiselect membership and `validator:` failures are
    copier's verdicts, not a re-implementation. On top of the pass:

    - a key no question declares is rejected (copier would silently render
      the default instead -- tests/test_answer_fixtures.py guards the same
      trap for fixtures);
    - a key naming a `when: false` internal is rejected (derived variables
      are computed at render time, never answered);
    - a key whose question copier would not ask at these answers is rejected
      (a forced answer copier keeps but the render guards discard -- the
      questions/_combo.yml `when` / `combinable` / `has_*` trio);
    - a layer include on a base that cannot carry it is rejected (the
      `combinable` half of the same trio: `include_web_api=true` on ros2);
    - an answer set whose base no support.yml row promises earns a warning
      reason, not a rejection (support refusal is advisory here; the render
      still runs).

    Returns a ValidationResult; `errors` is empty exactly when `ok` holds.
    The `errors` carry machine-readable {question, reason} pairs in
    questionnaire (ask) order.
    """
    by_name = questionnaire.questions_by_name()
    order = {name: index for index, name in enumerate(by_name)}
    errors = _unknown_errors(answers, by_name) + _internal_errors(answers, by_name)

    known = {key: value for key, value in answers.items() if key in by_name and not by_name[key].internal}
    if known:
        verdicts, stopped = _copier_verdicts(known, by_name, order)
        errors.extend(verdicts)
        if stopped:
            return ValidationResult(ok=False, errors=_ordered(errors, order))

    warning = _support_warning(known, errors)
    if warning is not None:
        errors.append(warning)

    return ValidationResult(ok=not errors, errors=_ordered(errors, order))


@dataclass
class Match:
    """One preset candidate: the preset, why it fits, and what it answers."""

    preset: str
    reasons: list[str] = field(default_factory=list)
    answers: dict[str, Any] = field(default_factory=dict)
    score: int = 0

    def as_dict(self) -> dict[str, Any]:
        """The JSON payload row: name, score, reasons, and the answers it pins."""
        return {
            "preset": self.preset,
            "score": self.score,
            "reasons": list(self.reasons),
            "answers": dict(self.answers),
        }


def _tokens(text: str) -> set[str]:
    """Lowercase alphanumeric tokens of a requirement string, minus filler."""
    return set(_TOKEN.findall(text.lower())) - _STOPWORDS


def _preset_signals(name: str) -> set[str]:
    """The families a preset belongs to, derived from its pinned answers (never prose).

    Signals are the `_KEYWORDS` left-hand sides collapsed by family: a preset
    carries `web_api` when it pins `project_type: web_api` (or the
    `include_web_api` layer), `mcp` when it pins `include_mcp: true`, and so
    on. Comment prose is deliberately unread: the bot preset's comment
    mentions `web_api` as a base it rides on, but answering "api" with the
    bot family would be the wrong recommendation.
    """
    answers = _preset_answers(name)
    signals: set[str] = set()
    project_type = str(answers.get("project_type") or "")
    if project_type:
        signals.add(project_type)
    if project_type == "web_api":
        signals.add("web_api")
    if project_type == "data_science":
        signals.add("data")
    signals |= _layer_signals(answers)
    if project_type == "online_judge":
        signals |= _judge_signals(answers)
    return signals


def _preset_answers(name: str) -> dict[str, Any]:
    """The preset's pinned answers mapping ({} when the file is missing or broken)."""
    try:
        return answers.read_preset(name, PRESETS)
    except (OSError, TypeError, ValueError, answers.PresetError):
        return {}


def _layer_signals(answers: dict[str, Any]) -> set[str]:
    """The layer signals from the include_* flags a preset pins."""
    flags = {
        "include_web_api": "web_api",
        "include_data_science": "data",
        "include_mcp": "mcp",
        "include_bot": "bot",
        "include_scraping": "scraping",
        "include_ctf": "ctf",
    }
    return {signal for flag, signal in flags.items() if answers.get(flag) is True}


def _judge_signals(answers: dict[str, Any]) -> set[str]:
    """The judge signals: `oj` groups the family, `oj:<kind>` ranks the kind."""
    kind = str(answers.get("oj_kind") or "")
    if not kind:
        return {"oj"}
    # The judge kind is its own signal: "atcoder" ranks the AtCoder
    # preset above its siblings, while "oj" still groups them.
    return {"oj", f"oj:{kind}"}


def _match_for_preset(name: str, wanted: dict[str, tuple[str, str]]) -> Match | None:
    """The ranking entry for one preset file, or None when no family matches."""
    carried = _preset_signals(name)
    # All reasons whose token named a carried signal (sorted, so the
    # wording is stable whatever order the requirement words came in);
    # the score counts each signal family once.
    reasons = sorted({reason for _signal, reason in wanted.values() if _signal in carried})
    families = {_signal for _signal, _reason in wanted.values() if _signal in carried}
    if not families:
        return None
    return Match(preset=name, reasons=reasons, answers=_preset_answers(name), score=len(families))


def suggest_presets(requirements: list[str]) -> list[Match]:
    """Rank presets against requirement words, deterministically, with no model.

    Each requirement string is tokenized (lowercase alphanumerics, filler
    dropped); a token counts when `_KEYWORDS` knows it AND the preset carries
    the signal (derived from its pinned answers by `_preset_signals`, never
    from comment prose). One signal family votes once per preset; ties break
    by preset name, so the ranking is stable across runs. A preset with no
    matching family is not returned; with no tokens at all, the ranking is
    empty (nothing to match on).
    """
    wanted = {token for text in requirements for token in _tokens(text)}
    if not wanted:
        return []
    signals = {token: _KEYWORDS[token] for token in wanted if token in _KEYWORDS}
    if not signals:
        return []
    ranked: list[Match] = []
    for name in answers.preset_names(PRESETS):
        matched = _match_for_preset(name, signals)
        if matched is not None:
            ranked.append(matched)
    ranked.sort(key=lambda match: (-match.score, match.preset))
    return ranked


def _format_matches(matches: list[Match], requirements: list[str]) -> str:
    """The human report: each candidate with its score, reasons and next step."""
    if not matches:
        return (
            "no preset matches "
            + (", ".join(requirements) if requirements else "(no requirements given)")
            + "; run `daimonion new --list-presets` to browse every family"
        )
    lines = [f"requirements: {', '.join(requirements)}", ""]
    for match in matches:
        lines.append(f"{match.preset} (score {match.score}): {'; '.join(match.reasons)}")
        pinned = ", ".join(f"{key}={value!r}" for key, value in sorted(match.answers.items()))
        lines.append(f"  answers: {pinned or '(defaults)'}")
    lines += [
        "",
        (
            "Next: propose the full answer set, check it with "
            "`daimonion suggest --validate answers.yml`, then generate with "
            f"`daimonion new <dir> --preset {matches[0].preset}` (or --data-file)."
        ),
    ]
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="daimonion suggest", description="Propose preset candidates for requirements, or validate an answer set."
    )
    parser.add_argument("requirements", nargs="*", help="requirement words, e.g. 'internal API, postgres'")
    parser.add_argument(
        "--validate",
        type=Path,
        default=None,
        metavar="ANSWERS_YML",
        help="validate an answers YAML file instead of suggesting (exit 2 when rejected)",
    )
    parser.add_argument("--json", action="store_true", help="print the machine-readable payload")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: suggest presets for requirements, or validate an answers file."""
    args = _parse_args(argv)
    if args.validate is not None:
        answers = _read_answers_file(args.validate)
        if answers is None:
            return 2
        result = validate_answers(answers)
        _report_validation(result, as_json=args.json)
        return 0 if result.ok else 2
    _report_matches(suggest_presets(list(args.requirements)), list(args.requirements), as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
