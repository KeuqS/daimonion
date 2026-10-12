#!/usr/bin/env python3
"""The questionnaire's dependency graph: what references what, in which order, and where new definitions fit.

The questionnaire's questions and its internal `when: false` variables form a
dependency graph -- internals reference questions and other internals, and a
question's `when:`/`default:` reference internals -- and copier evaluates it
in DEFINITION ORDER (the include chain over questions/, top-level key order
within a fragment). A definition must therefore precede every reference: a
backward reference silently reads Undefined (falsy) and picks the wrong
branch. That bit twice (the docs_type -> micropython_pkg back-reference and
the mcp_effective -> web_api ordering, TODO.md §13), and the two structure
tests (`test_question_references_are_forward_only`,
`test_internal_variable_references_are_forward_only` in
tests/test_copier_structure.py) now enforce it -- after the fact. As gates,
layers and platforms are added, this hand-managed ordering is the most
fragile part of the questionnaire; this tool makes it visible and plannable
BEFORE the next edit breaks it. It reuses the existing parsers
(tools/questionnaire.load_questions for the ask order and source fragments,
tools/when_model.jinja_identifiers for the identifier reads) -- no second
Jinja parser lives here.

Three capabilities:

1. **The graph**: one node per asked question and per internal, with its
   fragment and position (fragment line + index in definition order); one
   edge per reference read out of `when` + `default`, classified question /
   internal / external. Identifiers that name no definition (Jinja filters
   like `replace`, method names like `strftime`) are external leaves:
   reported for the record, never failures.
2. **Validation**: the forward-reference rule, recomputed. For an asked
   question, ANY reference to a later definition is a violation (the
   question resolves when it is asked; nothing later exists yet). For an
   internal, only internal-to-internal edges are order-bound -- internals
   resolve at render time, after every answer exists, so reading a later
   *asked* question is fine (exactly the split the two structure tests
   draw). A violation is reported with both names and both positions;
   exit status 1.
3. **The placement guide** (``--where NAME``): where a new internal or
   question named NAME -- whose references are given with ``--refs`` -- may
   live, and what currently occupies that spot. This answers "where do I
   add the new gate's internals": after the last definition it reads, before
   anything that will read it, and (repo convention, see
   docs/explanations/template-dev.md) internals that questions reference
   live in their genre fragment before the asking gate, render-only
   internals at the end of questions/_internal.yml.

Usage:

    python tools/question_graph.py                # the human report (on stderr)
    python tools/question_graph.py --json         # the machine report (stdout; prose stays on stderr)
    python tools/question_graph.py --where mygate_effective --refs include_mygate,project_type
    python tools/question_graph.py --where mcp_effective   # an existing name: its own refs, its window
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:  # tools/ is no root package (pyproject.toml)
    sys.path.insert(0, str(TOP))

from tools import questionnaire  # noqa: E402
from tools import when_model  # noqa: E402

#: Kinds of node (and the classification every edge target gets).
QUESTION = "question"
INTERNAL = "internal"
EXTERNAL = "external"

#: The fields the graph reads references from. `choices` is deliberately not
#: among them: the structure tests own it there, and this graph is about the
#: when/default wiring the placement guide reasons over.
FIELDS = ("when", "default")

# when_model.JINJA_OPERATORS plus `if`/`else`: this module also reads
# `default:` values, which use Jinja's inline conditional (`x if y else z`)
# -- those two name operators of the grammar, never variables a definition
# reads.
_JINJA_OPERATORS = when_model.JINJA_OPERATORS | {"if", "else"}

#: A top-level YAML key at column 0 -- what maps each node to its line inside
#: its fragment (the fragments keep every definition at column 0; help text
#: and comments are indented or start with `#`, so nothing else can match).
_TOP_LEVEL_KEY = re.compile(r"(?m)^([A-Za-z_][A-Za-z0-9_-]*):(?:\s|$)")


@dataclass(frozen=True)
class Node:
    """One definition (asked question or internal) at its position in the order."""

    name: str
    kind: str  # QUESTION or INTERNAL
    fragment: str  # repo-relative file the definition lives in, e.g. questions/_internal.yml
    line: int  # 1-based line of the definition's top-level key in that file
    order: int  # index in the definition order (= copier's ask order)

    @property
    def at(self) -> str:
        """The position as a display string: fragment:line (order N)."""
        return f"{self.fragment}:{self.line} (order {self.order})"


@dataclass(frozen=True)
class Edge:
    """One reference: a definition's `field` reads identifier `target`."""

    source: str
    field: str  # "when" or "default"
    target: str
    target_kind: str  # QUESTION, INTERNAL or EXTERNAL


