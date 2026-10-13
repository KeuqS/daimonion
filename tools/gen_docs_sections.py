"""The questionnaire catalogue blocks: project types, areas, details, features.

`tools/gen_docs.py` renders the questionnaire-derived documentation; this
module owns the markdown blocks that repeat the questionnaire: the
project-type list, the area-gate table with opt-in layers, the per-gate
detailed questions, the trailing project-details table, and the features
catalogue (areas table, task-runner bullet, support wrappers, tier ledger).

This is a machinery-layer module by the tests/test_tool_layers.py table:
the `Model` in, markdown text out -- no template tree, no subprocess.
"""

# WHYNOT: leaf sibling of the gen_docs split; the private names below
# are intra-package collaborators, not encapsulated APIs.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))
from tools import support_ledger  # noqa: E402
from tools.gen_docs_model import FEATURES_DOC  # noqa: E402
from tools.gen_docs_model import RUNNER_URLS  # noqa: E402
from tools.gen_docs_model import SUPPORT_DOC  # noqa: E402
from tools.gen_docs_model import TIERS_JSON  # noqa: E402
from tools.gen_docs_model import Model  # noqa: E402
from tools.gen_docs_prose import _wrap  # noqa: E402
from tools.gen_docs_prose import choice_help  # noqa: E402
from tools.gen_docs_prose import condition_prose  # noqa: E402
from tools.gen_docs_prose import declined  # noqa: E402
from tools.gen_docs_prose import default_prose  # noqa: E402
from tools.gen_docs_prose import prompt_line  # noqa: E402
from tools.gen_docs_prose import recommended  # noqa: E402
from tools.questionnaire import Question  # noqa: E402


def render_project_types(model: Model) -> str:
    """`docs/reference/questionnaire.md`: the project-type choices."""
    question = model.question("project_type")
    described = choice_help(question)
    lines: list[str] = []
    for choice in question.choices:
        value = str(choice)
        description = described.get(value, "")
        lines += _wrap(f"**{value}** — {description}" if description else f"**{value}**", prefix="- ")
        follow = model.follow_ups(value)
        if follow:
            lines += _wrap("Questions asked when this is the base type:", prefix="  ", continuation="  ")
            lines += [line for item in follow for line in _detail_lines(item, indent="  ")]
    return "\n".join(lines)


def _area_table(model: Model) -> list[str]:
    """The area-gate table: gate, its recommended default, and when it is asked."""
    lines = ["| Area gate | Recommended default | Asked when |", "|---|---|---|"]
    lines += [
        f"| `{gate.name}` | {support_ledger.cell(recommended(gate))} | {support_ledger.cell(condition_prose(gate))} |"
        for gate in model.area_gates
    ]
    return lines


def render_areas(model: Model) -> str:
    """`docs/reference/questionnaire.md`: the area gates and opt-in layers."""
    lines = [
        (
            "Each area asks one gate question first: answering **Yes** configures it from the"
            " recommendation below, answering **No** reveals that area's detailed questions."
        ),
        "",
        *_area_table(model),
    ]
    if model.includes:
        lines += ["", "An opt-in layer adds its area to a combinable base:", ""]
        for layer in model.includes:
            text = (
                f"**`{layer.name}`** (asked when {condition_prose(layer)}; default {default_prose(layer)})"
                f" — {prompt_line(layer)}"
            )
            lines += _wrap(text, prefix="- ")
    if model.option_gates:
        lines += ["", "An opt-in layer asks its own gate on top:", ""]
        for gate in model.option_gates:
            text = f"**`{gate.name}`** (asked when {condition_prose(gate)}): {recommended(gate)}"
            lines += _wrap(text, prefix="- ")
    return "\n".join(lines)


def _choice_bullets(question: Question, described: dict[str, str]) -> list[tuple[str, str]]:
    """The (value, description) bullets to render for a question.

    Questions whose `choices` are a template (`package_manager`, `oj_kind`)
    declare their values only in the help text, so everything the help
    describes is rendered; otherwise the declared choices win.
    """
    if not question.choices:
        return list(described.items())
    return [(str(choice), described[str(choice)]) for choice in question.choices if str(choice) in described]


def _choice_values(question: Question, described: dict[str, str]) -> list[str]:
    """The choices with no help bullet, value plus label when the model has one.

    A long list (the SPDX license set) is rendered as bare values: the labels
    would triple its length without adding anything to look up.
    """
    labels = dict(zip(question.choices, question.labels, strict=True)) if question.labels else {}
    with_labels = len(question.choices) <= 20
    parts: list[str] = []
    for choice in question.choices:
        value = str(choice)
        if value in described:
            continue
        label = labels.get(choice) if with_labels else None
        parts.append(f"`{value}` ({label})" if label and label != value else f"`{value}`")
    return parts


