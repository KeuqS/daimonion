#!/usr/bin/env python3
"""What a render of the questionnaire must satisfy, read from one file.

``tests/matrix/invariants.yml`` is the single source for "what a leaf must
satisfy": the artifacts it ships and must not ship, the content predicates
that hold on them, its witness tier and the reason a question type is left out
(TODO.md §26.4 item 4, §23.4 item 2). This module is the only reader of that
file, so the schema is enforced in one place and a typo cannot silently shrink
a class's invariants:

- every row key, ``select`` key and ``select`` value is checked against the
  questionnaire (``project_type`` choices, ``oj_kind`` choices, ``bot_platform``
  choices, the ``include_*`` questions, the ``use_recommended_*`` gates) and
  against the file's own predicate registry and tier vocabulary. An unknown
  key or value raises ``InvariantError`` naming the row;
- every ``project_type`` the questionnaire offers must be selected by a row,
  and a row may not select an excluded one;
- every ``excluded`` entry is held against the live questionnaire: an excluded
  ``project_type`` must not be offered again, an excluded ``question`` must
  still be declared -- either way a stale exclusion fails at load, not in the
  witness output;
- a leaf whose answers carry a dimension value no row selects (a new judge, a
  new layer, a gate nobody declared) is reported by ``unclaimed`` and refused
  by ``expect_for`` instead of quietly resolving to the common layout.

A leaf's expectation is the ordered union of the rows its answers select:
"base first, override last" is the file's order, in which ``ships``/``absent``
concatenate and a later row's tier takes precedence for the classes it
selects.

Consumers:

- ``tools/z3_witnesses.py`` builds each §C6 request's ``expect`` with
  ``expect_for`` and takes everything the leaf space keeps out (the excluded
  project types and the excluded questions) from ``excluded``/``excluded_questions``;
- ``tests/test_recommended_path.py`` derives its fast-path ``MARKERS`` (branch
  tells) with ``markers_for`` and its per-case content checks with
  ``content_for``;
- ``tests/test_render_invariants.py`` looks up which content predicates a leaf
  must satisfy with ``predicates_for``;
- ``tests/test_invariants.py`` holds the loader's contract and the meta checks
  (every witness leaf resolves to a row, and the union reproduces the
  committed ``expect``).
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Template

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:  # tests import tools/ the same way (no root package)
    sys.path.insert(0, str(TOP))

from tools import when_model  # noqa: E402
from tools.questionnaire import GATE_PREFIX  # noqa: E402
from tools.questionnaire import INCLUDE_PREFIX  # noqa: E402
from tools.questionnaire import static_str_choices  # noqa: E402

#: The file this module is the reader of.
PATH = TOP / "tests" / "matrix" / "invariants.yml"

#: The witness tiers a row may declare (tests/test_witness_matrix.py's tiers).
TIERS = ("full", "fast", "best_effort", "none")

#: ``select`` keys that name questionnaire values, checked against it.
NAMED_SELECT_KEYS = ("project_type", "oj_kind", "include", "gate_off", "bot_platform", "domain")

#: ``select`` keys that name a derived questionnaire trait (see ``Facts``).
TRAITS = ("data_science", "kaggle", "src_layout", "web_api")

SELECT_KEYS = (*NAMED_SELECT_KEYS, *TRAITS)

ROW_KEYS = ("id", "select", "ships", "absent", "markers", "content", "predicates", "tier", "why")


class InvariantError(ValueError):
    """A malformed invariants file, or a leaf no row classifies."""


def _matches(key: str, expected: Any, facts: Facts) -> bool:
    """Whether one ``select`` entry holds for a leaf.

    A dispatch table rather than a branch per key: every named key compares
    the leaf's values with the row's by intersection (``bot_platform`` and
    ``oj_kind`` included -- their value is a single item, so the intersection
    is simply "is it one of these"), and the two keys whose shape differs
    (the boolean traits, and ``project_type``, whose membership is checked the
    same way) are handled before it. Adding a select key means adding one
    entry here and one to the vocabulary in ``_select``.
    """
    if key in TRAITS:
        return facts.trait(key) is expected
    intersection = {
        "project_type": (facts.project_type,),
        "oj_kind": (facts.oj_kind,),
        "bot_platform": (facts.bot_platform,),
        "domain": facts.domains,
        "include": facts.includes,
        "gate_off": facts.gates_off,
    }
    return bool(set(expected) & set(intersection[key]))


@dataclass(frozen=True)
class Tier:
    """The witness tier a leaf class is CI-gated for, and the evidence."""

    name: str
    why: str


@dataclass(frozen=True)
class LeafClass:
    """One row: the leaf class it selects, and what that class must satisfy."""

    id: str
    select: dict[str, Any]
    ships: tuple[str, ...]
    absent: tuple[str, ...]
    marker_ships: tuple[str, ...]
    marker_absent: tuple[str, ...]
    predicates: tuple[str, ...]
    content: tuple[tuple[str, str], ...]
    tier: Tier | None
    why: str

    def matches(self, facts: Facts) -> bool:
        """Whether this row selects the leaf those facts describe."""
        return all(_matches(key, expected, facts) for key, expected in self.select.items())


@dataclass(frozen=True)
class Facts:
    """The dimensions of one leaf, derived from its copier answers.

    ``traits`` holds the questionnaire's derived internals, keyed by ``TRAITS``:
    the web_api and data_science layers move where the package lives
    (questions/_internal.yml's ``pkg_dir`` switch) and the kaggle judge brings
    its own workspace, so a row about a package directory has to select on them.
    ``bot_platform`` is the effective platform (the question's copier default
    when the answers omit it); ``bot_platform_asked`` remembers whether the
    answers actually carried it, because that is what a row must claim -- a
    leaf that never answered the question rides the default like the ``oj_kind``
    leaves that are not online_judge, and needs no row of its own.
    """

    project_type: str
    oj_kind: str
    includes: tuple[str, ...]
    gates_off: tuple[str, ...]
    traits: Mapping[str, bool]
    bot_platform: str
    bot_platform_asked: bool
    domains: tuple[str, ...]

    def trait(self, name: str) -> bool:
        """One derived trait of the questionnaire (a key of ``TRAITS``)."""
        return self.traits[name]

    @property
    def label(self) -> str:
        """A one-line name for messages: the dimensions this leaf carries."""
        return "/".join(f"{key}={value}" for key, value in self.dimensions())

    def dimensions(self) -> tuple[tuple[str, str], ...]:
        """Every (dimension, value) pair some row has to select for this leaf."""
        dimensions = [("project_type", self.project_type)]
        if self.oj_kind:
            dimensions.append(("oj_kind", self.oj_kind))
        if self.bot_platform_asked:
            dimensions.append(("bot_platform", self.bot_platform))
        dimensions += [("include", name) for name in self.includes]
        dimensions += [("gate_off", name) for name in self.gates_off]
        # The domain traits are a multiselect, so a leaf answers several at
        # once: each value gets its own dimension pair, and a row may select
        # any of them (or, with several listed, any one).
        dimensions += [("domain", name) for name in self.domains]
        return tuple(dimensions)


@dataclass(frozen=True)
class Vocabulary:
    """The questionnaire's names, as ``select`` values are checked against them."""

    project_types: tuple[str, ...]
    categories: tuple[str, ...]
    oj_kind_choices: dict[str, tuple[str, ...]]
    includes: tuple[str, ...]
    gates: tuple[str, ...]
    bot_platforms: tuple[str, ...]
    bot_platform_default: str
    domains: tuple[str, ...]

    @property
    def oj_kinds(self) -> tuple[str, ...]:
        """Every judge, across every ``oj_category``."""
        return tuple(dict.fromkeys(kind for kinds in self.oj_kind_choices.values() for kind in kinds))


def _derive_leaf_traits(project_type: str, oj_kind: Any, includes: tuple[str, ...]) -> dict[str, bool]:
    """Derive structural traits (web_api, data_science, kaggle, src_layout)."""
    web_api = project_type == "web_api" or "include_web_api" in includes
    data_science = project_type == "data_science" or "include_data_science" in includes
    return {
        "web_api": web_api,
        "data_science": data_science,
        "kaggle": project_type == "online_judge" and oj_kind == "kaggle",
        "src_layout": project_type in ("library", "cli") and not web_api,
    }


def _extract_domain_traits(domain_raw: Any, allowed_domains: tuple[str, ...]) -> tuple[str, ...]:
    """Extract known domain labels from string or list input."""
    chosen = {domain_raw} if isinstance(domain_raw, str) else set(domain_raw or [])
    return tuple(name for name in allowed_domains if name in chosen)


@dataclass(frozen=True)
class Invariants:
    """The loaded file: its rows, predicate registry, exclusions and merge contracts."""

    source: Path
    predicates: dict[str, str]
    excluded: dict[str, str]
    excluded_questions: dict[str, str]
    vocabulary: Vocabulary
    rows: tuple[LeafClass, ...]
    merge_contracts: dict[str, tuple[str, ...]]

    @property
    def renderable_project_types(self) -> tuple[str, ...]:
        """The questionnaire's project types, minus the excluded ones."""
        return tuple(value for value in self.vocabulary.project_types if value not in self.excluded)

    def facts(self, answers: Mapping[str, Any]) -> Facts:
        """The leaf a set of copier answers describes.

        Only the dimensions the questionnaire varies matter here, so an
        answer set that omits a question is read as that question's default
        (false for every gate, layer and judge this file selects on).
        """
        project_type = answers.get("project_type")
        if not isinstance(project_type, str) or project_type not in self.vocabulary.project_types:
            msg = f"leaf {dict(answers)!r} has no project_type the questionnaire offers"
            raise InvariantError(msg)
        includes = tuple(name for name in self.vocabulary.includes if answers.get(name) is True)
        gates_off = tuple(name for name in self.vocabulary.gates if answers.get(name) is False)
        oj_kind = answers.get("oj_kind")
        bot_platform_raw = answers.get("bot_platform")
        traits = _derive_leaf_traits(project_type, oj_kind, includes)
        domains = _extract_domain_traits(answers.get("domain_traits", []), self.vocabulary.domains)
        return Facts(
            project_type=project_type,
            oj_kind=oj_kind if isinstance(oj_kind, str) else "",
            includes=includes,
            gates_off=gates_off,
            traits=traits,
            bot_platform=(
                bot_platform_raw if isinstance(bot_platform_raw, str) else self.vocabulary.bot_platform_default
            ),
            bot_platform_asked=isinstance(bot_platform_raw, str),
            domains=domains,
        )

    def rows_for(self, answers: Mapping[str, Any]) -> tuple[LeafClass, ...]:
        """The rows this leaf selects, in file order."""
        facts = self.facts(answers)
        return tuple(row for row in self.rows if row.matches(facts))

    def unclaimed(self, answers: Mapping[str, Any]) -> tuple[str, ...]:
        """The leaf's dimension values no row selects (empty when classified).

        This is the "no leaf is unclassified" property: a new question, layer
        or judge fails here until a row says what it renders.
        """
        claimed = {(key, value) for row in self.rows for key in NAMED_SELECT_KEYS for value in row.select.get(key, ())}
        return tuple(f"{key}={value}" for key, value in self.facts(answers).dimensions() if (key, value) not in claimed)

    def expect_for(self, answers: Mapping[str, Any]) -> dict[str, list[str]]:
        """The §C6 ``expect`` of this leaf: what it must ship and must not."""
        facts = self.facts(answers)
        missing = self.unclaimed(answers)
        if missing:
            msg = f"leaf {facts.label} is unclassified: no row selects {list(missing)}"
            raise InvariantError(msg)
        files: list[str] = []
        absent: list[str] = []
        for row in self.rows_for(answers):
            files.extend(row.ships)
            absent.extend(row.absent)
        files = list(_unique(files))
        absent = list(_unique(absent))
        both = sorted(set(files) & set(absent))
        if both:
            msg = f"leaf {facts.label} declares {both} both shipped and absent"
            raise InvariantError(msg)
        return {"files": files, "absent": absent}

    def markers_for(self, answers: Mapping[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """The fast-path branch tells of this leaf: what proves it took its branch."""
        ships: list[str] = []
        absent: list[str] = []
        for row in self.rows_for(answers):
            ships.extend(row.marker_ships)
            absent.extend(row.marker_absent)
        return (_unique(ships), _unique(absent))

    def content_for(self, answers: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
        """The (path, substring) checks this leaf's class declares."""
        return _unique_pairs([pair for row in self.rows_for(answers) for pair in row.content])

    def predicates_for(self, answers: Mapping[str, Any]) -> tuple[str, ...]:
        """The content predicates this leaf must satisfy, de-duplicated."""
        return _unique([name for row in self.rows_for(answers) for name in row.predicates])

    def tiers_for(self, answers: Mapping[str, Any]) -> tuple[str, ...]:
        """Every tier the rows of this leaf declare (the class's policy)."""
        return _unique([row.tier.name for row in self.rows_for(answers) if row.tier is not None])


def _unique(items: list[str]) -> tuple[str, ...]:
    """De-duplicate while keeping the declared order."""
    return tuple(dict.fromkeys(items))


def _unique_pairs(pairs: list[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    """De-duplicate (path, substring) pairs while keeping the declared order."""
    return tuple(dict.fromkeys(pairs))


def _static_choices(questions: dict[str, dict], name: str) -> list[str]:
    """A question's choice values (mapping labels normalized), or a loud error when it has none."""
    choices = questions[name].get("choices")
    values = (
        [str(value) for value in choices.values()]
        if isinstance(choices, dict)
        else [str(value) for value in static_str_choices(questions[name])]
    )
    if not values:
        msg = f"question {name!r} has no static choices; the leaf space needs a fixed domain"
        raise InvariantError(msg)
    return values


def _oj_kind_choices(questions: dict[str, dict], category: str) -> list[str]:
    """``oj_kind``'s choices for one ``oj_category`` (its ``choices`` is a template)."""
    rendered = Template(str(questions["oj_kind"]["choices"])).render(oj_category=category)
    return [str(value) for value in yaml.safe_load(rendered)]


def questionnaire_vocabulary(questions: dict[str, dict] | None = None) -> Vocabulary:
    """The questionnaire's names, read through the one parser (tools/questionnaire.py)."""
    if questions is None:
        questions, _order = when_model.load_questions()
    categories = tuple(_static_choices(questions, "oj_category"))
    return Vocabulary(
        project_types=tuple(_static_choices(questions, "project_type")),
        categories=categories,
        oj_kind_choices={category: tuple(_oj_kind_choices(questions, category)) for category in categories},
        includes=tuple(name for name in questions if name.startswith(INCLUDE_PREFIX)),
        gates=tuple(name for name in questions if name.startswith(GATE_PREFIX)),
        bot_platforms=tuple(_static_choices(questions, "bot_platform")),
        bot_platform_default=str(questions["bot_platform"]["default"]),
        domains=tuple(_static_choices(questions, "domain_traits")),
    )


def load(path: Path | None = None) -> Invariants:
    """Read and validate the invariants file, or raise ``InvariantError``."""
    source = PATH if path is None else path
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        msg = f"{source}: not valid YAML: {exc}"
        raise InvariantError(msg) from exc
    if not isinstance(payload, dict):
        msg = f"{source}: the file must be a mapping of sections"
        raise InvariantError(msg)
    unknown = sorted(set(payload) - {"version", "predicates", "excluded", "leaf_classes", "merges"})
    if unknown:
        msg = f"{source}: unknown section(s) {unknown}; the schema is version/predicates/excluded/leaf_classes/merges"
        raise InvariantError(msg)
    predicates = _predicates(payload.get("predicates"), source)
    excluded, excluded_questions = _excluded(payload.get("excluded"), source)
    merge_contracts = _merge_contracts(payload.get("merges"), source)
    questions, _order = when_model.load_questions()
    vocabulary = questionnaire_vocabulary(questions)
    rows = _rows(payload.get("leaf_classes"), vocabulary, predicates, excluded, source)
    invariants = Invariants(
        source=source,
        predicates=predicates,
        excluded=excluded,
        excluded_questions=excluded_questions,
        vocabulary=vocabulary,
        rows=rows,
        merge_contracts=merge_contracts,
    )
    _check_project_type_coverage(invariants)
    _check_excluded_questions(invariants, questions)
    return invariants


def _merge_contracts(value: Any, source: Path) -> dict[str, tuple[str, ...]]:
    """The ``merges:`` section: kind -> the post-conditions it promises.

    Structure only, here: that each kind is a non-empty mapping to non-empty
    condition-name lists. Which condition names have implementations, and that
    the kinds match the merge dispatch, is held by tests/test_merge_contracts.py
    -- the same split as the render predicates, whose implementations live in
    their test module.
    """
    if value is None:
        return {}
    where = f"{source}: merges"
    contracts: dict[str, tuple[str, ...]] = {}
    for kind, conditions in _mapping(value, where).items():
        if not isinstance(kind, str) or not kind:  # pyright: ignore[reportUnnecessaryIsInstance]  WHYNOT: YAML mapping keys are untyped at runtime
            msg = f"{where}: every kind must be a non-empty string"
            raise InvariantError(msg)
        if (
            not isinstance(conditions, list)
            or not conditions
            or not all(isinstance(condition, str) and condition for condition in conditions)
        ):
            msg = f"{where}: {kind} must promise a non-empty list of condition names"
            raise InvariantError(msg)
        if len(set(conditions)) != len(conditions):
            msg = f"{where}: {kind} repeats a condition"
            raise InvariantError(msg)
        contracts[kind] = tuple(conditions)
    return contracts


def _mapping(value: Any, where: str) -> dict[str, Any]:
    """One YAML mapping, or a loud error naming where it should have been."""
    if not isinstance(value, dict):
        msg = f"{where}: expected a mapping, got {type(value).__name__}"
        raise InvariantError(msg)
    return value


def _strings(value: Any, where: str, key: str) -> tuple[str, ...]:
    """A list of non-empty strings (relative paths, artifact names)."""
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        msg = f"{where}: {key} must be a list of non-empty strings"
        raise InvariantError(msg)
    absolute = sorted(item for item in value if item.startswith("/"))
    if absolute:
        msg = f"{where}: {key} must be render-relative, got {absolute}"
        raise InvariantError(msg)
    return tuple(value)


def _why(row: dict[str, Any], where: str) -> str:
    """Every row carries the reason it says what it says."""
    why = row.get("why")
    if not isinstance(why, str) or not why.strip():
        msg = f"{where}: every row needs a `why` (the evidence for what it declares)"
        raise InvariantError(msg)
    return why


def _predicates(value: Any, source: Path) -> dict[str, str]:
    """The predicate registry: id -> why, ids unique and non-empty."""
    where = f"{source}: predicates"
    if not isinstance(value, list) or not value:
        msg = f"{where}: at least one predicate must be declared"
        raise InvariantError(msg)
    found: dict[str, str] = {}
    for index, entry in enumerate(value):
        row = _mapping(entry, f"{where}[{index}]")
        unknown = sorted(set(row) - {"id", "why"})
        if unknown:
            msg = f"{where}[{index}]: unknown key(s) {unknown}"
            raise InvariantError(msg)
        name = row.get("id")
        if not isinstance(name, str) or not name:
            msg = f"{where}[{index}]: `id` must be a non-empty string"
            raise InvariantError(msg)
        if name in found:
            msg = f"{where}: duplicate predicate {name!r}"
            raise InvariantError(msg)
        found[name] = _why(row, f"{where}[{index}] ({name})")
    return found


def _excluded(value: Any, source: Path) -> tuple[dict[str, str], dict[str, str]]:
    """The exclusions: name -> why, split by kind.

    A ``project_type`` entry names a non-goal the questionnaire must not offer
    again (its witness generator keeps it out of the leaf space); a
    ``question`` entry names a live question the leaf space deliberately never
    varies. Either kind carries the one-line reason the coverage output prints.
    """
    where = f"{source}: excluded"
    if value is None:
        return {}, {}
    if not isinstance(value, list):
        msg = f"{where}: must be a list"
        raise InvariantError(msg)
    project_types: dict[str, str] = {}
    questions: dict[str, str] = {}
    for index, entry in enumerate(value):
        row = _mapping(entry, f"{where}[{index}]")
        unknown = sorted(set(row) - {"project_type", "question", "why"})
        if unknown:
            msg = f"{where}[{index}]: unknown key(s) {unknown}"
            raise InvariantError(msg)
        if "project_type" in row and "question" in row:
            msg = f"{where}[{index}]: declare `project_type` or `question`, not both"
            raise InvariantError(msg)
        kind = "project_type" if "project_type" in row else "question"
        name = row.get(kind)
        if not isinstance(name, str) or not name:
            msg = f"{where}[{index}]: `{kind}` must be a non-empty string"
            raise InvariantError(msg)
        if name in project_types or name in questions:
            msg = f"{where}: {name!r} is excluded twice"
            raise InvariantError(msg)
        target = project_types if kind == "project_type" else questions
        target[name] = _why(row, f"{where}[{index}] ({name})")
    return project_types, questions


def _select(value: Any, vocabulary: Vocabulary, excluded: dict[str, str], where: str) -> dict[str, Any]:
    """One row's selector, checked key by key and value by value."""
    select = _mapping(value, f"{where}: select")
    unknown = sorted(set(select) - set(SELECT_KEYS))
    if unknown:
        msg = f"{where}: unknown select key(s) {unknown}; the vocabulary is {list(SELECT_KEYS)}"
        raise InvariantError(msg)
    for key in TRAITS:
        if key in select and not isinstance(select[key], bool):
            msg = f"{where}: select.{key} must be true or false, got {select[key]!r}"
            raise InvariantError(msg)
    offered = {
        "project_type": vocabulary.project_types,
        "oj_kind": vocabulary.oj_kinds,
        "include": vocabulary.includes,
        "gate_off": vocabulary.gates,
        "bot_platform": vocabulary.bot_platforms,
        "domain": vocabulary.domains,
    }
    for key in NAMED_SELECT_KEYS:
        if key not in select:
            continue
        values = select[key]
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            msg = f"{where}: select.{key} must be a list of names"
            raise InvariantError(msg)
        for name in values:
            if key == "project_type" and name in excluded:
                msg = f"{where}: selects the excluded project_type {name!r} ({excluded[name]})"
                raise InvariantError(msg)
            if name not in offered[key]:
                msg = f"{where}: unknown {key} {name!r}; the questionnaire offers {list(offered[key])}"
                raise InvariantError(msg)
    return select


def _markers(row: dict[str, Any], ships: tuple[str, ...], where: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """One row's branch tells: the row's own artifacts unless it says otherwise."""
    markers = _mapping(row.get("markers", {}), f"{where}: markers")
    unknown = sorted(set(markers) - {"ships", "absent"})
    if unknown:
        msg = f"{where}: unknown markers key(s) {unknown}; markers are ships/absent"
        raise InvariantError(msg)
    marker_ships = ships if "ships" not in markers else _strings(markers["ships"], where, "markers.ships")
    marker_absent = _strings(markers.get("absent", []), where, "markers.absent")
    both = sorted(set(marker_ships) & set(marker_absent))
    if both:
        msg = f"{where}: markers declare {both} both shipped and absent"
        raise InvariantError(msg)
    return marker_ships, marker_absent


def _content(row: dict[str, Any], where: str) -> tuple[tuple[str, str], ...]:
    """One row's (path, substring) content checks."""
    raw = row.get("content", [])
    if not isinstance(raw, list):
        msg = f"{where}: content must be a list of [path, substring] pairs"
        raise InvariantError(msg)
    content: list[tuple[str, str]] = []
    for pair in raw:
        if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(item, str) for item in pair):
            msg = f"{where}: content entries must be [path, substring] pairs, got {pair!r}"
            raise InvariantError(msg)
        content.append((pair[0], pair[1]))
    return tuple(content)


def _predicate_names(row: dict[str, Any], predicates: dict[str, str], where: str) -> tuple[str, ...]:
    """The predicate ids one row names, checked against the registry."""
    names = _strings(row.get("predicates", []), where, "predicates")
    unknown = sorted(set(names) - set(predicates))
    if unknown:
        msg = f"{where}: unknown predicate(s) {unknown}; the registry holds {sorted(predicates)}"
        raise InvariantError(msg)
    return names


def _row(
    entry: Any,
    where: str,
    vocabulary: Vocabulary,
    predicates: dict[str, str],
    excluded: dict[str, str],
) -> LeafClass:
    """One leaf class row, checked against the questionnaire and the registry."""
    row = _mapping(entry, where)
    unknown = sorted(set(row) - set(ROW_KEYS))
    if unknown:
        msg = f"{where}: unknown key(s) {unknown}; the schema is {list(ROW_KEYS)}"
        raise InvariantError(msg)
    name = row.get("id")
    if not isinstance(name, str) or not name:
        msg = f"{where}: `id` must be a non-empty string"
        raise InvariantError(msg)
    where = f"{where} ({name})"
    for key in ("select", "ships", "absent"):
        if key not in row:
            msg = f"{where}: `{key}` is required (say `[]`/`{{}}` when the row adds nothing)"
            raise InvariantError(msg)
    ships = _strings(row["ships"], where, "ships")
    marker_ships, marker_absent = _markers(row, ships, where)
    return LeafClass(
        id=name,
        select=_select(row["select"], vocabulary, excluded, where),
        ships=ships,
        absent=_strings(row["absent"], where, "absent"),
        marker_ships=marker_ships,
        marker_absent=marker_absent,
        predicates=_predicate_names(row, predicates, where),
        content=_content(row, where),
        tier=_tier(row.get("tier"), where),
        why=_why(row, where),
    )


def _rows(
    value: Any,
    vocabulary: Vocabulary,
    predicates: dict[str, str],
    excluded: dict[str, str],
    source: Path,
) -> tuple[LeafClass, ...]:
    """Every leaf class row, in composition order."""
    if not isinstance(value, list) or not value:
        msg = f"{source}: leaf_classes must be a non-empty list"
        raise InvariantError(msg)
    rows: list[LeafClass] = []
    seen: set[str] = set()
    for index, entry in enumerate(value):
        where = f"{source}: leaf_classes[{index}]"
        row = _row(entry, where, vocabulary, predicates, excluded)
        if row.id in seen:
            msg = f"{where}: duplicate leaf class id {row.id!r}"
            raise InvariantError(msg)
        seen.add(row.id)
        rows.append(row)
    return tuple(rows)


def _tier(value: Any, where: str) -> Tier | None:
    """One row's witness tier and its evidence."""
    if value is None:
        return None
    tier = _mapping(value, f"{where}: tier")
    unknown = sorted(set(tier) - {"name", "why"})
    if unknown:
        msg = f"{where}: unknown tier key(s) {unknown}; a tier is name/why"
        raise InvariantError(msg)
    name = tier.get("name")
    if name not in TIERS:
        msg = f"{where}: unknown tier {name!r}; the tiers are {list(TIERS)}"
        raise InvariantError(msg)
    return Tier(name=name, why=_why(tier, f"{where} tier {name!r}"))


def _check_project_type_coverage(invariants: Invariants) -> None:
    """Every renderable project type must be selected by some row.

    A project type with no row would resolve to the common layout alone, which
    is exactly the silent weakening this file exists to prevent.
    """
    covered = {name for row in invariants.rows for name in row.select.get("project_type", ())}
    missing = sorted(set(invariants.renderable_project_types) - covered)
    if missing:
        msg = (
            f"{invariants.source}: no row selects project_type(s) {missing}; "
            f"every project type the questionnaire offers needs a row"
        )
        raise InvariantError(msg)
    for name, reason in invariants.excluded.items():
        if name in invariants.vocabulary.project_types:
            msg = f"{invariants.source}: {name!r} is excluded ({reason}) but the questionnaire still offers it"
            raise InvariantError(msg)


def _check_excluded_questions(invariants: Invariants, questions: dict[str, dict]) -> None:
    """An excluded question must still be one the questionnaire declares.

    The entry exists to say why the leaf space never varies a live question;
    once the question is gone the reason describes nothing, and a renamed
    question would otherwise silently un-exclude itself.
    """
    for name, reason in invariants.excluded_questions.items():
        if name not in questions:
            msg = f"{invariants.source}: {name!r} is excluded ({reason}) but the questionnaire no longer declares it"
            raise InvariantError(msg)