@dataclass(frozen=True)
class Violation:
    """A backward reference: `source` (at its position) reads `target` defined later."""

    source: Node
    field: str
    target: Node


@dataclass
class Graph:
    """The questionnaire as a directed graph, in definition order."""

    nodes: list[Node]
    edges: list[Edge]

    @property
    def by_name(self) -> dict[str, Node]:
        """The nodes keyed by name."""
        return {node.name: node for node in self.nodes}

    def dependents(self) -> dict[str, list[str]]:
        """Name -> the definitions that reference it, in definition order."""
        result: dict[str, list[str]] = {node.name: [] for node in self.nodes}
        for edge in self.edges:
            if edge.target_kind != EXTERNAL and edge.source not in result[edge.target]:
                result[edge.target].append(edge.source)
        return result

    def externals(self) -> dict[str, list[str]]:
        """External identifier -> the definitions that read it (external leaves, reported not failures)."""
        result: dict[str, list[str]] = {}
        for edge in self.edges:
            if edge.target_kind == EXTERNAL and edge.source not in result.setdefault(edge.target, []):
                result[edge.target].append(edge.source)
        return result


def _fragment_path(source: str) -> Path:
    """The file a `questionnaire.Question.source` label points at (fragments keep the basename)."""
    return TOP / "copier.yml" if source.startswith("copier.yml") else TOP / "questions" / source


def _fragment_label(source: str) -> str:
    """The fragment as a repo-relative display path."""
    return "copier.yml" if source.startswith("copier.yml") else f"questions/{source}"


def _refs(text: str) -> frozenset[str]:
    """The identifiers a when/default expression reads (when_model owns the scanner; keywords are not reads)."""
    return frozenset(when_model.jinja_identifiers(text)) - _JINJA_OPERATORS


def build_graph() -> Graph:
    """Every question and internal as a node, every when/default reference as an edge.

    tools/questionnaire.load_questions() is the authority: its returned list
    IS the ask order (includes resolved the way copier merges them), and each
    entry carries its source fragment. Line numbers come from one regex scan
    per fragment file (``_TOP_LEVEL_KEY``), not from a YAML re-parse.
    """
    questions, _settings = questionnaire.load_questions()
    lines: dict[str, dict[str, int]] = {}
    for question in questions:
        if question.source in lines:
            continue
        text = _fragment_path(question.source).read_text(encoding="utf-8")
        lines[question.source] = {
            match.group(1): text.count("\n", 0, match.start()) + 1 for match in _TOP_LEVEL_KEY.finditer(text)
        }

    nodes = [
        Node(
            name=question.name,
            kind=INTERNAL if question.internal else QUESTION,
            fragment=_fragment_label(question.source),
            line=lines[question.source].get(question.name, 0),
            order=order,
        )
        for order, question in enumerate(questions)
    ]

    kinds = {question.name: (INTERNAL if question.internal else QUESTION) for question in questions}
    edges: list[Edge] = []
    for question in questions:
        for field in FIELDS:
            value = getattr(question, field)
            if not isinstance(value, str):
                continue  # a plain default (`true`, `'src'`, a list): no expressions, no reads
            for target in sorted(_refs(value)):
                target_kind = kinds.get(target, EXTERNAL)
                edges.append(Edge(source=question.name, field=field, target=target, target_kind=target_kind))
    return Graph(nodes=nodes, edges=edges)


def _is_backward(edge: Edge, by_name: dict[str, Node]) -> bool:
    """Whether one edge violates the forward-reference rule (the two structure tests' split, kept faithful).

    An asked question resolves when it is reached in ask order, so any
    reference of its `when`/`default` to a LATER definition (question or
    internal) reads Undefined. An internal resolves at render time, after
    every answer exists, so only its internal-to-internal edges are
    order-bound -- reading a later *asked* question is fine by design.
    """
    if edge.target_kind == EXTERNAL:
        return False
    source, target = by_name[edge.source], by_name[edge.target]
    if target.order <= source.order:
        return False
    return not (source.kind == INTERNAL and edge.target_kind != INTERNAL)


def find_violations(graph: Graph) -> list[Violation]:
    """Every backward reference, with both names and both positions."""
    by_name = graph.by_name
    return [
        Violation(source=by_name[edge.source], field=edge.field, target=by_name[edge.target])
        for edge in graph.edges
        if _is_backward(edge, by_name)
    ]


