#!/usr/bin/env python3
"""Questionnaire surface: ask order, presets, explanations, proposals, validation.

Responsibility: the tools that answer from the questionnaire's own words
without rendering anything -- `list_questions`, `list_presets`,
`explain_choice`, `suggest_config`, `validate_answers` -- plus the one helper
(`_explain_text`) that routes an `explain_choice` call to the `explain.*`
function it names. Filesystem only, no render, no network (validation runs
copier's own questionnaire pass, which is still not a render).
"""

# WHYNOT: the functions below are registered through @server.tool()
# inside register_*(); their call edge is the decorator, invisible to
# the checker.
# pyright: reportUnusedFunction=false

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402
from tools import cli  # noqa: E402
from tools import explain  # noqa: E402
from tools import suggest  # noqa: E402


def explain_text(
    question: str | None,
    value: str | None,
    preset: str | None,
    deviate_question: str | None,
    deviate_value: str | None,
) -> str:
    """The explanation text for one `explain_choice` call (the tool itself only wraps errors)."""
    if preset is not None:
        return explain.explain_preset(preset)
    if deviate_question is not None and deviate_value is not None:
        return explain.explain_deviation(deviate_question, deviate_value)
    if question is not None:
        return explain.explain_answer(question, value)
    msg = "pass preset=, question=[value=], or deviate_question= + deviate_value="
    raise ToolError(msg)


def register_questionnaire(server: Any) -> None:
    """Register the questionnaire tools on `server`."""

    @server.tool()
    def list_questions(*, asked_only: bool = True) -> dict[str, Any]:
        """List this template's questionnaire in ask order.

        Returns {"count", "questions"}; each entry has name, type, default (as written -- defaults are Jinja
        expressions), when, help, choices and source file. `internal` marks the
        derived `when: false` variables, which `asked_only=True` (the default)
        excludes. Call this before `render_project`: it is the only way to know
        which answers are valid and what each question defaults to. Two questions
        (`package_manager`, `oj_kind`) carry a `choices_template` instead of a
        resolved list, because their choices narrow themselves from earlier
        answers.
        """
        schema = suggest.questionnaire_schema(asked_only=asked_only)
        return {"count": schema["count"], "questions": schema["questions"]}

    @server.tool()
    def list_presets() -> dict[str, Any]:
        """List the ready-made answer files under presets/.

        Returns {"count", "presets"}; each entry has `name` (what the CLI's
        `--preset` flag and `new`'s preset parameter accept) and `answers` (the
        mapping the file supplies on top of copier's defaults -- the family
        keys only, never the full questionnaire). `recommend_answers` builds an
        answer set from named constraints; `list_presets` is the cheaper inverse:
        the named starting points that already exist. Filesystem only -- no
        render, no network.
        """
        presets = [{"name": name, "answers": cli.preset_answers(name)} for name in cli.available_presets()]
        return {"count": len(presets), "presets": presets}

    @server.tool()
    def explain_choice(
        question: str | None = None,
        value: str | None = None,
        preset: str | None = None,
        deviate_question: str | None = None,
        deviate_value: str | None = None,
    ) -> dict[str, Any]:
        """Explain a preset or an answer choice from the questionnaire's own words.

        Pass `preset` to explain one preset (why it pins what it pins),
        `question` (plus optional `value`) to explain one question's recommended
        setting, or `deviate_question` + `deviate_value` for what changes when
        that question takes that value instead (which questions appear or
        disappear, which support rows name the combination). Returns {"explanation"}
        with the human-readable text. Filesystem only -- no render, no network.
        """
        try:
            text = explain_text(question, value, preset, deviate_question, deviate_value)
        except explain.ExplainError as exc:
            raise ToolError(str(exc)) from exc
        return {"explanation": text}

    @server.tool()
    def suggest_config(requirements: str) -> dict[str, Any]:
        """Propose preset candidates for requirement words (the constrained assistant's first step).

        Pass what the project needs ("an internal API with Postgres", "a Discord
        bot", "firmware for esp32"); returns {"requirements", "matches"} with each
        match's preset name, score, human reasons and the answers it pins. The
        ranking is a deterministic keyword match over the preset files -- no
        model, no render. Next: draft the full answer set, check it with
        `validate_answers`, then generate with `daimonion new --preset` or an
        answers file. Filesystem only -- no render, no network.
        """
        matches = suggest.suggest_presets([requirements])
        return {"requirements": requirements, "matches": [match.as_dict() for match in matches]}

    @server.tool()
    def validate_answers(answers: dict[str, Any]) -> dict[str, Any]:
        """Check a proposed answer set against the questionnaire's own machinery.

        Pass the candidate answers (e.g. {"project_type": "web_api"}); returns
        {"ok", "errors"} where errors are {question, reason} pairs in ask order:
        unknown questions, answers to derived internals, values outside the
        choices, validator failures, answers to questions copier would never ask,
        and layer includes on a non-combinable base are all rejected. An approved
        set (`ok: true`) is what `render_project` or `daimonion new --preset`
        may generate from. Reads the questionnaire and runs copier's own
        questionnaire pass -- no render, no network.
        """
        return suggest.validate_answers(dict(answers)).as_dict()
