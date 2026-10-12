"""The declared support contract (`support.yml`): the reader and its doc renderer.

`support.yml` is the human-approved declaration of which witness-leaf
combinations this template keeps working, at which verification tier, and
with what measured evidence (`why`). Two consumers read it, so the reading
and the table rendering live in one place (TODO.md §28.5 R5): the docs
generator (tools/gen_docs.py renders the catalogue's compact summary and the
full `docs/reference/support.md` from it) and the MCP server (the
`template://support` resource). tests/test_support_matrix.py keeps the
declaration honest against the witness ledger.

The full support page also renders the committed update-rehearsal report
(`docs/data/update-rehearsal.json`, written by tools/update_rehearsal.py
--json and committed by .github/workflows/update-rehearsal.yml): the
"Update rehearsal" section at the end of the page is that JSON made
readable, and its reader lives here beside the other doc renderer.

This is a foundations-layer module by the tests/test_tool_layers.py table:
data files in, markdown text out -- no template tree, no subprocess.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

SUPPORT_YML = TOP / "support.yml"
"""The declared support contract (W4 owns the file; no file, no blocks)."""

SUPPORT_DOC = TOP / "docs" / "reference" / "support.md"
"""The generated full-matrix reference page."""

REHEARSAL_JSON = TOP / "docs" / "data" / "update-rehearsal.json"
"""The committed update-rehearsal report the support page renders.

update-rehearsal.yml writes `tools/update_rehearsal.py --json` here after
each scheduled run, alongside the regenerated page, via the auto PR. Absent
(before the first such run) the page renders "no rehearsal recorded yet".
"""

REHEARSAL_KEYS = frozenset({"base", "base_rev", "target", "target_rev", "rehearsed", "skipped", "failures"})
"""The report keys the section renders; the payload's full shape is its own.

(`convergence` and `renders` are per-run detail the tool prints but the
section does not show, so they are not required here.)"""

SECTIONS = ("supported", "best_effort", "tier_policy")
"""The sections a full rendering needs, in page order."""


class SupportLedgerError(Exception):
    """`support.yml` is missing, malformed, or has a hole a renderer needs."""


def load_support(path: Path = SUPPORT_YML) -> dict[str, Any]:
    """Read `support.yml`."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"{path.name} must hold a mapping"
        raise SupportLedgerError(msg)
    return data


def support_section(support: dict[str, Any], key: str) -> list[Any]:
    """One `support.yml` section, validated as a non-empty list of mappings."""
    rows = support.get(key)
    if not isinstance(rows, list) or not rows:
        msg = f"support.yml has no non-empty `{key}:` list"
        raise SupportLedgerError(msg)
    return rows


TIERED_SECTIONS = ("supported", "best_effort")
"""The sections that promise a tier: a row names a combination, textually.

Substring checks, because support.yml writes its combinations as prose
(`project_type=cli/gate=off:use_recommended_agent`,
`task_runner = make | poe | invoke | duty`): an answer matches a row when
its name and value spellings both appear in the combination text. The
renderers (tools/gen_docs.py) already read them the same way.
"""


def rows_naming(question: str, value: str | None = None) -> list[str]:
    """The tiered rows naming `question` (and `value`), as human lines.

    `value=None` matches rows naming the question at all (the "which
    combinations involve this question" reading). Each line carries the
    section, the tier and the measured `why`. An unreadable support.yml
    reads as no rows -- the callers' verdicts stay advisory, never loud.
    """
    try:
        support = load_support()
    except (OSError, SupportLedgerError):
        return []
    notes: list[str] = []
    for section in TIERED_SECTIONS:
        try:
            rows = support_section(support, section)
        except SupportLedgerError:
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            combination = str(row.get("combination", ""))
            if question not in combination:
                continue
            if value is not None and str(value) not in combination:
                continue
            why = str(row.get("why", "")).strip()
            tier = str(row.get("tier", "")).strip()
            line = f"Support ({section}, tier {tier}): `{combination}`"
            if why:
                line += f" -- {why}"
            notes.append(line)
    return notes


def base_is_promised(support: dict[str, Any], project_type: str) -> bool:
    """Whether any tiered row carries the `project_type` base to a tier."""
    for section in TIERED_SECTIONS:
        try:
            rows = support_section(support, section)
        except SupportLedgerError:
            continue
        for row in rows:
            if isinstance(row, dict) and project_type in str(row.get("combination", "")):
                return True
    return False


def cell(text: str) -> str:
    """A markdown table cell: one line, no unescaped pipes."""
    return " ".join(text.split()).replace("|", "\\|")


