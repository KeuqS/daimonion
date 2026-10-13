"""The questionnaire's ask order as a mermaid graph.

`tools/gen_docs.py` renders the questionnaire-derived documentation; this
module owns the catalogue's mermaid block: each `project_type` base's
follow-up questions, each gate's Yes/No branches (labelled from the gate's
own help text), the mid-sequence ask diamonds, the opt-in layers, and the
trailing project-details tail.

This is a machinery-layer module by the tests/test_tool_layers.py table:
the `Model` in, mermaid text out -- no template tree, no subprocess.
"""

# WHYNOT: leaf sibling of the gen_docs split; the private names below
# are intra-package collaborators, not encapsulated APIs.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from itertools import count
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools.gen_docs_model import ALL_TYPES  # noqa: E402
from tools.gen_docs_model import GATE_PREFIX  # noqa: E402
from tools.gen_docs_model import GenDocsError  # noqa: E402
from tools.gen_docs_model import Model  # noqa: E402
from tools.gen_docs_prose import _break_label  # noqa: E402
from tools.gen_docs_prose import _escape_label  # noqa: E402
from tools.gen_docs_prose import _short_gate_label  # noqa: E402
from tools.gen_docs_prose import asked_for_values  # noqa: E402
from tools.gen_docs_prose import choice_help  # noqa: E402
from tools.gen_docs_prose import condition_prose  # noqa: E402
from tools.questionnaire import Question  # noqa: E402


@dataclass(frozen=True)
class _AskGroup:
    """One `project_type` branch: the questions asked, and for which base."""

    choice: str
    questions: list[Question]
    first_index: int


def _ask_groups(model: Model) -> list[_AskGroup]:
    """The project-type branches: each base's follow-up questions, in ask order."""
    order = {q.name: index for index, q in enumerate(model.questions)}
    groups: list[_AskGroup] = []
    for choice in model.question("project_type").choices:
        questions = model.follow_ups(str(choice))
        if questions:
            groups.append(_AskGroup(str(choice), questions, min(order[q.name] for q in questions)))
    return groups


def _ask_label() -> Callable[[list[Question]], str]:
    """Build the `ask: ...` node label for a group of questions."""

    def label(questions: list[Question]) -> str:
        parts: list[str] = []
        for question in questions:
            choices = [str(choice) for choice in question.choices] or list(choice_help(question))
            values = choices or asked_for_values(question)
            parts.append(f"{question.name} ({' / '.join(values)})" if values else question.name)
        return f"ask: {_break_label(parts)}"

    return label


class _Graph:
    """Accumulates mermaid lines for one questionnaire and hands out node ids."""

    def __init__(self, model: Model) -> None:
        self.model = model
        self.lines: list[str] = []
        self._counter = count()

    def node(self, prefix: str) -> str:
        """A fresh node id with this prefix."""
        return f"{prefix}{next(self._counter)}"

    def add(self, *lines: str) -> None:
        """Append lines to the graph."""
        self.lines.extend(lines)


def _split_asks(model: Model, first_gate: Question) -> tuple[list[_AskGroup], list[_AskGroup]]:
    """Split the project-type branches into pre-gate and mid-sequence ones."""
    first = min(index for index, q in enumerate(model.questions) if q.name == first_gate.name)
    groups = _ask_groups(model)
    return (
        [group for group in groups if group.first_index < first],
        [group for group in groups if group.first_index >= first],
    )


def _graph_project_types(graph: _Graph, early: list[_AskGroup], early_ids: list[str], head: list[Question]) -> None:
    """Branch from `project_type` to the bases' follow-ups and the head gates."""
    ask_label = _ask_label()
    for group, node in zip(early, early_ids, strict=True):
        graph.add(f'    PT -->|{group.choice}| {node}["{ask_label(group.questions)}"]')
    when = condition_prose(head[0])
    edge = f"    PT -->|{when}|" if when != ALL_TYPES else "    PT -->"
    graph.add(f'{edge} {_gate_id(head[0])}{{"{_gate_label(head[0])}"}}')
    if len(head) > 1:
        graph.add(f'    PT -->|other| {_gate_id(head[1])}{{"{_gate_label(head[1])}"}}')
    target = _gate_id(head[-1])
    graph.add(*[f"    {node} --> {target}" for node in early_ids])


def _graph_branches(graph: _Graph, gate: Question, after: str) -> None:
    """A gate's Yes/No branches and their rejoin."""
    graph.add(*_gate_branches(graph.model, gate, _gate_id(gate)))
    graph.add(f"    {_yes_id(gate)} --> {after}", f"    {_no_id(gate)} --> {after}")


def _graph_asks(graph: _Graph, late: list[_AskGroup], late_ids: list[str], after_ids: list[str], entry: str) -> None:
    """The mid-sequence project-type asks (`online_judge`), each a Yes/No diamond."""
    ask_label = _ask_label()
    previous = entry
    for group, diamond, after in zip(late, late_ids, after_ids, strict=True):
        ask = graph.node("Q")
        graph.add(f'    {diamond}{{"{_escape_label(group.choice)}?"}}')
        if previous != diamond:
            graph.add(f"    {previous} --> {diamond}")
        graph.add(
            f'    {diamond} -->|Yes| {ask}["{ask_label(group.questions)}"]',
            f"    {ask} --> {after}",
            f"    {diamond} -->|No| {after}",
        )
        previous = after


