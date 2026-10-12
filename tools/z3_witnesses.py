#!/usr/bin/env python3
"""Enumerate the questionnaire's leaf space as §C6 batch requests (W3).

The questionnaire's full cartesian product is far too large to render (every
`use_recommended_*` gate times every detail question times every project
type), so W3 draws its witnesses from a *declared* subspace, enumerated with
Z3 and rendered one JSONL line per leaf by tools/batch.py:

    leaf = project_type
         x (every `use_recommended_*` gate at its default true, or exactly one off)
         x (no include layer, or exactly one include layer on)
         x (oj_category/oj_kind, when project_type is online_judge)

The three restrictions are the declared leaf space (the W4 audit surface) and
are encoded as Z3 constraints:

- ``z3.AtMost(*[z3.Not(gate) for gate in gates], 1)``: accept every
  recommendation, or open exactly one area's detail questions.
- ``z3.AtMost(*includes, 1)``: at most one opt-in layer on top of the base
  layout (the questionnaire's own `combinable` guard applies on top).
- a gate may only be turned off where its own `when` holds, and an include
  layer only turned on where its `when` holds. Otherwise the answer belongs
  to a question copier never asks and the leaf is not a real branch of the
  questionnaire. Those `when` conditions are *projected* onto the leaf space
  below (the derived `has_data_science` / `has_web_api` / `kaggle` /
  `combinable` internals from questions/_internal.yml are inlined there).
  copier.yml stays the source of truth: every question is loaded through
  the one parser (tools/questionnaire.py, via when_model.load_questions), a
  gate/include with no projection is an error, and
  each projected branch a leaf takes is cross-checked against the shared
  encoder (tools/when_model.py `when_expr_satisfiable`; its grammar and its
  blind spots are documented there, and tests/test_when_model.py is the
  differential test that pins its verdicts to real Jinja evaluation).

Everything else stays at its copier default (tools/batch.py renders with
`defaults=True`): the detail questions an off gate reveals keep their
defaults, so a leaf is one branch of the questionnaire, not a second full
question matrix. Two derived exceptions, both configurations no leaf on the
projection's own axes carries: the integrations-details variant answers an
off integrations gate's details for each web_api leaf (``DETAIL_VARIANTS``:
docker and the MCP scaffold), because "docker + MCP" is a configuration the
inverse template is asked for (TODO §18.8); and the bot-platform variant
answers ``bot_platform`` for each leaf whose bot gate is off
(``BOT_PLATFORM_VARIANTS``: the generated platforms other than the discord
default), so every generated bot platform joins the nightly rehearsal and
the render sweep instead of only the recommended one. `project_type` is its
static choices minus the excluded project
types, and the include dimension is INCLUDE_LAYERS minus nothing: every name
the leaf space keeps out -- web_django, which aborts generation by design
(`_tasks.jinja` exits 1 for it) and so cannot render, and the integration
detail question include_sentry behind use_recommended_integrations, which is
not a layer -- is declared in tests/matrix/invariants.yml's `excluded` with a
one-line reason (TODO §23.4). That file is the single source for exclusions,
as it is for every leaf class's invariants, and this tool accounts for the
whole questionnaire: an include question that is neither a layer nor varied by
the derivation nor declared excluded is an error, and every exclusion must
still describe the live questionnaire. The one-line accounting is printed on
every run, so "enumerated" and "excluded" are both numbers a reader can trust:

    leaves: 272 enumerated, 3 excluded (project_type=web_django, ...)

Usage:

    python tools/z3_witnesses.py --json           # leaf space + leaves
    python tools/z3_witnesses.py --jsonl PATH     # the same, as §C6 lines
    python tools/batch.py tests/matrix/witnesses.jsonl --json

Each leaf carries the answers (tests/test_recommended_path.py:25-34 `BASE`,
so the required Project Details stay fixed) and the render invariants of its
declared layout: the artifact set that shape must produce, and no unrendered
`*.jinja` left behind. Those invariants are not declared here -- they are read
from tests/matrix/invariants.yml through tools/invariants.py, the one source
for what a leaf class must satisfy (TODO.md §26.4 item 4), so this tool cannot
drift from the runner that checks it.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import cast

import z3

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:  # tests import tools/ the same way (no root package)
    sys.path.insert(0, str(TOP))

from tools import answers  # noqa: E402
from tools import invariants  # noqa: E402
from tools import when_model  # noqa: E402

# Every leaf's declared artifacts, its class's tier and the excluded question
# types live in one file, read through its loader (TODO §26.4 item 4): this
# tool is one of its consumers, not a second copy of the answer.
INVARIANTS = invariants.load()

# The Project Details every leaf pins, so fixtures stay self-consistent
# (validators, URLs): the shared set from tools/answers.py, not a copy of
# tests/test_recommended_path.py's (TODO §23.1).
BASE: dict[str, Any] = answers.BASE

# The opt-in layers (questions/_combo.yml) that make up the include
# dimension of the leaf space. include_mcp / include_sentry are detail
# questions behind use_recommended_integrations, not layers.
INCLUDE_LAYERS: tuple[str, ...] = (
    "include_data_science",
    "include_web_api",
    "include_ctf",
    "include_scraping",
    "include_bot",
)

# The integrations details the derived leaf variants answer (``build()``): the
# docker artifact and the MCP scaffold. include_mcp is also the include_*
# question ``_check_includes`` accounts for as varied -- it is behind
# use_recommended_integrations, so the Z3 projection keeps it at its default
# and the derivation is what turns it on.
DETAIL_VARIANTS: tuple[str, ...] = ("docker", "include_mcp")

# The bot platforms the derived leaf variants answer (``build()``): the
# generated platforms no leaf on the projection's own axes carries. The
# projection mirrors ``use_recommended_bot`` per gate, and those gate-off
# leaves keep ``bot_platform`` at its copier default (discord), so without the
# derivation a leaf never answers "slack"/"line"/"gmail" -- the same gap
# DETAIL_VARIANTS closes for docker and the MCP scaffold (a515149a), and the
# reason ``predicates`` reports bot_slack_effective and friends as never
# splitting the space. discord is absent on purpose: it is the gate-off leaf's
# own default, so that base leaf already claims it.
BOT_PLATFORM_VARIANTS: tuple[str, ...] = ("slack", "line", "gmail")

# The domain-trait variants: the `domain_traits` multiselect's choices, each
# answered alone and all of them answered together.
#
# This is the axis the leaf space never had. Every leaf before it kept
# `domain_traits` at its copier default (empty), so nothing rendered a domain
# section -- and nothing could test that two domains *co-occurring* behave:
# one section each, no duplication, both ethics sections present, and no
# dependency double-declared. The multiselect is exactly the shape that makes
# "select both" a real configuration, so the space has to carry it.
#
# `together` is the additivity probe (TODO §30): the union of the solo leaves'
# contributions must equal the combined leaf's. A single derived leaf is
# enough for that check because the sections and dependencies are independent
# per domain -- if the union of {face} and {medtech} equals {face, medtech},
# any larger selection follows by induction.
DOMAIN_TRAIT_CHOICES: tuple[str, ...] = ("personal-data", "face-recognition", "medtech")

# The leaves the domain variants are hosted on: the two ids whose answers put
# them on either side of the pair a domain trait can interact with (does the
# project kind carry an src/ package or not, and does the data-science layout
# hold -- the second decides whether the medtech trait also lands the CARE
# sheet in data/. AGENTS.md itself stopped being the discriminator when it
# became a constant true on 2026-09-21). Every other leaf renders the same
# domain appendix as one of these, so hosting more would cost leaves without
# covering a new case.
DOMAIN_TRAIT_HOSTS: frozenset[str] = frozenset(
    {
        "project_type=data_science/gate=recommended",
        "project_type=cli/gate=recommended",
    }
)

# The variant labels: each choice alone, then all of them together -- the
# co-occurrence answer the multiselect exists for, and the leaf the additivity
# check compares against the solo ones (build()). `all` is appended only when
# there is more than one choice to combine, so a single-trait questionnaire
# does not mint a leaf that says nothing. Each list is `list[str]` (not the
# literal choices' own type) so the optional `all` entry does not narrow the
# tuple's element type.
DOMAIN_TRAIT_SOLO_VARIANTS: tuple[tuple[str, list[str]], ...] = tuple(
    (str(choice), [str(choice)]) for choice in DOMAIN_TRAIT_CHOICES
)
DOMAIN_TRAIT_VARIANTS: tuple[tuple[str, list[str]], ...] = DOMAIN_TRAIT_SOLO_VARIANTS + (
    (("all", [str(choice) for choice in DOMAIN_TRAIT_CHOICES]),) if len(DOMAIN_TRAIT_CHOICES) > 1 else ()
)

# The `distribution` answers that change what the ethics appendix carries. The
# default (`in-house`) ships no distribution-dependent section, so only the
# two that do need a leaf: `commercial` (the CRA obligations) and `oss` (the
# open-release case, where a project is published but not sold -- the
# distinction EU 2024/2847's art. 24 exemption turns on). A leaf answering
# both covers the overlap.
DISTRIBUTION_VARIANTS: tuple[tuple[str, list[str]], ...] = (
    ("commercial", ["commercial"]),
    ("oss", ["oss"]),
    ("commercial+oss", ["commercial", "oss"]),
)

GATE_PREFIX = "use_recommended_"

# gates whose `when` the projection below keeps at "always asked".
UNCONDITIONAL_GATES: tuple[str, ...] = (
    "use_recommended_toolchain",
    "use_recommended_polish",
    "use_recommended_docs",
    "use_recommended_quality",
    "use_recommended_license",
    "use_recommended_integrations",
    "use_recommended_security",
)

# gates whose `when` the projection below mirrors explicitly.
PROJECTED_GATES: tuple[str, ...] = (
    "use_recommended_agent",
    "use_recommended_data_science",
    "use_recommended_web_api",
    "use_recommended_scraping",
    "use_recommended_bot",
)


@dataclass(frozen=True)
class Leaf:
    """One declared leaf: its id, the copier answers, and the invariants."""

    id: str
    note: str
    answers: dict[str, Any]
    expect: dict[str, Any]

    def as_request(self) -> dict[str, Any]:
        """The §C6 batch request line for this leaf.

        The dest is a directory name, so `/` and `:` cannot survive (they are a
        path separator and Windows-hostile); `=` goes too, but for the secret
        scanner: this file is text gitleaks reads, and a leaf that joins the
        project_type ``web_api`` to its gate and include axes with underscores
        reads to its generic-api-key rule as the keyword ``api``, a separator
        and a high-entropy value -- which is how the hygiene job first went
        red. The id keeps its `=` because the rule's span stops at the `/` of
        the slash-separated form.
        """
        return {
            "id": self.id,
            "note": self.note,
            "ref": "HEAD",
            "dest": self.id.replace("/", "_").replace(":", "-").replace("=", "-"),
            "answers": self.answers,
            "expect": self.expect,
        }


@dataclass(frozen=True)
class Space:
    """The Z3 handles of the declared leaf space."""

    solver: z3.Solver
    pt: z3.ArithRef
    oj_category: z3.ArithRef
    oj_kind: z3.ArithRef
    gates: dict[str, z3.BoolRef]
    includes: dict[str, z3.BoolRef]
    pt_domain: list[str]
    oj_categories: list[str]
    oj_kinds: dict[str, list[str]]

    @property
    def variables(self) -> list[Any]:
        """Every Z3 variable of the leaf space (the blocking-clause scope)."""
        return [self.pt, self.oj_category, self.oj_kind, *self.gates.values(), *self.includes.values()]


def _check_includes(questions: dict[str, dict]) -> None:
    """Every include_* question the questionnaire asks is accounted for.

    It is either a layer varied here, a detail question ``DETAIL_VARIANTS``
    varies on a derived leaf variant, or a declared exclusion
    (tests/matrix/invariants.yml's ``excluded``, which also names the excluded
    project types), never a silent default (TODO §23.4).
    """
    # The projection keeps these out (their values derive from the answers, not
    # from the space); build()'s derivation varies them instead.
    varied_details = frozenset(DETAIL_VARIANTS)
    excluded_questions = INVARIANTS.excluded_questions
    overlapped = sorted(set(excluded_questions) & set(INCLUDE_LAYERS))
    if overlapped:
        msg = f"{overlapped} are both leaf-space layers and declared excluded; the leaf space contradicts itself"
        raise SystemExit(msg)
    unaccounted = sorted(
        name
        for name in questions
        if name.startswith("include_")
        and name not in INCLUDE_LAYERS
        and name not in excluded_questions
        and name not in varied_details
    )
    if unaccounted:
        msg = (
            f"include question(s) {unaccounted} are neither a leaf-space layer nor declared excluded; "
            f"add them to INCLUDE_LAYERS or to tests/matrix/invariants.yml's `excluded` with a reason"
        )
        raise SystemExit(msg)


def _validate_gate_projections(questions: dict[str, dict], gates: dict[str, z3.BoolRef]) -> None:
    """Validate that every gate in the questionnaire has a known projection."""
    for name in (*UNCONDITIONAL_GATES, *PROJECTED_GATES, *INCLUDE_LAYERS):
        if name not in questions:
            msg = f"{name!r} is declared in this tool but gone from the questionnaire; update the leaf space"
            raise SystemExit(msg)
    unprojected = set(gates) - set(UNCONDITIONAL_GATES) - set(PROJECTED_GATES)
    if unprojected:
        msg = f"gate(s) {sorted(unprojected)} have no projection; declare their `when` in this tool"
        raise SystemExit(msg)
    for name in UNCONDITIONAL_GATES:
        when = questions[name].get("when")
        if when is not None and name != "use_recommended_toolchain":
            msg = f"gate {name!r} is no longer unconditional (when={when!r}); project its `when` here"
            raise SystemExit(msg)
    _check_includes(questions)


@dataclass(frozen=True)
class _LeafCoordinates:
    """Z3 variables and domain tables indexing the leaf space's coordinate axes."""

    pt: z3.ArithRef
    oj_category: z3.ArithRef
    oj_kind: z3.ArithRef
    index: dict[str, int]
    pt_domain: list[str]
    oj_categories: list[str]
    oj_kinds: dict[str, list[str]]


