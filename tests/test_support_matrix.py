"""W4: the declared support matrix, its witness evidence, and its docs.

`support.yml` is the human-approved declaration; `tests/matrix/witnesses.json`
is what the witness tiers actually ran. These tests keep the two honest:
every `supported` combination must be a leaf the full tier executed and
passed, `docs/reference/support.md` must be exactly what `tools/gen_docs.py`
renders from `support.yml` (the same `--check` gate CI runs), and the
`tier: none` exclusion hook must never be used without a reason.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import gen_docs  # noqa: E402
from tools import support_ledger  # noqa: E402

LEDGER = TOP / "tests" / "matrix" / "witnesses.json"
SECTIONS = ("supported", "best_effort", "tier_policy")


def ledger() -> dict[str, dict[str, Any]]:
    """The committed witness ledger, keyed by leaf id."""
    payload: dict[str, Any] = json.loads(LEDGER.read_text(encoding="utf-8"))
    return {str(entry["id"]): entry for entry in payload["leaves"]}


def support() -> dict[str, Any]:
    """The committed declaration, as tools/support_ledger.py reads it."""
    return support_ledger.load_support(support_ledger.SUPPORT_YML)


def test_supported_combinations_are_exactly_the_full_tier_sample():
    """Every leaf the full tier runs is declared supported, and nothing else.

    The declaration and the executed sample drift apart silently otherwise:
    a new full-tier leaf would run unannounced, and a declared `supported`
    combination nobody runs would be a promise CI does not keep.
    """
    declared = {str(row["combination"]) for row in support()["supported"]}
    executed = {leaf_id for leaf_id, entry in ledger().items() if entry["tier"] == "full"}
    assert declared == executed


def test_supported_combinations_have_a_recorded_full_tier_pass():
    """A supported combination is one the ledger records as a full-tier pass."""
    entries = ledger()
    problems: list[str] = []
    for row in support()["supported"]:
        leaf_id = str(row["combination"])
        entry = entries.get(leaf_id)
        if entry is None:
            problems.append(f"{leaf_id}: not in {LEDGER.name}")
        elif (entry["tier"], entry["result"], entry.get("source")) != ("full", "pass", "full"):
            problems.append(f"{leaf_id}: {entry['tier']}/{entry['result']}/{entry.get('source')}")
    assert problems == []


def test_every_support_entry_has_a_why():
    """Each declared entry carries the measured evidence for its tier."""
    missing = [
        f"{section}[{index}]"
        for section in SECTIONS
        for index, row in enumerate(support().get(section, []))
        if not (isinstance(row.get("why"), str) and row["why"].strip())
    ]
    assert missing == []


def test_support_doc_is_exactly_the_generator_output():
    """`docs/reference/support.md` is the generated file, prose included."""
    assert support_ledger.SUPPORT_DOC.read_text(encoding="utf-8") == gen_docs.support_doc_text()
    target = next(block for block in gen_docs.generated_blocks() if block.path == support_ledger.SUPPORT_DOC)
    assert gen_docs.check(gen_docs.Model.load(), [target]) == []


def rehearsal_report(tmp_path: Path, *, failures: dict[str, list[str]] | None = None) -> Path:
    """A fixture report in `tools/update_rehearsal.py --json`'s payload shape."""
    report = tmp_path / "update-rehearsal.json"
    payload = {
        "base": "6.0.0",
        "base_rev": "0123456789abcdef0123456789abcdef01234567",
        "target": "HEAD",
        "target_rev": "abcdefabcdefabcdefabcdefabcdefabcdefabcd",
        "rehearsed": 278,
        "skipped": {
            "library/oj/other": "choice 'other' postdates 6.0.0",
            "cli/scraping": "choice 'scraping' postdates 6.0.0",
        },
        "failures": failures or {},
        "convergence": {},
        "renders": {"cached": 10, "fresh": 5, "reused": 15},
    }
    report.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    return report


def test_support_doc_rehearsal_section_renders_the_committed_report(tmp_path: Path):
    """The page's trailing section is the committed JSON, made readable."""
    report = rehearsal_report(tmp_path)
    section = support_ledger.render_update_rehearsal(report)
    assert section.startswith("## Update rehearsal")
    assert "| `6.0.0` (0123456789) | `HEAD` (abcdefabcd) | 278 | 0 — every leaf updated cleanly | 2 |" in section
    assert "weekly via update-rehearsal.yml; latest committed run" in section
    # The section closes the page the generator writes, not a side panel.
    assert support_ledger.render_support_doc(support(), rehearsal=report).endswith(section)

    # A red run reports its failures as a count, not the clean-run phrase.
    red = rehearsal_report(tmp_path, failures={"library/gate=recommended": ["conflict residue: ['x']"]})
    assert "| `6.0.0` (0123456789) | `HEAD` (abcdefabcd) | 278 | 1 | 2 |" in support_ledger.render_update_rehearsal(red)


def test_support_doc_rehearsal_section_without_a_report(tmp_path: Path):
    """Before the first scheduled run commits a report, the page says so."""
    absent = tmp_path / "update-rehearsal.json"
    section = support_ledger.render_update_rehearsal(absent)
    assert section == "## Update rehearsal\n\nNo rehearsal has been recorded yet."
    assert support_ledger.render_support_doc(support(), rehearsal=absent).endswith(section)


def test_ledger_none_entries_carry_a_reason():
    """The `tier: none` hook cannot exclude a leaf without naming why."""
    unreasoned = [
        leaf_id
        for leaf_id, entry in ledger().items()
        if entry.get("tier") == "none" and not (isinstance(entry.get("reason"), str) and entry["reason"].strip())
    ]
    assert unreasoned == []