def _detail_lines(question: Question, indent: str = "") -> list[str]:
    """One detailed question, its choices, and its documented default."""
    kind = question.type or "str"
    head = f"**`{question.name}`** ({kind}; default {default_prose(question)}) — {prompt_line(question)}"
    lines = _wrap(head, prefix=f"{indent}- ", continuation=f"{indent}  ")
    described = choice_help(question)
    for value, description in _choice_bullets(question, described):
        lines += _wrap(f"**`{value}`** — {description}", prefix=f"{indent}  - ", continuation=f"{indent}    ")
    undescribed = _choice_values(question, described)
    if undescribed:
        lines += _wrap(f"One of: {' · '.join(undescribed)}.", prefix=f"{indent}  ", continuation=f"{indent}  ")
    return lines


def render_detailed_questions(model: Model) -> str:
    """`docs/reference/questionnaire.md`: what each gate reveals."""
    header = [
        "Answering **No** to a gate reveals that area's detailed questions:",
    ]
    sections: list[str] = []
    for gate in model.gates:
        part = [
            f"### `{gate.name}`",
            "",
            f"{prompt_line(gate)} Recommended: {recommended(gate)}",
            "",
            f"Answer **No** to {declined(gate)}",
        ]
        details = [line for item in model.details(gate) for line in _detail_lines(item)]
        if details:
            part += ["", *details]
        sections.append("\n".join(part))
    return "\n".join(header) + "\n\n" + "\n\n".join(sections)


def render_project_details(model: Model) -> str:
    """`docs/reference/questionnaire.md`: the trailing project-details questions."""
    lines = [
        "| Question | Default | Asked when | Prompt |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| `{question.name}` | {support_ledger.cell(default_prose(question))}"
        f" | {support_ledger.cell(condition_prose(question))}"
        f" | {support_ledger.cell(prompt_line(question))} |"
        for question in model.project_details
    ]
    return "\n".join(lines)


def render_features_areas(model: Model) -> str:
    """`docs/reference/features.md`: the per-area recommended settings table."""
    return "\n".join(_area_table(model))


def render_features_task_runner(model: Model) -> str:
    """`docs/reference/features.md`: the task-runner bullet, with the questionnaire's default."""
    runners = model.question("task_runner")
    pixi = model.question("task_runner_pixi")
    text = (
        f"A task runner of your choice ({_runner_list(runners)}) driving lint / type-check / test / docs"
        " — one shared task definition, invoked by CI too. With `package_manager` = pixi, the choices are"
        f" {_runner_list(pixi)} (poethepoet is not offered there)."
    )
    return "\n".join(_wrap(text, prefix="- "))


def _runner_list(question: Question) -> str:
    """One task runner's choices, linked, with the questionnaire's default marked."""
    labels = question.labels or [str(choice) for choice in question.choices]
    parts: list[str] = []
    for choice, label in zip(question.choices, labels, strict=True):
        name = f"[{label.replace(' ', '&nbsp;')}]({RUNNER_URLS[choice]})" if choice in RUNNER_URLS else label
        parts.append(f"{name} (default)" if choice == question.default else name)
    return " / ".join(parts)


def render_support_table(support: dict[str, Any]) -> str:
    """`docs/reference/features.md`: the compact support summary, from `support.yml`.

    Bound to the link into the full reference, which only this module knows
    (the summary is generated into the catalogue page).
    """
    link = SUPPORT_DOC.relative_to(FEATURES_DOC.parent)
    return support_ledger.render_support_table(support, full_link=str(link))


def render_support_doc(support: dict[str, Any]) -> str:
    """`docs/reference/support.md`: the full support matrix, prose included."""
    return support_ledger.render_support_doc(support)


def render_tier_ledger(_model: Model) -> str:
    """`docs/explanations/verification.md`: the cost ledger as a table.

    The selector, the collected count, the budget and the measured wall are
    the ledger's own numbers (TODO.md §28.6-D4), so this block is generated
    from `tests/matrix/tiers.json` instead of a hand-copied table drifting
    from it -- the same "the docs repeat the data, the generator owns the
    region" treatment the questionnaire blocks get. The hand-written table
    above it keeps the *roles* (what each tier is for); this one keeps the
    *numbers* (what each tier costs and when that was measured).
    """
    ledger = json.loads(TIERS_JSON.read_text(encoding="utf-8"))
    entries: list[tuple[str, dict[str, Any]]] = [
        *ledger["tiers"].items(),
        *ledger.get("witness", {}).items(),
    ]
    lines = ["| Ledger row | Selector | Tests | Budget | Measured |", "|---|---|---|---|---|"]
    for name, row in entries:
        selector = f'-m "{row["expression"]}"' if row.get("expression") else "—"
        budget = (
            f"{row['budget_seconds']}s (measured {row['wall_seconds']}s)"
            if "budget_seconds" in row
            else f"measured {row['wall_seconds']}s"
        )
        lines.append(
            f"| `{row.get('task', name)}` | `{support_ledger.cell(selector)}`"
            f" | {row['collected']} | {support_ledger.cell(budget)} | {row['measured']} |"
        )
    return "\n".join(lines)