@dataclass(frozen=True)
class _DerivedInternals:
    """The 4 derived internal variables projected into the leaf space."""

    kaggle: z3.BoolRef
    combinable: z3.BoolRef
    has_web_api: z3.BoolRef
    has_data_science: z3.BoolRef


def _model_derived_internals(
    coords: _LeafCoordinates,
    includes: dict[str, z3.BoolRef],
) -> _DerivedInternals:
    """Model the 4 derived internals read by the leaf space: kaggle, combinable, has_web_api, has_data_science."""
    kaggle_category = coords.oj_categories.index("data_science")
    kaggle = _bool(
        z3.And(
            coords.pt == coords.index["online_judge"],
            coords.oj_category == kaggle_category,
            coords.oj_kind == coords.oj_kinds["data_science"].index("kaggle"),
        )
    )
    combinable = _bool(
        z3.Or(*(coords.pt == coords.index[name] for name in ("library", "cli", "web_api", "data_science")), kaggle)
    )
    has_web_api = _bool(z3.Or(coords.pt == coords.index["web_api"], z3.And(includes["include_web_api"], combinable)))
    has_data_science = _bool(
        z3.Or(coords.pt == coords.index["data_science"], z3.And(includes["include_data_science"], combinable))
    )
    return _DerivedInternals(kaggle, combinable, has_web_api, has_data_science)


