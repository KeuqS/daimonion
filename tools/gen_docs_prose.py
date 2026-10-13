"""The questionnaire's help text and `when` conditions, as docs prose.

`tools/gen_docs.py` renders the questionnaire-derived documentation; this
module is the prose half of the reading: the first-sentence / prompt /
recommendation lifts out of each question's help string, the `when`
expression rendered as prose (parsed from when_model's token stream, so the
match is by meaning, not spelling), and the small text helpers (`_wrap`,
`_es`, `_br`, `_clip`) the markdown and mermaid renderers share.

This is a machinery-layer module by the tests/test_tool_layers.py table:
questionnaire data in, markdown/mermaid text out -- no template tree, no
subprocess.
"""

# WHYNOT: leaf sibling of the gen_docs split; `_wrap`/`_es`/`_br`/`_clip`
# and the prose helpers are shared with the markdown and mermaid
# siblings, so imported private names read as unused locally.
# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

import re
import sys
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import when_model  # noqa: E402
from tools.gen_docs_model import ALL_TYPES  # noqa: E402
from tools.gen_docs_model import BOOL_PROSE  # noqa: E402
from tools.gen_docs_model import PROMPT_STOPS  # noqa: E402
from tools.gen_docs_model import GenDocsError  # noqa: E402
from tools.gen_docs_model import Model  # noqa: E402
from tools.questionnaire import Question  # noqa: E402

_HELP_BULLET = re.compile(r"^- ([A-Za-z0-9_.\-]+): (.*)$")


def first_sentence(text: str) -> str:
    """A paragraph's first sentence.

    Only a `.`/`!`/`?` followed by a whitespace and a capital, digit, backtick
    or bracket ends a sentence, so abbreviations like `e.g. 0000-0002-...`
    and version numbers like `SQLAlchemy 2.0 + ...` stay intact.
    """
    end = re.search(r"[.!?]\s(?=[A-Z0-9`(])", text)
    return text[: end.start() + 1].strip() if end else text.strip()


def help_paragraph(question: Question, marker: str) -> str:
    """The first sentence after `marker` in a question's help text.

    The questionnaire's help strings have a fixed shape (`Recommended: ...`,
    `Answer No to ...`), which is why the recommendation and the opt-out
    behaviour can be lifted out of them instead of being restated here.
    """
    joined = " ".join(question.help.split())
    index = joined.find(marker)
    if index < 0:
        msg = f"question {question.name!r} has no {marker.strip()!r} line in its help"
        raise GenDocsError(msg)
    return first_sentence(joined[index + len(marker) :])


def recommended(gate: Question) -> str:
    """What a gate's recommended answer configures."""
    return help_paragraph(gate, "Recommended: ")


def declined(gate: Question) -> str:
    """What answering No to a gate does."""
    return help_paragraph(gate, "Answer No to ")


def prompt_line(question: Question) -> str:
    """The question's prompt: its help's first paragraph, before the markers."""
    lines: list[str] = []
    for line in question.help.splitlines():
        if not line.strip() or line.startswith(("- ", "  ")):
            break
        lines.append(line.strip())
    text = " ".join(lines)
    for stop in PROMPT_STOPS:
        index = text.find(stop)
        if index >= 0:
            text = text[:index]
    return _clip(text.strip(), 150) if text.strip() else question.name


def choice_help(question: Question) -> dict[str, str]:
    """`- value: description` bullets in a question's help, keyed by value.

    Continuation lines (indented past the bullet) are joined into the value's
    description, so a wrapped help string reads as one sentence here.
    """
    found: dict[str, str] = {}
    current = ""
    for line in question.help.splitlines():
        match = _HELP_BULLET.match(line)
        if match:
            value, description = match.groups()
            found[str(value)] = str(description).strip()
            current = str(value)
        elif current and line.startswith("  ") and line.strip():
            found[current] = f"{found[current]} {line.strip()}"
        else:
            current = ""
    return found