@dataclass
class Placement:
    """Where a definition named `name` may live, given the identifiers it reads.

    ``earliest``/``latest`` bound the legal positions in definition order:
    after the last definition it reads, before the first definition that
    reads it (``latest`` is the append-at-the-end slot for a brand-new
    name, which has no dependents yet). ``occupant`` is the definition
    currently sitting at the earliest spot -- what a new definition would be
    inserted in front of. ``current``/``current_legal`` are filled for a
    name that already exists.
    """

    name: str
    kind: str
    exists: bool
    refs: list[Node]  # known definitions it reads, in definition order
    external_refs: list[str]  # identifiers it reads that name no definition
    earliest: int  # first legal position in definition order
    latest: int  # last legal position (the end slot for a new name)
    occupant: Node | None  # the definition currently at ``earliest``
    insert_fragment: str  # the fragment an insertion at ``earliest`` lands in
    current: Node | None  # the existing definition itself, when ``exists``
    current_legal: bool | None  # whether that existing spot satisfies the rule
    note: str  # the convention advice that comes with the spot


def _insert_fragment(graph: Graph, order: int) -> str:
    """The fragment position ``order`` belongs to (the last fragment when appending at the end)."""
    if order >= len(graph.nodes):
        return graph.nodes[-1].fragment
    return graph.nodes[order].fragment


def _placement_note(kind: str, *, exists: bool) -> str:
    """The convention line that comes with every placement answer."""
    if kind == QUESTION:
        return (
            "a question `when:` runs at ask time, so it may reference anything defined"
            " earlier in the include chain -- raw answers and already-defined internals alike"
            " (docs/explanations/template-dev.md); every definition it references must sit"
            " before it, so place the internals first, then re-run --where for the question"
        )
    if exists:
        return (
            "internals a question references live in that question's genre fragment before the"
            " asking gate; render-only internals stay in questions/_internal.yml at the end of the chain"
        )
    return (
        "if a question must reference this internal, it belongs in that question's genre fragment"
        " BEFORE the asking gate; if only render-side code reads it, questions/_internal.yml at the"
        " end of the chain is the conventional spot"
    )


def _resolve_placement_refs(
    graph: Graph, name: str, ref_names: list[str], *, exists: bool
) -> tuple[list[Node], list[str]]:
    """Resolve reference names into sorted internal Node objects and unknown external names."""
    by_name = graph.by_name
    if exists and not ref_names:
        ref_names = [edge.target for edge in graph.edges if edge.source == name and edge.target != name]
    seen: set[str] = set()
    refs: list[Node] = []
    external_refs: list[str] = []
    for ref_name in ref_names:
        if ref_name == name or ref_name in seen:
            continue
        seen.add(ref_name)
        if ref_name in by_name:
            refs.append(by_name[ref_name])
        else:
            external_refs.append(ref_name)
    refs.sort(key=lambda ref: ref.order)
    return refs, sorted(external_refs)


def _calculate_placement_bounds(refs: list[Node], name: str, *, exists: bool, graph: Graph) -> tuple[int, int]:
    """Compute the earliest and latest legal order indices for a node."""
    last_ref = max((ref.order for ref in refs), default=-1)
    earliest = last_ref + 1
    if exists:
        dependent_orders = [graph.by_name[dep].order for dep in graph.dependents().get(name, [])]
        latest = max(min(dependent_orders, default=len(graph.nodes)) - 1, earliest)
    else:
        latest = len(graph.nodes)
    return earliest, max(latest, earliest)


def place(graph: Graph, name: str, ref_names: list[str], kind: str) -> Placement:
    """Compute the placement window for ``name`` (an existing definition, or a new one + its refs).

    An existing name uses its own edges as the refs (``ref_names`` ignored):
    its window is closed on both sides, because it cannot move before a
    definition it reads nor after its first dependent. A new name has no
    dependents yet, so only the lower bound applies.
    """
    by_name = graph.by_name
    node = by_name.get(name)
    exists = node is not None
    refs, external_refs = _resolve_placement_refs(graph, name, ref_names, exists=exists)
    earliest, latest = _calculate_placement_bounds(refs, name, exists=exists, graph=graph)

    return Placement(
        name=name,
        kind=node.kind if exists else kind,
        exists=exists,
        refs=refs,
        external_refs=external_refs,
        earliest=earliest,
        latest=latest,
        occupant=graph.nodes[earliest] if earliest < len(graph.nodes) else None,
        insert_fragment=_insert_fragment(graph, earliest),
        current=node,
        current_legal=(
            not any(_is_backward(edge, by_name) for edge in graph.edges if edge.source == name) if exists else None
        ),
        note=_placement_note(node.kind if exists else kind, exists=exists),
    )