def _project_gate_when_conditions(
    coords: _LeafCoordinates,
    gates: dict[str, z3.BoolRef],
    includes: dict[str, z3.BoolRef],
    derived: _DerivedInternals,
) -> dict[str, z3.BoolRef]:
    """Project questionnaire when-conditions onto the leaf space."""
    asked: dict[str, z3.BoolRef] = dict.fromkeys(
        [*gates, *includes],
        z3.BoolVal(True),  # noqa: FBT003  WHYNOT: z3's own API takes a Python bool.
    )
    pt, idx = coords.pt, coords.index
    asked["use_recommended_agent"] = _bool(z3.Or(pt == idx["library"], pt == idx["cli"]))
    asked["use_recommended_data_science"] = _bool(derived.has_data_science)
    asked["use_recommended_web_api"] = _bool(derived.has_web_api)
    asked["use_recommended_scraping"] = includes["include_scraping"]
    asked["use_recommended_bot"] = includes["include_bot"]
    asked["include_data_science"] = _bool(z3.Or(pt == idx["library"], pt == idx["cli"], pt == idx["web_api"]))
    asked["include_web_api"] = _bool(
        z3.Or(pt == idx["library"], pt == idx["cli"], pt == idx["data_science"], derived.kaggle)
    )
    asked["include_ctf"] = _bool(z3.Or(pt == idx["library"], pt == idx["cli"]))
    asked["include_scraping"] = _bool(pt == idx["cli"])
    asked["include_bot"] = _bool(z3.Or(pt == idx["cli"], pt == idx["web_api"]))
    return asked


