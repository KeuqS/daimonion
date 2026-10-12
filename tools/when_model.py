#!/usr/bin/env python3
"""Model the questionnaire's `when` expressions, on the one shared parse.

Copier's `when` conditions are Jinja, and the questionnaire's shape is only
checkable if something can reason about them: which project types can reach a
question, which gate is asked where, whether a branch is satisfiable at all.
This module is that reasoner, and it encodes a `when` expression as a Z3
formula. The layering is fixed: tools/questionnaire.py owns the
questionnaire's *shape* (the one `!include` resolver, which also keeps each
question's source fragment, plus the gate/layer prefixes, the internal
predicates and the static choice values), and this module owns only the
`when`-expression semantics layered on the raw view it exposes
(`load_questions` delegates to `questionnaire.load_raw_questions`).
Copier's own loader is not consulted here -- it survives as a differential
oracle in tests, which pin that it agrees with the parser.

What it models
- the `when` grammar the questionnaire actually uses: `==`, `!=`, `in` and
  `not in` over question references and string literals, combined with
  `and`/`or`/`not` and parentheses;
- a question with static `choices` as an Int over its choice values, so
  `x == 'value'` becomes `Int(x) == domain.index('value')` and `x in [a, b]`
  becomes a disjunction. A literal outside the domain is False, which is what
  makes a typo'd `project_type == 'librry'` unsatisfiable;
- every other identifier as a free boolean, and each question is checked
  independently with the earlier gates free.

What it deliberately does not model
- Jinja beyond that subset: filters, attribute access, arithmetic, and `is`
  tests (the tokenizer raises on them rather than guessing).
- a comparison whose operand is a plain boolean identifier, or a boolean
  against a string: Jinja's `False == 'x'` is never true, but an unpinned str
  reference is a free boolean here, so the two cases are indistinguishable and
  the comparison stays free. Two str references (`x == y`) *are* modeled:
  equality of their choice indices.
- A question whose `choices` are templated or absent (`package_manager`,
  `oj_kind`) has no fixed domain, so it is a free boolean unless the caller
  supplies a domain for it. A comparison against such a variable is then
  unconstrained: satisfiable whatever the answer. Real Jinja is the only
  oracle for that, and tests/test_when_model.py is the differential test
  against it.
- Ask order and the derived internals: a `when: false` variable (has_web_api,
  kaggle, ...) is a free boolean, never computed from the questions it
  derives from.
- Unknown identifiers: a name that is not a question is satisfiable by
  design, so a misspelled variable is invisible here. The reference check in
  tests/test_copier_structure.py owns that class of bug.

Callers: tests/test_copier_structure.py (the questionnaire's shape),
tools/z3_witnesses.py (the leaf space, whose branches are cross-checked
through this encoder) and tests/test_when_model.py (the differential test
against copier/Jinja evaluation).
"""

from __future__ import annotations

import functools
import re
import sys
from collections.abc import Mapping
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:  # tools/ is no root package (pyproject.toml)
    sys.path.insert(0, str(TOP))

from tools import questionnaire  # noqa: E402

COPIER_YML = TOP / "copier.yml"


def load_questions() -> tuple[dict[str, dict], list[str]]:
    """Return ({key: raw-question-dict}, ordered-keys) from copier.yml.

    A thin delegate to `questionnaire.load_raw_questions`: the dataclass
    parser in tools/questionnaire.py is the one `!include` resolver (only its
    Question records keep the source fragment a question came from, which the
    raw view cannot carry), so this module re-parses nothing and owns the
    `when`-expression semantics on top. The shape is unchanged -- the same
    raw dicts in copier's ask order the module always returned.
    """
    return questionnaire.load_raw_questions(COPIER_YML)


#: Jinja keywords `jinja_identifiers` reports as identifiers (the same set
#: tests/test_when_model.py pins): they are operators of the grammar, never
#: variables a condition reads. Consumers of the scanner subtract this set;
#: tools/question_graph.py extends it with `if`/`else`, which only its
#: `default:` expressions use.
JINJA_OPERATORS = frozenset(
    {"and", "or", "not", "in", "true", "false", "True", "False", "is", "defined", "none", "None"}
)