def _graph_tail(graph: _Graph, tail: list[Question], entries: list[str], after_ids: list[str], entry: str) -> None:
    """Chain the remaining gates; every branch rejoins at the next stage."""
    previous = entry
    for index, gate in enumerate(tail):
        after = after_ids[index]
        if entries[index] != _gate_id(gate):
            layer = (
                f'    {entries[index]}{{"{_layer_label(graph.model, gate)}?"}}'
                if previous == entries[index]
                else f'    {previous} --> {entries[index]}{{"{_layer_label(graph.model, gate)}?"}}'
            )
            graph.add(
                layer,
                f'    {entries[index]} -->|Yes| {_gate_id(gate)}{{"{_gate_label(gate)}"}}',
                f"    {entries[index]} -->|No| {after}",
            )
        elif previous == _gate_id(gate):
            graph.add(f'    {_gate_id(gate)}{{"{_gate_label(gate)}"}}')
        else:
            graph.add(f'    {previous} --> {_gate_id(gate)}{{"{_gate_label(gate)}"}}')
        _graph_branches(graph, gate, after)
        previous = after


def _head_split(model: Model) -> tuple[list[Question], list[Question]]:
    """Split the gates into the head run and the ones behind the ask diamonds.

    The head gates are the leading run drawn straight off `project_type`; the
    rest chain behind the mid-sequence ask diamonds. Derived from the ask
    order, not a count (TODO.md §28.5 R5): the head gates are the ones asked
    before the first project-type branch that itself follows a gate (today,
    online_judge), so a new gate or a moved genre's questions reshape the
    graph without editing a hardcoded slice.
    """
    gates = model.gates
    order = {q.name: index for index, q in enumerate(model.questions)}
    mid = min(
        (
            group.first_index
            for group in _ask_groups(model)
            if any(order[gate.name] < group.first_index for gate in gates)
        ),
        default=None,
    )
    if mid is None:
        return gates, []
    return [gate for gate in gates if order[gate.name] < mid], [gate for gate in gates if order[gate.name] >= mid]


def render_mermaid(model: Model) -> str:
    """The questionnaire's ask order, with each gate's Yes/No branches."""
    gates = model.gates
    if not gates:
        msg = "the questionnaire has no use_recommended_* gate to draw"
        raise GenDocsError(msg)
    head, tail = _head_split(model)
    early, late = _split_asks(model, head[0])
    graph = _Graph(model)
    early_ids = [graph.node("Q") for _ in early]
    late_ids = [graph.node("D") for _ in late]
    entries = [graph.node("L") if _layer_var(gate) or gate in model.option_gates else _gate_id(gate) for gate in tail]
    includes_id = "INC" if model.includes else None
    first_tail = entries[0] if tail else "PD"
    late_after = [*late_ids[1:], includes_id or first_tail] if late_ids else []
    after_head = late_ids[0] if late_ids else includes_id or first_tail
    graph.add("flowchart TD", "    Start([Start]) --> PT[project_type]")
    _graph_project_types(graph, early, early_ids, head)
    for index, gate in enumerate(head):
        after = _gate_id(head[index + 1]) if index + 1 < len(head) else after_head
        _graph_branches(graph, gate, after)
    _graph_asks(graph, late, late_ids, late_after, after_head)
    if includes_id:
        names = _break_label([f"ask: {', '.join(q.name for q in model.includes)}"], 56)
        label = f'INC["{names}<br/>(each only for the bases it combines with)"]'
        graph.add(f"    {label}" if late_ids else f"    {after_head} --> {label}")
    _graph_tail(graph, tail, entries, [*entries[1:], "PD"], includes_id or after_head)
    details = _break_label([q.name for q in model.project_details])
    graph.add(f'    PD["Project details: {details}"]', "    PD --> End([Generate project])")
    return "\n".join(graph.lines)


def _gate_id(gate: Question) -> str:
    """Stable node id for a gate diamond."""
    return f"G_{gate.name.removeprefix(GATE_PREFIX)}"


def _yes_id(gate: Question) -> str:
    """Node id of a gate's Yes node."""
    return f"{_gate_id(gate)}_yes"


def _no_id(gate: Question) -> str:
    """Node id of a gate's No node."""
    return f"{_gate_id(gate)}_no"


def _gate_label(gate: Question) -> str:
    """A gate diamond's label: the question, and when it is asked."""
    when = condition_prose(gate)
    if when == ALL_TYPES:
        return f"{gate.name}?"
    return f"{_escape_label(gate.name)}?<br/>({_escape_label(when)})"


def _layer_var(gate: Question) -> str | None:
    """The `has_*` layer variable a gate's condition tests, if any."""
    match = re.match(r"^\{\{\s*(has_[a-z_]+)\s*\}\}$", str(gate.when))
    return match.group(1) if match else None


def _layer_label(model: Model, gate: Question) -> str:
    """The layer question asked before a layer-gated area gate."""
    variable = _layer_var(gate)
    if variable:
        return f"{variable.removeprefix('has_').replace('_', ' ')} layer"
    option = next((q for q in model.includes if str(q.when) and q.name in str(gate.when)), None)
    return option.name if option else "option"


def _gate_branches(model: Model, gate: Question, node_id: str) -> list[str]:
    """A gate's Yes/No edges, labelled from its own help text."""
    yes = _short_gate_label(model, gate, yes=True)
    no = _short_gate_label(model, gate, yes=False)
    return [
        f'    {node_id} -->|Yes| {_yes_id(gate)}["{yes}"]',
        f'    {node_id} -->|No| {_no_id(gate)}["{no}"]',
    ]