def _cap(names: list[str], limit: int) -> str:
    """A display list capped at ``limit`` names (the report stays one line per node)."""
    if len(names) <= limit:
        return ", ".join(names)
    return ", ".join(names[:limit]) + f" ... +{len(names) - limit} more"


def placement_lines(placement: Placement, last_node: Node) -> list[str]:
    """The placement guide, as prose lines."""
    title = f"{placement.kind} '{placement.name}'" + (" (new)" if not placement.exists else "")
    reads = [f"{ref.name} [{ref.kind}, {ref.fragment}:{ref.line}, order {ref.order}]" for ref in placement.refs]
    lines = [
        f"placement guide -- {title}",
        f"  reads: {_cap(reads, 8) if reads else '(nothing it must come after)'}",
    ]
    if placement.external_refs:
        lines.append(f"  external reads (no definition; no ordering weight): {_cap(placement.external_refs, 8)}")
    lines.append(f"  legal window: orders {placement.earliest}..{placement.latest}")
    if placement.current is not None:
        verdict = "legal" if placement.current_legal else "VIOLATION: it reads a definition defined later"
        lines.append(f"  currently at {placement.current.at} -- {verdict}")
    if placement.occupant is not None and placement.occupant != placement.current:
        occupant = placement.occupant
        lines += [
            (
                f"  earliest legal spot: order {placement.earliest}, currently occupied by"
                f" {occupant.name} [{occupant.kind}, {occupant.fragment}:{occupant.line}]"
            ),
            (
                f"  insert into {placement.insert_fragment} immediately before {occupant.name}"
                f" (line {occupant.line}), or anywhere later in definition order"
            ),
        ]
    elif placement.occupant is not None:
        lines.append("  it already sits at the earliest legal spot")
    else:
        lines += [
            f"  earliest legal spot: the end of the definition order (after order {placement.earliest - 1})",
            (
                f"  append to {placement.insert_fragment}, after {last_node.name} [{last_node.kind},"
                f" {last_node.fragment}:{last_node.line}]"
            ),
        ]
    lines.append(f"  convention: {placement.note}")
    return lines


def violation_lines(violations: list[Violation]) -> list[str]:
    """Every backward reference with both names and both positions."""
    lines = [
        (
            f"forward-reference violations ({len(violations)}) -- a reference to a definition later in"
            " order reads Undefined (falsy) and silently picks the wrong branch:"
        )
    ]
    for violation in violations:
        lines.append(
            f"  {violation.source.kind} '{violation.source.name}' {violation.source.at}"
            f" --{violation.field}--> {violation.target.kind} '{violation.target.name}' {violation.target.at}"
        )
        lines.append(
            f"    move {violation.target.name} (or a copy of its definition) before"
            f" {violation.source.name} in the include chain"
        )
    return lines


def report(graph: Graph, violations: list[Violation]) -> str:
    """The human-readable report: definition order grouped by fragment, per node its dependents."""
    asked = sum(node.kind == QUESTION for node in graph.nodes)
    internals = len(graph.nodes) - asked
    externals = graph.externals()
    dependents = graph.dependents()
    by_fragment: dict[str, list[Node]] = {}
    for node in graph.nodes:
        by_fragment.setdefault(node.fragment, []).append(node)

    lines = [
        (
            f"question graph: {len(graph.nodes)} definitions ({asked} asked questions, {internals} internals),"
            f" {len(graph.edges)} when/default edges, {len(externals)} external reads,"
            f" {len(violations)} forward-reference violations"
        ),
        "definition order is the topological order when the violation count is 0 (copier evaluates in this order)",
        "",
    ]
    for fragment, nodes in by_fragment.items():
        lines.extend(_format_fragment_section(fragment, nodes, graph, dependents))
        lines.append("")
    if externals:
        lines.append(
            f"external leaves ({len(externals)}) -- identifiers that name no definition"
            " (filters/methods); reported, not failures:"
        )
        for name, readers in sorted(externals.items()):
            lines.append(f"  {name:<16} read by {_cap(readers, 4)}")
        lines.append("")
    if violations:
        lines += violation_lines(violations)
        lines.append("")
    lines.append("placement guide: --where NAME [--refs A,B,C] [--kind internal|question]")
    return "\n".join(lines)