def _create_leaf_solver(
    coords: _LeafCoordinates,
    gates: dict[str, z3.BoolRef],
    includes: dict[str, z3.BoolRef],
    asked: dict[str, z3.BoolRef],
) -> z3.Solver:
    """Build the Z3 solver enforcing domain bounds, at-most-one restrictions, and ask implications."""
    solver = z3.Solver()
    solver.add(coords.pt >= 0, coords.pt < len(coords.pt_domain))
    solver.add(coords.oj_category >= 0, coords.oj_category < len(coords.oj_categories))
    solver.add(z3.AtMost(*[z3.Not(gate) for gate in gates.values()], 1))
    solver.add(z3.AtMost(*includes.values(), 1))
    for name, gate in gates.items():
        solver.add(z3.Implies(z3.Not(gate), asked[name]))
    for name, include in includes.items():
        solver.add(z3.Implies(include, asked[name]))
    for category, kinds in coords.oj_kinds.items():
        position = coords.oj_categories.index(category)
        asked_kind = z3.Or(*(coords.oj_kind == i for i in range(len(kinds))))
        solver.add(
            z3.Implies(z3.And(coords.pt == coords.index["online_judge"], coords.oj_category == position), asked_kind)
        )
    solver.add(
        z3.Implies(coords.pt != coords.index["online_judge"], z3.And(coords.oj_category == 0, coords.oj_kind == 0))
    )
    return solver


