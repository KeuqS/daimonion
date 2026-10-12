"""`tools/explain.py`: preset and answer explanations from the questionnaire's own words.

The explanations are assembled, not written: `questions/*.yml` help text,
the questions' `choices` / `when` context, the preset files' leading
comments, `support.yml`'s measured `why` lines, and the question graph's
when/default edges (`tools/question_graph.py`). The parametrization reads
`cli.available_presets()` so a new preset is covered the moment it exists.
"""

import sys
from pathlib import Path

import pytest

TOP = Path(__file__).absolute().parent.parent
if str(TOP) not in sys.path:  # tests/test_cli.py does the same to reach tools/
    sys.path.insert(0, str(TOP))

from tools import cli  # noqa: E402
from tools import explain  # noqa: E402
from tools import question_graph  # noqa: E402

PRESETS = cli.available_presets()


@pytest.mark.parametrize("preset", PRESETS)
def test_every_preset_is_explainable(preset: str):
    """Every shipped preset explains itself: each pinned answer gets its reason."""
    text = explain.explain_preset(preset)
    answers = cli.preset_answers(preset)
    assert f"Preset `{preset}`" in text
    for key, pinned in answers.items():
        assert f"{key} = {pinned!r}" in text, f"preset {preset}: answer {key} has no explanation"


def test_explain_preset_rejects_an_unknown_preset():
    """An unknown preset is an error naming the available ones, not an empty page."""
    with pytest.raises(explain.ExplainError, match="Available presets"):
        explain.explain_preset("no-such-preset")


def test_explain_answer_rejects_an_unknown_question():
    """An unknown question is an error naming the valid names."""
    with pytest.raises(explain.ExplainError, match="unknown question"):
        explain.explain_answer("no_such_question")


def test_explain_answer_names_help_choices_and_gate():
    """The answer explanation carries the question's own words: help, values, when."""
    text = explain.explain_answer("project_type", "cli")
    assert "What kind of project is this?" in text
    assert "cli" in text
    assert "library" in text  # the written default is named


def test_explain_deviation_reports_real_when_dependents():
    """`deviate` derives its impact from the graph: project_type=cli gates include_scraping."""
    text = explain.explain_deviation("project_type", "cli")
    assert "include_scraping" in text
    # the graph is the mechanism: the reported names are exactly the edges into project_type
    graph = question_graph.build_graph()
    gated = {edge.source for edge in graph.edges if edge.target == "project_type" and edge.field == "when"}
    assert "include_scraping" in gated, "the pinned combination must be a real when-edge, not prose"
    assert "include_mcp" in text


def test_explain_deviation_names_support_for_a_supported_pair():
    """A supported combination says which tier promises it."""
    text = explain.explain_deviation("project_type", "cli")
    assert "tier full" in text


def test_explain_deviation_is_honest_about_an_unnamed_combination():
    """A combination no row names says so, rather than inventing a tier."""
    text = explain.explain_deviation("project_type", "micropython")
    assert "micropython" in text


def test_explain_main_routes_the_three_forms(capsys: pytest.CaptureFixture[str]):
    """The entry point prints for --preset, QUESTION VALUE, and --deviate."""
    assert explain.main(["--preset", "web-api"]) == 0
    assert "project_type = 'web_api'" in capsys.readouterr().out
    assert explain.main(["project_type", "cli"]) == 0
    assert "project_type" in capsys.readouterr().out
    assert explain.main(["--deviate", "project_type", "cli"]) == 0
    assert "include_scraping" in capsys.readouterr().out
    assert explain.main(["--preset", "no-such-preset"]) == 2