def jinja_identifiers(text: str) -> set[str]:
    """All identifiers inside {{ }} / {% %} blocks in ``text``.

    Only full Jinja tags are scanned (a stray ``{``/``}`` in a template body
    is never treated as a tag boundary). Within each tag, string literals
    (e.g. ``== 'ros2'``) and Jinja keywords are not identifiers; GitHub
    Actions expressions (``${{ secrets.X }}``) are not Jinja and are skipped.
    """
    found: set[str] = set()
    # GitHub Actions expressions (${{ secrets.X }}) are not Jinja; blank them
    # out first so they are never scanned.
    text = re.sub(r"\$\{\{[^}]*\}\}", " ", text)
    # {% raw %}...{% endraw %} blocks are emitted verbatim for another tool
    # (git-cliff's cliff.toml.jinja), not rendered by copier.
    text = re.sub(r"\{%-?\s*raw\s*-?%\}.*?\{%-?\s*endraw\s*-?%\}", " ", text, flags=re.DOTALL)
    for tag in re.findall(r"\{\{.*?\}\}|\{%.*?%\}", text, re.DOTALL):
        # Drop quoted strings inside this tag only — tag-internal quotes like
        # == "BSL-1.0" must not span across to quotes in the body text.
        stripped = re.sub(r"'[^']*'|\"[^\"]*\"", " ", tag)
        for m in re.finditer(r"[A-Za-z_][A-Za-z0-9_]*", stripped):
            # Attribute access: in `x.attr`, `attr` is not a variable.
            if m.start() > 0 and stripped[m.start() - 1] == ".":
                continue
            # Keyword argument: in `filter(keyword=value)`, `keyword` is not a
            # variable (`==` comparisons are unaffected — two '=' signs).
            rest = stripped[m.end() :]
            if rest.startswith("=") and not rest.startswith("=="):
                continue
            found.add(m.group(0))
    return found


def static_str_choices(question: dict) -> list[str]:
    """Return a question's static (non-templated) choice values, or [].

    Delegates to tools/questionnaire.py (the one parser owns every reading of
    a question's shape); kept here so the encoder's callers keep one import.
    """
    return questionnaire.static_str_choices(question)


def str_domains(questions: dict[str, dict], pt_domain: list[str] | None = None) -> dict[str, list[str]]:
    """The str-typed domain of every question the questionnaire's `when`s read.

    A referenced question with static choices contributes its choice values.
    A bool question, a free-text question, and a question whose choices are
    templated (its values depend on the earlier answers) are left out, so the
    encoder models them as free booleans. `pt_domain` is the project_type
    domain the caller's space uses; it defaults to the question's own static
    choices.
    """
    if pt_domain is None:
        pt_domain = static_str_choices(questions["project_type"])
    referenced: set[str] = set()
    for question in questions.values():
        when = question.get("when")
        if isinstance(when, str):
            referenced |= jinja_identifiers(when)
    domains: dict[str, list[str]] = {"project_type": pt_domain}
    for name in sorted(referenced):
        question = questions.get(name)
        if question is None or question.get("type") == "bool":
            continue
        values = static_str_choices(question)
        if values:
            domains[name] = values
    return domains


def _scan_token(text: str, stripped: str, i: int, out: list[str]) -> int:
    """Consume one token at `stripped[i]`, appending to `out`; return the next index."""
    n = len(stripped)
    c = stripped[i]
    if c.isspace():
        return i + 1
    if c in "()[],":
        out.append(c)
        return i + 1
    if stripped.startswith("==", i) or stripped.startswith("!=", i):
        out.append(stripped[i : i + 2])
        return i + 2
    if stripped.startswith("not in", i) and not (stripped[i + 6 : i + 7].isalnum() or stripped[i + 6 : i + 7] == "_"):
        # The lookahead keeps `not include_web_api` from reading as the
        # operator `not in` plus a truncated identifier.
        out.append("not in")
        return i + 6
    if c in "'\"":
        end = i + 1
        while end < n and stripped[end] != c:
            end += 1
        out.append(stripped[i : end + 1])
        return end + 1
    if c.isalpha() or c == "_":
        end = i
        while end < n and (stripped[end].isalnum() or stripped[end] == "_"):
            end += 1
        out.append(stripped[i:end])
        return end
    raise AssertionError(f"unexpected char {c!r} in when expression {text!r}")


@functools.lru_cache(maxsize=1024)
def _tokenize_when_cached(text: str) -> tuple[str, ...]:
    """Tokenize the Jinja subset used in when expressions, cached."""
    stripped = text.strip().removeprefix("{{").removesuffix("}}")
    out: list[str] = []
    i = 0
    while i < len(stripped):
        i = _scan_token(text, stripped, i, out)
    return tuple(out)