def _build_space(questions: dict[str, dict], pt_domain: list[str], oj_categories: list[str]) -> Space:
    """Assert the leaf-space restrictions on top of the questionnaire's variables."""
    gates = {name: z3.Bool(name) for name in questions if name.startswith(GATE_PREFIX)}
    includes = {name: z3.Bool(name) for name in INCLUDE_LAYERS}
    _validate_gate_projections(questions, gates)

    index = {name: position for position, name in enumerate(pt_domain)}
    pt = z3.Int("project_type")
    oj_category = z3.Int("oj_category")
    oj_kind = z3.Int("oj_kind")
    oj_kinds = {category: list(INVARIANTS.vocabulary.oj_kind_choices[category]) for category in oj_categories}

    coords = _LeafCoordinates(pt, oj_category, oj_kind, index, pt_domain, oj_categories, oj_kinds)
    derived = _model_derived_internals(coords, includes)
    asked = _project_gate_when_conditions(coords, gates, includes, derived)
    solver = _create_leaf_solver(coords, gates, includes, asked)
    return Space(solver, pt, oj_category, oj_kind, gates, includes, pt_domain, oj_categories, oj_kinds)


def _bool(expr: object) -> z3.BoolRef:
    """One z3 formula as a BoolRef.

    z3's stubs widen `And`/`Or`/probe results to `BoolRef | Probe` and an `Int`
    comparison to `BoolRef | Literal[False]`; every value here is a formula, so
    the cast is the honest narrowing (the leaf is re-checked against the
    questionnaire's own encoder before it is written out).
    """
    return cast("z3.BoolRef", expr)


