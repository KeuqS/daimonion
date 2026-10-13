"""The generated-size ledger: row keys and the docs table that renders them.

The size block (`generated-size` in docs/reference/dependencies.md) is
measured, not derived: the numbers live in tests/matrix/sizes.json and
tools/gen_docs.py --check fails when the docs table differs. These tests
pin the two halves that --check cannot see on its own: the ledger covers
exactly the questionnaire's project_type choices x the preset set (plus the
non-preset rows the table shows), and every committed number is a sane
positive int.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import gen_docs  # noqa: E402
from tools.answers import preset_names  # noqa: E402

EXPECTED_NON_PRESET_ROWS = {"project_type=script", "row:oj_kaggle", "row:oj_ctf"}


def _ledger() -> dict:
    return json.loads((TOP / "tests" / "matrix" / "sizes.json").read_text(encoding="utf-8"))


def test_size_ledger_covers_every_preset_and_base_type():
    """Ledger rows are exactly presets + script + the oj extra rows."""
    ledger = _ledger()
    expected = {f"preset:{name}" for name in preset_names()} | EXPECTED_NON_PRESET_ROWS
    assert set(ledger["rows"]) == expected, (
        "sizes.json rows drifted from the preset set: "
        f"missing={sorted(expected - set(ledger['rows']))} extra={sorted(set(ledger['rows']) - expected)}"
    )


def test_size_ledger_bases_match_the_questionnaire():
    """Every ledger row's base is a project_type the questionnaire offers."""
    model = gen_docs.Model.load()
    choices = {str(choice) for choice in model.question("project_type").choices}
    ledger = _ledger()
    for name, row in ledger["rows"].items():
        assert row["base"] in choices, f"{name}: base {row['base']!r} is not a project_type choice"
        for key in ("files", "lines", "deps"):
            assert isinstance(row[key], int) and row[key] >= 0, f"{name}: {key}={row[key]!r} is not a sane count"


def test_size_table_renders_the_ledger():
    """The renderer emits one well-formed table row per ledger row."""
    ledger = _ledger()
    text = gen_docs.render_size_ledger(gen_docs.Model.load())
    lines = text.splitlines()
    assert lines[0] == "| Row | Files | Lines | Runtime deps |"
    assert len(lines) == len(ledger["rows"]) + 2
    for name, row in ledger["rows"].items():
        assert f"| `{name}` | {row['files']} | {row['lines']} | {row['deps']} |" in text
