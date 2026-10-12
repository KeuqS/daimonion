"""The constrained configuration assistant (TODO §42-B1): propose presets, validate answers.

`tools/suggest.py` never invents answers: `questionnaire_schema` publishes
the questions a proposal may answer, `validate_answers` runs a proposal
through copier's own questionnaire pass, and `suggest_presets` ranks the
preset files by requirement keywords with no model. These tests pin the
three halves against the live questionnaire -- not a copy of it -- so a
renamed question or a new preset moves the expectations, not the wording.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))
from tools import cli  # noqa: E402
from tools import questionnaire  # noqa: E402
from tools import suggest  # noqa: E402


def _refused(answers: dict[str, Any]) -> list[dict[str, str]]:
    """The rejection reasons for an answer set that must not validate."""
    result = suggest.validate_answers(answers)
    assert not result.ok, f"{answers} was accepted"
    return result.errors


def test_schema_lists_every_question_in_ask_order():
    """The schema is the questionnaire: same names, same order, same count."""
    live = [question.name for question in questionnaire.load_questions()[0]]
    schema = suggest.questionnaire_schema()
    assert [entry["name"] for entry in schema["questions"]] == live
    assert schema["count"] == len(live)


def test_schema_entry_carries_the_contract_fields():
    """Each entry names what a proposal may set and when it is asked."""
    entries = {entry["name"]: entry for entry in suggest.questionnaire_schema()["questions"]}
    project_type = entries["project_type"]
    assert {"name", "type", "choices", "help", "when", "default"} <= set(project_type)
    assert "library" in project_type["choices"] and "web_api" in project_type["choices"]
    assert entries["combinable"]["internal"] is True
    assert entries["project_type"]["internal"] is False


def test_schema_asked_only_drops_the_derived_variables():
    """The MCP working set excludes what an answer set must never name."""
    everything = suggest.questionnaire_schema()["questions"]
    asked = suggest.questionnaire_schema(asked_only=True)["questions"]
    assert len(asked) < len(everything)
    assert all(entry["internal"] is False for entry in asked)
    assert "combinable" not in {entry["name"] for entry in asked}


def test_validate_accepts_a_preset_family():
    """A preset's own answers are valid -- the gate trusts what it recommends."""
    for name in ("web-api", "bot", "library", "mcp-server"):
        result = suggest.validate_answers(dict(cli.preset_answers(name)))
        assert result.ok, f"preset {name} rejected: {result.errors}"
        assert result.errors == []


def test_validate_rejects_an_unknown_question():
    """Unknown keys are refused: copier would silently render the default."""
    errors = _refused({"project_type": "web_api", "unknown_q": 1})
    by_question = {error["question"]: error["reason"] for error in errors}
    assert "unknown_q" in by_question and "unknown question" in by_question["unknown_q"]


def test_validate_rejects_a_value_outside_the_choices():
    """Copier's own choice verdict: a non-choice never reaches a render."""
    errors = _refused({"project_type": "not_a_type"})
    assert any(error["question"] == "project_type" and "not_a_type" in error["reason"] for error in errors)


def test_validate_rejects_an_answer_to_a_question_that_is_never_asked():
    """A forced answer copier keeps but the render discards is refused."""
    errors = _refused({"project_type": "web_api", "include_scraping": True})
    assert any(error["question"] == "include_scraping" and "not asked" in error["reason"] for error in errors)


def test_validate_rejects_a_layer_on_a_non_combinable_base():
    """The `combinable` half of the trio: include_web_api cannot ride ros2."""
    errors = _refused({"project_type": "ros2", "include_web_api": True})
    assert any("non-combinable" in error["reason"] for error in errors)


def test_validate_rejects_an_answer_to_a_derived_internal():
    """Derived variables are computed, never proposed."""
    errors = _refused({"project_type": "library", "combinable": True})
    assert any(error["question"] == "combinable" and "derived internal" in error["reason"] for error in errors)


def test_validate_rejects_a_validator_failure():
    """Copier's own `validator:` verdict, surfaced as a rejection reason."""
    errors = _refused(
        {"project_type": "library", "use_recommended_license": False, "fair": True, "author_orcid": "bogus"}
    )
    assert any(error["question"] == "author_orcid" for error in errors)


def test_suggest_ranks_web_api_first_for_api():
    """The acceptance probe: 'api' recommends the web-api family on top."""
    matches = suggest.suggest_presets(["api"])
    assert matches, "no preset matched 'api'"
    assert matches[0].preset == "web-api"
    assert matches[0].answers.get("project_type") == "web_api"


def test_suggest_matches_the_acceptance_requirements():
    """'internal API, postgres, github actions' proposes the web-api preset with a reason."""
    matches = suggest.suggest_presets(["internal API, postgres, github actions"])
    assert matches and matches[0].preset == "web-api"
    assert any("ostgres" in reason for reason in matches[0].reasons)


def test_suggest_routes_other_families():
    """Each family is reachable: bot, data-science, micropython, the AtCoder judge."""
    assert suggest.suggest_presets(["discord bot"])[0].preset == "bot"
    assert suggest.suggest_presets(["data analysis notebooks"])[0].preset == "data-science"
    assert suggest.suggest_presets(["firmware esp32"])[0].preset == "micropython"
    assert suggest.suggest_presets(["competitive programming atcoder"])[0].preset == "online-judge-atcoder"


def test_suggest_is_deterministic_and_empty_without_signal():
    """Same words, same ranking; filler or unknown words match nothing."""
    first = [(match.preset, match.score) for match in suggest.suggest_presets(["api", "postgres"])]
    second = [(match.preset, match.score) for match in suggest.suggest_presets(["postgres", "api"])]
    assert first == second
    assert suggest.suggest_presets([]) == []
    assert suggest.suggest_presets(["the and our project please"]) == []
    assert suggest.suggest_presets(["quantum toaster"]) == []


def test_suggest_main_suggests_and_validates(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """The `daimonion suggest` entry point: prose by default, exit 2 on rejection."""
    assert suggest.main(["api"]) == 0
    assert "web-api" in capsys.readouterr().out
    answers = tmp_path / "answers.yml"
    answers.write_text("project_type: web_api\nunknown_q: 1\n", encoding="utf-8")
    assert suggest.main(["--validate", str(answers)]) == 2
    assert "unknown_q" in capsys.readouterr().out