def _support_cell(value: Any) -> str:
    """One support-matrix cell."""
    if isinstance(value, list):
        return ", ".join(f"`{item}`" for item in value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return "—"
    return f"`{value}`"


def matrix_rows(rows: list[Any], *, drop: tuple[str, ...] = (), plain: tuple[str, ...] = ()) -> str:
    """One markdown table over `rows`, deriving its columns from their keys.

    `drop` removes keys that belong in the full reference but not in a
    summary: the catalogue keeps one row per combination, while the `why`
    column (the measured evidence) lives in `docs/reference/support.md`.

    `plain` columns are prose cells, rendered without the code-span wrapping
    `_support_cell` gives identifiers (`why` quotes commands and paths). The
    questionnaire tables (tools/gen_docs.py) reuse this renderer so the whole
    docs surface has one table vocabulary.
    """
    columns: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            msg = "every support entry must be a mapping"
            raise SupportLedgerError(msg)
        columns += [str(key) for key in row if str(key) not in columns and str(key) not in drop]
    if not columns:
        msg = "a support section has no columns to render"
        raise SupportLedgerError(msg)
    lines = [f"| {' | '.join(columns)} |", f"|{'---|' * len(columns)}"]
    for row in rows:
        cells = [
            cell(str(row.get(column))) if column in plain else cell(_support_cell(row.get(column)))
            for column in columns
        ]
        lines.append(f"| {' | '.join(cells)} |")
    return "\n".join(lines)


def render_support_table(support: dict[str, Any], *, full_link: str) -> str:
    """The catalogue's compact support summary, from `support.yml`.

    One row per combination and no `why` column: the full matrix and its
    evidence live in `docs/reference/support.md`, which the summary links to
    (`full_link`, already relative to the page the summary is generated into).
    The columns are the entry keys, in the order the file writes them, so the
    table follows whatever shape W4 settles on instead of pinning one here.
    """
    blocks = [
        "**Supported** — executed end to end by CI:",
        "",
        matrix_rows(support_section(support, "supported"), drop=("why",)),
    ]
    best_effort = support.get("best_effort")
    if best_effort is not None:
        blocks += [
            "",
            "**Best effort** — rendered by CI, but never executed:",
            "",
            matrix_rows(support_section(support, "best_effort"), drop=("why",)),
        ]
    blocks += ["", f"Full matrix and the evidence behind each tier: [{full_link}]({full_link})."]
    return "\n".join(blocks)


def _load_rehearsal_payload(report: Path) -> dict[str, Any] | None:
    """Load and validate the JSON rehearsal report; returns None when absent."""
    if not report.is_file():
        return None
    try:
        payload = json.loads(report.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"{report}: not a JSON rehearsal report: {exc}"
        raise SupportLedgerError(msg) from exc
    if not isinstance(payload, dict):
        msg = f"{report}: the rehearsal report must be a JSON object"
        raise SupportLedgerError(msg)
    missing = sorted(REHEARSAL_KEYS - payload.keys())
    if missing:
        msg = f"{report}: rehearsal report lacks {', '.join(missing)}"
        raise SupportLedgerError(msg)
    return payload


def _format_rehearsal_table(payload: dict[str, Any]) -> list[str]:
    """Format the markdown table displaying the rehearsal verdict."""
    failures = len(payload["failures"])
    skipped = len(payload["skipped"])
    base = cell(f"`{payload['base']}` ({str(payload['base_rev'])[:10]})")
    target = cell(f"`{payload['target']}` ({str(payload['target_rev'])[:10]})")
    failed = cell(str(failures)) if failures else "0 — every leaf updated cleanly"
    row = f"| {base} | {target} | {cell(str(payload['rehearsed']))} | {failed} | {cell(str(skipped))} |"
    return [
        "| Base | Target | Rehearsed | Failures | Skipped |",
        "|---|---|---|---|---|",
        row,
        "",
        "weekly via update-rehearsal.yml; latest committed run",
    ]


def render_update_rehearsal(report: Path = REHEARSAL_JSON) -> str:
    """The `## Update rehearsal` section at the end of `docs/reference/support.md`."""
    head = ["## Update rehearsal", ""]
    payload = _load_rehearsal_payload(report)
    if payload is None:
        return "\n".join([*head, "No rehearsal has been recorded yet."])
    return "\n".join([*head, *_format_rehearsal_table(payload)])


def render_support_doc(support: dict[str, Any], *, rehearsal: Path = REHEARSAL_JSON) -> str:
    """`docs/reference/support.md`: the full support matrix, prose included.

    `rehearsal` is the report the trailing "Update rehearsal" section reads
    (the committed one by default; a fixture path in tests).
    """
    sections = {key: support_section(support, key) for key in SECTIONS}
    lines = [
        "Every combination this template keeps working, the tier that guarantees",
        "it, and the measured evidence behind that tier.",
        "",
        "## Supported",
        "",
        "Executed end to end in CI by the witness full tier: `uv sync`, the",
        "generated project's own pytest, basedpyright and its docs build.",
        f"Measured at ~3 minutes per leaf, so only these {len(sections['supported'])} run it.",
        "",
        matrix_rows(sections["supported"], plain=("why",)),
        "",
        "## Best effort",
        "",
        "Declared so the questionnaire's existing answers keep rendering, but",
        "never executed by CI. The witness fast tier renders and ruff-checks",
        "these leaves (272 renders at ~1.3 s each, 10-20 s in parallel); a",
        "regression that only breaks install or run is not caught there.",
        "",
        matrix_rows(sections["best_effort"], plain=("why",)),
        "",
        "## Tier policy",
        "",
        "Which tier each class of witness leaf is declared for. `none` is",
        "reserved for a future W4 exclusion: it is declared as `tier: none`",
        "plus a `reason` in `tests/matrix/witnesses.json`, and no leaf uses it",
        "today because every declared leaf has a recorded fast-tier run.",
        "",
        matrix_rows(sections["tier_policy"], plain=("why",)),
        "",
        # The update rehearsal closes the page: the tiers above promise the
        # update path keeps working, and this section is the run that proves
        # it for the configuration set those tiers cover.
        render_update_rehearsal(rehearsal),
    ]
    return "\n".join(lines)