def _models(space: Space) -> list[dict[Any, Any]]:
    """Enumerate every satisfying model, blocking each one as it is found."""
    found: list[dict[Any, Any]] = []
    while space.solver.check() == z3.sat:
        model = space.solver.model()
        values = {var: model.eval(var, model_completion=True) for var in space.variables}
        found.append(values)
        space.solver.add(z3.Or(*[var != value for var, value in values.items()]))
    return found


def _verify_projected_branches(questions: dict[str, dict], branches: list[str], domains: dict[str, list[str]]) -> None:
    """Verify each projected branch is satisfiable in the shared when_model encoder."""
    for name in branches:
        when = questions[name].get("when")
        if isinstance(when, str) and not when_model.when_expr_satisfiable(when, domains, z3):
            msg = f"branch {name!r} projected as reachable but its when {when!r} is unsatisfiable"
            raise SystemExit(msg)


def _build_leaf_answers_and_parts(
    space: Space, values: dict[Any, Any], project_type: str, off: list[str], on: list[str]
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Build the answers dict, id path parts, and descriptive notes for one leaf."""
    parts = [f"project_type={project_type}", f"gate=off:{off[0]}" if off else "gate=recommended"]
    answers: dict[str, Any] = {**BASE, "project_type": project_type}
    if project_type == "online_judge":
        category = space.oj_categories[values[space.oj_category].as_long()]
        oj_kind = space.oj_kinds[category][values[space.oj_kind].as_long()]
        answers["oj_category"] = category
        answers["oj_kind"] = oj_kind
        parts.append(f"oj={category}/{oj_kind}")
    if on:
        parts.append(f"include={on[0]}")
        answers[on[0]] = True
    if off:
        answers[off[0]] = False

    note = ["all use_recommended_* gates at their default"]
    if off:
        note.append(f"one gate off: {off[0]} (its detail questions stay at their defaults)")
    if on:
        note.append(f"one include layer on: {on[0]}")
    return answers, parts, note


def _leaf(
    questions: dict[str, dict],
    space: Space,
    values: dict[Any, Any],
    domains: dict[str, list[str]],
) -> Leaf:
    """Map one Z3 model to its §C6 request (id, answers, expected invariants)."""
    project_type = space.pt_domain[values[space.pt].as_long()]
    off = [name for name, gate in space.gates.items() if not z3.is_true(values[gate])]
    on = [name for name, include in space.includes.items() if z3.is_true(values[include])]
    _verify_projected_branches(questions, [*off, *on], domains)
    answers, parts, note = _build_leaf_answers_and_parts(space, values, project_type, off, on)
    return Leaf(
        id="/".join(parts),
        note=f"W3 Z3 witness: {'; '.join(note)}",
        answers=answers,
        expect=INVARIANTS.expect_for(answers),
    )


def exclusions() -> dict[str, str]:
    """Every name the leaf space keeps out, kind-prefixed, with its reason.

    The single source is tests/matrix/invariants.yml's `excluded` section: a
    `project_type=` entry is a non-goal the questionnaire must not offer
    again, a `question=` entry is a live question every leaf keeps at its
    copier default. The prefix keeps the two kinds apart in the coverage
    output and in the `--json` leaf space.
    """
    excluded = {f"project_type={name}": why for name, why in INVARIANTS.excluded.items()}
    excluded.update((f"question={name}", why) for name, why in INVARIANTS.excluded_questions.items())
    return excluded


def completeness(leaf_space: dict[str, Any], leaves: list[Leaf]) -> str:
    """The one-line accounting of the enumeration (TODO §23.4).

    "Enumerated" and "excluded" are both numbers a reader can trust: the
    leaves the projection produced, and the named exclusions it did not.
    """
    excluded = leaf_space["excluded"]
    names = ", ".join(sorted(excluded)) or "none"
    return f"leaves: {len(leaves)} enumerated, {len(excluded)} excluded ({names})"


def _detail_variants(base_leaves: list[Leaf]) -> list[Leaf]:
    """The integrations-details and bot-platform variants.

    Both vary *detail* questions the projection keeps at their copier
    defaults, on the leaves where the owning gate is off:

    - docker + the MCP scaffold on the web_api leaf whose integrations gate is
      off -- the configuration the inverse template's flagship query matches
      (TODO §18.8);
    - one leaf per generated bot platform (slack / line / gmail) on each leaf
      whose bot gate is off, so every platform joins the nightly rehearsal and
      the render sweep instead of only the recommended discord.
    """
    variants: list[Leaf] = []
    for leaf in base_leaves:
        if leaf.answers.get("use_recommended_integrations") is False and leaf.answers.get("project_type") == "web_api":
            chosen = {**leaf.answers, **dict.fromkeys(DETAIL_VARIANTS, True)}
            variants.append(
                Leaf(
                    id=f"{leaf.id}/details=chosen",
                    note=f"{leaf.note}; integrations details chosen ({', '.join(DETAIL_VARIANTS)} on)",
                    answers=chosen,
                    expect=INVARIANTS.expect_for(chosen),
                )
            )
    for leaf in base_leaves:
        if leaf.answers.get("use_recommended_bot") is not False:
            continue
        variants += [
            Leaf(
                id=f"{leaf.id}/bot={platform}",
                note=f"{leaf.note}; bot platform {platform} chosen",
                answers={**leaf.answers, "bot_platform": platform},
                expect=INVARIANTS.expect_for({**leaf.answers, "bot_platform": platform}),
            )
            for platform in BOT_PLATFORM_VARIANTS
        ]
    return variants


def _leaf_domain_trait_variants(leaf: Leaf) -> list[Leaf]:
    """Derive domain_traits variants hosted on this leaf."""
    return [
        Leaf(
            id=f"{leaf.id}/domain={label}",
            note=f"{leaf.note}; domain traits selected ({', '.join(choices)})",
            answers={**leaf.answers, "domain_traits": choices},
            expect=INVARIANTS.expect_for({**leaf.answers, "domain_traits": choices}),
        )
        for label, choices in DOMAIN_TRAIT_VARIANTS
    ]


def _leaf_distribution_variants(leaf: Leaf) -> list[Leaf]:
    """Derive distribution variants hosted on this leaf."""
    return [
        Leaf(
            id=f"{leaf.id}/distribution={label}",
            note=f"{leaf.note}; distribution answered ({', '.join(choices)})",
            answers={**leaf.answers, "distribution": choices},
            expect=INVARIANTS.expect_for({**leaf.answers, "distribution": choices}),
        )
        for label, choices in DISTRIBUTION_VARIANTS
    ]


def _answer_axis_variants(base_leaves: list[Leaf]) -> list[Leaf]:
    """The `domain_traits` and `distribution` variants, on their declared hosts.

    Both are multiselects the projection keeps at their empty/default answer,
    so without these derivations no render carries a domain section or the CRA
    duties, and no test could see two selections interact.

    Hosted on DOMAIN_TRAIT_HOSTS rather than on every leaf: what they can
    differ by is whether the data-science layout holds (data_science: the
    layout side, where CARE also lands; cli: no layout). Hosting every leaf
    would add ~700 leaves for no new coverage.

    `base_leaves` is never appended to -- the variants are returned, so a
    variant cannot be re-hosted on itself (the duplicate ids this replaced).
    """
    hosts = [leaf for leaf in base_leaves if leaf.id in DOMAIN_TRAIT_HOSTS]
    missing = sorted(DOMAIN_TRAIT_HOSTS - {leaf.id for leaf in hosts})
    if missing:
        msg = f"DOMAIN_TRAIT_HOSTS names leaves the space no longer enumerates: {missing}"
        raise SystemExit(msg)
    variants: list[Leaf] = []
    for leaf in hosts:
        variants.extend(_leaf_domain_trait_variants(leaf))
        variants.extend(_leaf_distribution_variants(leaf))
    return variants


def _derived_variants(base_leaves: list[Leaf]) -> list[Leaf]:
    """Every derived leaf: the detail variants plus the answer-axis ones.

    The projection enumerates the questionnaire's Z3 axes; these add the
    configurations it deliberately does not model, each because the axis is a
    detail rather than a dimension. See the two helpers for what each covers.
    """
    return _detail_variants(base_leaves) + _answer_axis_variants(base_leaves)


def build() -> tuple[dict[str, Any], list[Leaf]]:
    """Return the declared leaf space and its enumerated leaves."""
    questions, _order = when_model.load_questions()
    pt_domain = list(INVARIANTS.renderable_project_types)
    oj_categories = list(INVARIANTS.vocabulary.categories)
    space = _build_space(questions, pt_domain, oj_categories)
    domains = when_model.str_domains(questions, pt_domain)
    leaves = [_leaf(questions, space, values, domains) for values in _models(space)]

    leaves.extend(_derived_variants(leaves))
    _check_unique_ids(leaves)

    leaf_space = {
        "project_type": pt_domain,
        "gates": list(space.gates),
        "includes": list(INCLUDE_LAYERS),
        "oj_category": oj_categories,
        "oj_kind": space.oj_kinds,
        "restrictions": [
            "every use_recommended_* gate at its default (true), or exactly one off",
            "no include layer, or exactly one include layer on",
            "a gate may only be off, and an include only on, where its own `when` holds",
            "every other question stays at its copier default",
            (
                f"the web_api leaves with the integrations gate off also get a variant leaf answering "
                f"that gate's details ({', '.join(DETAIL_VARIANTS)})"
            ),
            (
                f"the use_recommended_bot gate-off leaves also get a variant leaf per generated "
                f"bot platform ({', '.join(BOT_PLATFORM_VARIANTS)}; discord is the gate-off leaf's own default)"
            ),
        ],
        "enumerated": len(leaves),
        "excluded": exclusions(),
    }
    return leaf_space, leaves


def _check_unique_ids(leaves: list[Leaf]) -> None:
    """Fail loudly when two leaves share an id (a variant re-hosted on itself)."""
    leaves.sort(key=lambda leaf: leaf.id)
    ids = [leaf.id for leaf in leaves]
    if len(ids) != len(set(ids)):
        msg = f"leaf ids are not unique: {sorted(name for name in ids if ids.count(name) > 1)}"
        raise SystemExit(msg)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enumerate the questionnaire's Z3 witness leaves (W3).")
    parser.add_argument("--json", action="store_true", help="print the leaf space and every leaf")
    parser.add_argument("--jsonl", type=Path, default=None, help="write the leaves as §C6 batch requests")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: enumerate, then print and/or write the §C6 request lines."""
    args = _parse_args(argv)
    leaf_space, leaves = build()
    # The accounting goes to stderr: stdout stays one JSON document for the
    # consumers that parse it (`--json`), and `task witness`'s log keeps the
    # numbers next to the generation it just did.
    print(completeness(leaf_space, leaves), file=sys.stderr)
    if args.jsonl is not None:
        args.jsonl.parent.mkdir(parents=True, exist_ok=True)
        lines = "".join(json.dumps(leaf.as_request(), sort_keys=False) + "\n" for leaf in leaves)
        args.jsonl.write_text(lines, encoding="utf-8")
    if args.json or args.jsonl is None:
        payload = {"leaf_space": leaf_space, "leaves": [leaf.as_request() for leaf in leaves]}
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