def json_report(graph: Graph, violations: list[Violation], placement: Placement | None) -> dict[str, object]:
    """The machine-readable report (`--json`): the graph, the violations, and the placement when asked."""
    dependents = graph.dependents()
    externals = graph.externals()

    report_data: dict[str, object] = {
        "nodes": [_serialize_node(node) for node in graph.nodes],
        "edges": [
            {
                "source": edge.source,
                "field": edge.field,
                "target": edge.target,
                "target_kind": edge.target_kind,
            }
            for edge in graph.edges
        ],
        "dependents": {name: who for name, who in dependents.items() if who},
        "externals": {name: sorted(readers) for name, readers in sorted(externals.items())},
        "violations": [
            {
                "source": violation.source.name,
                "source_at": violation.source.at,
                "field": violation.field,
                "target": violation.target.name,
                "target_at": violation.target.at,
            }
            for violation in violations
        ],
    }
    if placement is not None:
        report_data["placement"] = _serialize_placement(placement)
    return report_data


def _serialize_node(node: Node) -> dict[str, object]:
    """Serialize a Node to a JSON-compatible dictionary."""
    return {
        "name": node.name,
        "kind": node.kind,
        "fragment": node.fragment,
        "line": node.line,
        "order": node.order,
    }


def _serialize_placement(placement: Placement) -> dict[str, object]:
    """Serialize a Placement record to a JSON-compatible dictionary."""
    return {
        "name": placement.name,
        "kind": placement.kind,
        "exists": placement.exists,
        "refs": [_serialize_node(ref) for ref in placement.refs],
        "external_refs": placement.external_refs,
        "earliest_order": placement.earliest,
        "latest_order": placement.latest,
        "occupant": _serialize_node(placement.occupant) if placement.occupant is not None else None,
        "insert_fragment": placement.insert_fragment,
        "current": _serialize_node(placement.current) if placement.current is not None else None,
        "current_position_legal": placement.current_legal,
        "note": placement.note,
    }


def _format_fragment_section(
    fragment: str, nodes: list[Node], graph: Graph, dependents: dict[str, list[str]]
) -> list[str]:
    """Format human-readable lines for one fragment's definitions."""
    first, last = nodes[0].order, nodes[-1].order
    span = f"order {first}" if first == last else f"orders {first}-{last}"
    lines = [f"{fragment} ({span}, {len(nodes)} definitions)"]
    for node in nodes:
        read_names = {edge.target for edge in graph.edges if edge.source == node.name and edge.target != node.name}
        reads = sorted(
            read_names,
            key=lambda name: graph.by_name[name].order if name in graph.by_name else len(graph.nodes),
        )
        lines.append(
            f"  {node.order:>4}  {node.kind:<8} {node.name:<32} :{node.line:<4}"
            f" reads: {_cap(reads, 5) if reads else '-'}"
        )
        if dependents[node.name]:
            lines.append(f"       {'':<8} {'':<32} feeds: {_cap(dependents[node.name], 6)}")
    return lines


def _parse_refs(raw: list[str] | None) -> list[str]:
    """`--refs a,b --refs c` into one flat name list."""
    return [name.strip() for chunk in raw or [] for name in chunk.split(",") if name.strip()]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="The questionnaire's dependency graph: order, references, and where new definitions fit."
    )
    parser.add_argument("--json", action="store_true", help="print the machine-readable report to stdout")
    parser.add_argument(
        "--where",
        metavar="NAME",
        help="placement guide for a new definition named NAME (or, if NAME already exists, its own window)",
    )
    parser.add_argument(
        "--refs",
        action="append",
        metavar="IDENTS",
        help="comma-separated identifiers the new definition reads (with --where on a new name)",
    )
    parser.add_argument(
        "--kind",
        choices=(INTERNAL, QUESTION),
        default=INTERNAL,
        help="what the --where NAME is (internal by default: the motivating case is a new gate's internals)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: build the graph, validate, report (stderr prose; `--json` puts the machine report on stdout)."""
    args = _parse_args(argv)
    try:
        graph = build_graph()
    except (questionnaire.QuestionnaireError, OSError) as exc:
        print(f"cannot read questionnaire: {exc}", file=sys.stderr)
        return 2
    violations = find_violations(graph)
    placement = None
    if args.where is not None:
        if args.where not in graph.by_name and not _parse_refs(args.refs):
            print(
                f"unknown name {args.where!r}: pass --refs ident1,ident2 naming what the new definition reads",
                file=sys.stderr,
            )
            return 2
        placement = place(graph, args.where, _parse_refs(args.refs), args.kind)

    if args.json:
        print(json.dumps(json_report(graph, violations, placement), indent=2))
    elif placement is not None:
        print("\n".join(placement_lines(placement, graph.nodes[-1])), file=sys.stderr)
    else:
        print(report(graph, violations), file=sys.stderr)
    print(
        f"question graph: {len(graph.nodes)} definitions, {len(graph.edges)} edges, {len(violations)} violations",
        file=sys.stderr,
    )
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