def condition(question: Question) -> str:
    """The `when` condition in prose, or `all` when the question always runs.

    Rendered from the parsed expression -- when_model owns the tokenizer -- so
    the match is by meaning, not spelling: a semantically identical rewrite of
    a condition renders the same sentence, and a shape no rule below covers is
    a loud generator failure instead of a stale sentence in the docs.
    """
    if question.when is None:
        return ALL_TYPES
    return _condition_prose(str(question.when))


def _condition_prose(raw: str) -> str:
    """One `when` expression as prose, parsed from when_model's token stream.

    The grammar is the questionnaire's own Jinja subset; the prose rules: a
    `project_type` comparison renders as its choices (`library / cli`), any
    other comparison as `` `var` = value ``, a boolean identifier as its
    BOOL_PROSE explanation (or the `has_*` layer sentence), `or` joins with
    ` / ` and `and` with ` + `. A negative and-chain reads `not a + b`.
    """
    prose, rest = _or_prose(when_model.tokenize_when(raw))
    if rest:
        msg = f"unparsed trailing tokens in when condition {raw!r}: {rest}"
        raise GenDocsError(msg)
    return prose


def _or_prose(tokens: list[str]) -> tuple[str, list[str]]:
    """`a or b` renders as `a / b` (the choices a condition admits)."""
    prose, rest = _and_prose(tokens)
    while rest and rest[0] == "or":
        rhs, rest = _and_prose(rest[1:])
        prose = f"{prose} / {rhs}"
    return prose, rest


def _and_prose(tokens: list[str]) -> tuple[str, list[str]]:
    """`a and b` renders as `a + b` (requirements stacked in one condition)."""
    prose, rest = _atom_prose(tokens)
    while rest and rest[0] == "and":
        rhs, rest = _atom_prose(rest[1:])
        prose = f"{prose} + {rhs}"
    return prose, rest


def _atom_prose(tokens: list[str]) -> tuple[str, list[str]]:
    """One atom: a negation, a parenthesized group, or a comparison/name."""
    if not tokens:
        msg = "a when condition ends where an operand was expected"
        raise GenDocsError(msg)
    if tokens[0] == "not":
        inner, rest = _atom_prose(tokens[1:])
        return f"not {inner}", rest
    if tokens[0] == "(":
        inner, rest = _or_prose(tokens[1:])
        if not rest or rest[0] != ")":
            msg = "a when condition has an unbalanced parenthesis"
            raise GenDocsError(msg)
        return inner, rest[1:]
    return _comparison_prose(tokens)


def _comparison_prose(tokens: list[str]) -> tuple[str, list[str]]:
    """One comparison or bare name, as prose.

    A `project_type` comparison renders as its choices (`library / cli`), any
    other comparison as `` `var` = value `` or `` `var` in [a, b] ``, and a
    bare boolean identifier as its `_bool_prose` explanation.
    """
    name = tokens[0]
    if len(tokens) > 2 and tokens[1] in ("==", "!="):
        literal = _literal(tokens[2])
        if name == "project_type":
            if tokens[1] != "==":
                msg = f"project_type != is not a shape the prose covers: {' '.join(tokens[:3])!r}"
                raise GenDocsError(msg)
            return literal, tokens[3:]
        # Prose says `=` whatever the operator's arity: the sentence names the
        # value, it does not re-spell Jinja.
        return f"`{name}` = {literal}" if tokens[1] == "==" else f"`{name}` != {literal}", tokens[3:]
    if len(tokens) > 2 and tokens[1] == "in":
        values, rest = _literal_list(tokens[2:])
        if name == "project_type":
            return " / ".join(values), rest
        return f"`{name}` in [{', '.join(values)}]", rest
    if len(tokens) > 3 and tokens[1:3] == ["not", "in"]:
        values, rest = _literal_list(tokens[3:])
        return f"`{name}` not in [{', '.join(values)}]", rest
    return _bool_prose(name), tokens[1:]


def _literal(token: str) -> str:
    """A quoted string token, unquoted."""
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
        return token[1:-1]
    msg = f"expected a quoted literal, got {token!r}"
    raise GenDocsError(msg)