def tokenize_when(text: str) -> list[str]:
    """Tokenize the Jinja subset used in when expressions.

    Strips the surrounding ``{{ }}`` delimiters, then yields identifiers,
    quoted strings, list brackets, ==, !=, in / not in, and parentheses;
    whitespace is skipped.
    """
    return list(_tokenize_when_cached(text))


class _WhenList:
    __slots__ = ("items",)

    def __init__(self, items: list[str]) -> None:
        self.items = items


class _WhenVar:
    """A symbolic str question: an Int over its static choices."""

    __slots__ = ("_z3", "domain", "name")

    def __init__(self, name: str, domain: list[str], z3: ModuleType) -> None:
        self.name = name
        self.domain = domain
        self._z3 = z3

    def eq(self, literal: str) -> object:
        try:
            return self._z3.Int(self.name) == self.domain.index(literal)
        except ValueError:
            return self._z3.BoolVal(False)  # noqa: FBT003  WHYNOT: z3's own API takes a Python bool.


class _WhenZ3Parser:
    """Recursive-descent parser mapping Jinja when-syntax to Z3 formulas."""

    def __init__(
        self,
        expr: str,
        tokens: Sequence[str],
        domains: Mapping[str, list[str]],
        z3: ModuleType,
    ) -> None:
        self.expr = expr
        self.tokens = tokens
        self.domains = domains
        self.z3 = z3
        self.i = 0

    def peek(self) -> str | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def pop(self) -> str:
        tok = self.peek()
        if tok is None:
            raise AssertionError(f"unexpected end of when expression {self.expr!r}")
        self.i += 1
        return tok

    def parse(self) -> object:
        node = self.parse_or()
        if self.i != len(self.tokens):
            raise AssertionError(f"trailing tokens in when expression {self.expr!r}: {self.tokens[self.i :]}")
        return node

    def parse_or(self) -> object:
        node = self.parse_and()
        while self.peek() == "or":
            self.pop()
            node = self.z3.Or(node, self.parse_and())
        return node

    def parse_and(self) -> object:
        node = self.parse_not()
        while self.peek() == "and":
            self.pop()
            node = self.z3.And(node, self.parse_not())
        return node

    def parse_not(self) -> object:
        if self.peek() == "not":
            self.pop()
            return self.z3.Not(self.parse_not())
        return self.parse_cmp()

    def parse_cmp(self) -> object:
        left = self.parse_atom()
        op = self.peek()
        if op in ("==", "!=", "in", "not in"):
            self.pop()
            right = self.parse_atom()
            if op == "==":
                return self._encode_equality(left, right)
            if op == "!=":
                return self.z3.Not(self._encode_equality(left, right))
            if op == "in":
                return self._encode_membership(left, right)
            return self.z3.Not(self._encode_membership(left, right))
        return left

    def parse_atom(self) -> object:
        tok = self.pop()
        if tok == "(":
            node = self.parse_or()
            if self.pop() != ")":
                raise AssertionError(f"unbalanced parens in when expression {self.expr!r}")
            return node
        if tok == "[":
            return self._parse_list_literal()
        if tok in self.domains:
            return _WhenVar(tok, self.domains[tok], self.z3)
        if (tok.startswith("'") and tok.endswith("'")) or (tok.startswith('"') and tok.endswith('"')):
            return tok[1:-1]
        if tok in ("true", "True"):
            return self.z3.BoolVal(True)  # noqa: FBT003  WHYNOT: z3's own API takes a Python bool.
        if tok in ("false", "False"):
            return self.z3.BoolVal(False)  # noqa: FBT003  WHYNOT: z3's own API takes a Python bool.
        return self.z3.Bool(tok)

    def _parse_list_literal(self) -> _WhenList:
        items: list[str] = []
        while self.peek() not in ("]", None):
            if self.peek() == ",":
                self.pop()
                continue
            items.append(self._parse_string_literal(self.pop()))
        self.pop()  # ']'
        return _WhenList(items)

    def _parse_string_literal(self, tok: str) -> str:
        if (tok.startswith("'") and tok.endswith("'")) or (tok.startswith('"') and tok.endswith('"')):
            return tok[1:-1]
        raise AssertionError(f"expected string literal, got {tok!r} in {self.expr!r}")

    def _encode_equality(self, left: object, right: object) -> object:
        lvar = left if isinstance(left, _WhenVar) else None
        rvar = right if isinstance(right, _WhenVar) else None
        llit = left if isinstance(left, str) and not isinstance(left, _WhenVar) else None
        rlit = right if isinstance(right, str) and not isinstance(right, _WhenVar) else None
        if lvar is not None and isinstance(rlit, str):
            return lvar.eq(rlit)
        if rvar is not None and isinstance(llit, str):
            return rvar.eq(llit)
        if lvar is not None and rvar is not None:
            return self._encode_two_var_equality(lvar, rvar)
        return self.z3.Bool(f"eq_{left}_{right}")

    def _encode_two_var_equality(self, lvar: _WhenVar, rvar: _WhenVar) -> object:
        shared = [value for value in lvar.domain if value in rvar.domain]
        if not shared:
            return self.z3.BoolVal(False)  # noqa: FBT003  WHYNOT: z3's own API takes a Python bool.
        return self.z3.Or(
            [
                self.z3.And(
                    self.z3.Int(lvar.name) == lvar.domain.index(value),
                    self.z3.Int(rvar.name) == rvar.domain.index(value),
                )
                for value in shared
            ]
        )

    def _encode_membership(self, elem: object, container: object) -> object:
        if isinstance(elem, _WhenVar) and isinstance(container, _WhenList):
            return self.z3.Or([elem.eq(item) for item in container.items])
        raise AssertionError(f"cannot model membership {elem!r} in {container!r} in {self.expr!r}")