def _literal_list(tokens: list[str]) -> tuple[list[str], list[str]]:
    """`['a', 'b', ...]` as unquoted values; returns the values and the rest."""
    if not tokens or tokens[0] != "[":
        msg = f"expected a literal list, got {' '.join(tokens[:3])!r}"
        raise GenDocsError(msg)
    values: list[str] = []
    rest = tokens[1:]
    while rest and rest[0] != "]":
        if rest[0] == ",":
            rest = rest[1:]
            continue
        values.append(_literal(rest[0]))
        rest = rest[1:]
    if not rest:
        msg = "a when condition's literal list is never closed"
        raise GenDocsError(msg)
    return values, rest[1:]


def _bool_prose(name: str) -> str:
    """A bare boolean identifier as prose: the curated explanation or the layer sentence."""
    if name in BOOL_PROSE:
        return BOOL_PROSE[name]
    if name.startswith("has_"):
        return f"the {name.removeprefix('has_')} layer is present"
    msg = f"no prose rule for the bare condition name {name!r} (add it to BOOL_PROSE)"
    raise GenDocsError(msg)


def default_prose(question: Question) -> str:
    """A question's default, readable in a table cell."""
    value = question.default
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        if "{{" in value:
            return f"`{' '.join(value.strip('{} ').split())}`"
        return f"`{value}`" if value else "(empty)"
    if isinstance(value, list):
        return ", ".join(f"`{item}`" for item in value)
    return f"`{value}`"


def asked_for_values(question: Question) -> list[str]:
    """The literals a `when` compares a non-project_type variable to."""
    raw = str(question.when)
    if "project_type" in raw:
        return []
    return re.findall(r"== '([A-Za-z0-9_.\-]+)'", raw)


def _wrap(text: str, prefix: str = "", continuation: str = "  ", width: int = 100) -> list[str]:
    """Greedy-wrap `text`, prefixing the first line and each continuation line."""
    lines: list[str] = []
    current = prefix
    for word in text.split():
        separator = "" if not current or current.endswith(" ") else " "
        if current.strip() and len(current) + len(separator) + len(word) > width:
            lines.append(current)
            current = f"{continuation}{word}"
        else:
            current = f"{current}{separator}{word}"
    if current:
        lines.append(current)
    return lines


def _es(text: str) -> str:
    """Escape text for a quoted mermaid node label.

    Mermaid labels are plain text, not markdown, so code backticks are
    dropped rather than rendered literally.
    """
    text = text.replace("`", "")
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _br(parts: list[str], width: int = 64) -> str:
    """Join `parts` with `, ` and wrap into mermaid `<br/>`-separated lines."""
    return "<br/>".join(_es(line) for line in _wrap(", ".join(parts), width=width, continuation=""))


def _clip(text: str, limit: int = 96, *, prefer_paren: bool = False) -> str:
    """Shorten `text` to at most `limit` characters.

    The cut prefers a sentence end, then (for mermaid labels) the opening
    parenthesis of a trailing explanation, then a word boundary.
    """
    if len(text) <= limit:
        return text
    head = text[:limit]
    sentences = [match.end() for match in re.finditer(r"[.!?](?=\s+[A-Z0-9`(])", head)]
    if sentences and sentences[-1] >= limit // 2:
        return head[: sentences[-1]].strip()
    paren = head.rfind(" (")
    if prefer_paren and paren >= limit // 3:
        return head[:paren].strip()
    return f"{head.rsplit(' ', 1)[0]}…"


def _short_gate_label(model: Model, gate: Question, *, yes: bool) -> str:
    """A gate's Yes (recommended) or No (declined) branch label."""
    if yes:
        text = recommended(gate).removeprefix("yes — ").removeprefix("yes - ")
        return _es(_clip(text, 84, prefer_paren=True))
    details = model.details(gate)
    if details:
        return _br([f"ask: {', '.join(q.name for q in details)}"], 76)
    return _es(_clip(declined(gate), 84))