def _build_pinned_domains_and_fixed(
    str_domains: Mapping[str, list[str]],
    pinned: Mapping[str, Any] | None,
    z3: ModuleType,
) -> tuple[dict[str, list[str]], list[object]]:
    """Apply pinned answers to domains (shrinking str domains) and fixed bools."""
    domains = dict(str_domains)
    fixed: list[object] = []
    for name, answer in (pinned or {}).items():
        if name in domains and not isinstance(answer, str):
            raise AssertionError(f"cannot pin str question {name!r} to {answer!r}")
        if isinstance(answer, str):
            domains[name] = [answer]
        elif isinstance(answer, bool):
            fixed.append(z3.Bool(name) == z3.BoolVal(answer))  # noqa: FBT003  WHYNOT: z3's own API.
        else:
            raise AssertionError(f"cannot pin {name!r} to {answer!r}: only str and bool answers are modeled")
    return domains, fixed


def _build_domain_bound_solver(
    domains: Mapping[str, list[str]],
    fixed: Sequence[object],
    cond: object,
    z3: ModuleType,
) -> Any:
    """Build a Z3 Solver bounding each domain to its valid indices and asserting cond."""
    solver = z3.Solver()
    for name, domain in domains.items():
        solver.add(z3.Or([z3.Int(name) == i for i in range(len(domain))]))
    solver.add(*fixed)
    solver.add(cond)
    return solver


def when_expr_satisfiable(
    expr: str,
    str_domains: dict[str, list[str]],
    z3: ModuleType,
    *,
    pinned: Mapping[str, Any] | None = None,
) -> bool:
    """Check a when expression is satisfiable, modeling it in Z3.

    The questionnaire's when grammar is a small Jinja subset: comparisons
    (==, !=, in, not in) over question references and string literals, plus
    and/or/not and parentheses. A str-typed referenced question is modeled
    as an Int over its static choices; a comparison to a literal L maps to
    ``int == domain.index(L)`` (False when L is not a valid choice). Bool
    identifiers are free booleans (each question is checked independently,
    with earlier gates free). Returns True iff some assignment satisfies the
    expression.

    `pinned` asks the same question at a known assignment instead: each
    listed variable is fixed to that answer (a str answer makes the variable
    a one-value domain, so its comparisons are equality against the real
    answer; a bool answer fixes the free boolean) and the result is then
    whether the expression holds *there*. That is what
    tests/test_when_model.py compares against copier's own Jinja evaluation
    of the same expression — including for the str variables whose `choices`
    are templated and which `str_domains` therefore leaves free.
    """
    domains, fixed = _build_pinned_domains_and_fixed(str_domains, pinned, z3)
    tokens = _tokenize_when_cached(expr)
    parser = _WhenZ3Parser(expr, tokens, domains, z3)
    cond = parser.parse()
    solver = _build_domain_bound_solver(domains, fixed, cond, z3)
    return solver.check() == z3.sat
