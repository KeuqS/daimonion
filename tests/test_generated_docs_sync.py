"""Guards that the generated docs are the questionnaire's, not a stale copy.

`tools/gen_docs.py --check` is the gate: it renders every generated block from
the questionnaire model (`tools/questionnaire.py`, i.e. `copier.yml` plus
`questions/*.yml`) and compares it with the committed text. These tests run
that gate, and pin the three properties it depends on:

- a changed questionnaire changes the rendered docs (the blocks are derived,
  not hard-coded);
- the feature catalogue's graph covers the option set that drifted before
  (CTF, scraping, the license check);
- the task-runner bullet marks the questionnaire's default, not a former one.

The support matrix is only generated when `support.yml` exists (W4 owns that
file), so it is exercised here against a synthetic file instead.
"""

import sys
from pathlib import Path

import pytest

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import gen_docs  # noqa: E402
from tools import questionnaire  # noqa: E402

# Drift this generator exists to prevent (TODO.md: the Features / mermaid text
# vs the questionnaire): the questionnaire has these, the docs did not.
CATALOGUE_GRAPH_MUST_MENTION = (
    "oj_category",
    "ctf",
    "include_scraping",
    "use_recommended_scraping",
    "scraping_engine",
    "license_check",
)


def write_questionnaire(tmp_path: Path) -> Path:
    """A synthetic questionnaire, small enough to pin the renderers exactly."""
    (tmp_path / "questions").mkdir()
    (tmp_path / "questions" / "a.yml").write_text(
        "use_recommended_thing:\n"
        "    type: bool\n"
        "    default: true\n"
        "    help: |\n"
        "        Use the recommended thing?\n"
        "        Recommended: the alpha way.\n"
        "        Answer No to pick the beta way.\n"
    )
    (tmp_path / "questions" / "b.yml").write_text(
        "thing_kind:\n"
        "    type: str\n"
        '    when: "{{ not use_recommended_thing }}"\n'
        "    default: alpha\n"
        "    help: |\n"
        "        Which thing kind?\n"
        "        - alpha: the first kind.\n"
        "        - beta: the second kind.\n"
    )
    config = tmp_path / "copier.yml"
    config.write_text(
        "---\n"
        "project_type:\n"
        "    type: str\n"
        "    choices: [alpha_base, beta_base]\n"
        "    default: alpha_base\n"
        "    help: |\n"
        "        What kind of project is this?\n"
        "        - alpha_base: an alpha base.\n"
        "        - beta_base: a beta base.\n"
        "---\n"
        "!include questions/a.yml\n"
        "---\n"
        "!include questions/b.yml\n"
        "---\n"
        "package_name:\n"
        "    type: str\n"
        "    default: my_package\n"
        "    help: Name of the python import package.\n"
    )
    return config


def test_check_gate_passes_and_is_the_committed_gate(capsys: pytest.CaptureFixture[str]):
    """`--check` renders from the questionnaire and finds no drift."""
    assert gen_docs.main(["--check"]) == 0
    assert "generated block(s) in sync" in capsys.readouterr().out


def test_docs_blocks_are_derived_from_the_questionnaire(tmp_path: Path):
    """A questionnaire edit changes the rendered reference, not just the model."""
    config = write_questionnaire(tmp_path)
    model = gen_docs.Model.load(config)

    areas = gen_docs.render_areas(model)
    assert "| `use_recommended_thing` | the alpha way. | all |" in areas
    assert "| `use_recommended_thing` | the beta way. |" not in areas

    details = gen_docs.render_detailed_questions(model)
    assert "Answer **No** to pick the beta way." in details
    assert "`thing_kind`" in details
    assert "**`alpha`** — the first kind." in details

    graph = gen_docs.render_mermaid(model)
    assert 'G_thing{"use_recommended_thing?"}' in graph
    assert 'G_thing -->|Yes| G_thing_yes["the alpha way."]' in graph
    assert 'G_thing -->|No| G_thing_no["ask: thing_kind"]' in graph  # derived detail
    assert "Project details: package_name" in graph


def test_check_detects_drift_and_write_fixes_it(tmp_path: Path):
    """`--check` fails on a stale block; `--write` restores it from the model."""
    config = write_questionnaire(tmp_path)
    model = gen_docs.Model.load(config)
    doc = tmp_path / "doc.md"
    doc.write_text(f"{gen_docs.BEGIN.format(name='areas')}\nstale text\n{gen_docs.END.format(name='areas')}\n")
    target = gen_docs.GeneratedBlock(doc, "areas", gen_docs.render_areas)

    problems = gen_docs.check(model, [target])
    assert len(problems) == 1
    assert "differs at line 1" in problems[0]
    assert "- stale text" in problems[0]

    assert gen_docs.write(model, [target]) == [f"{doc}: areas"]
    assert "| `use_recommended_thing` | the alpha way. | all |" in doc.read_text(encoding="utf-8")
    assert gen_docs.check(model, [target]) == []

    # A missing marker is a failure to fix, not a silent skip.
    doc.write_text("no markers here\n")
    with pytest.raises(gen_docs.GenDocsError, match="no generated block"):
        gen_docs.write(model, [target])


def test_catalogue_graph_covers_the_option_set_that_drifted():
    """The graph names the questionnaire's CTF / scraping / license-check options."""
    graph = gen_docs.render_mermaid(gen_docs.Model.load())
    missing = [needle for needle in CATALOGUE_GRAPH_MUST_MENTION if needle not in graph]
    assert missing == [], f"the catalogue graph no longer documents {missing}"


def test_task_runner_bullet_marks_the_questionnaires_default():
    """`just` is the questionnaire's default, so the catalogue must say so."""
    model = gen_docs.Model.load()
    assert model.question("task_runner").default == "just"
    bullet = gen_docs.render_features_task_runner(model)
    assert "[Just](https://just.systems) (default)" in bullet
    assert bullet.count("(default)") == 2  # just (uv/poetry) and pixi (pixi)
    assert "Task (default)" not in bullet
    assert "task_runner_pixi" in {q.name for q in model.questions}


def test_support_table_is_generated_only_with_support_yml(tmp_path: Path):
    """Without `support.yml` no support block is targeted (W4 owns the file)."""
    blocks = gen_docs.generated_blocks(support=tmp_path / "support.yml")
    assert "support-table" not in {block.block for block in blocks}
    assert {block.block for block in blocks} >= {"features-areas", "features-mermaid", "areas"}


def test_support_table_follows_the_support_yml_columns(tmp_path: Path):
    """With `support.yml` present the table is generated from its entries."""
    support = tmp_path / "support.yml"
    support.write_text(
        "supported:\n"
        "  - base: library\n"
        "    tier: full\n"
        "    optional: [scraping, mcp]\n"
        "  - base: cli\n"
        "    tier: best_effort\n"
        "    optional: []\n"
    )
    blocks = gen_docs.generated_blocks(support=support)
    target = next(block for block in blocks if block.block == "support-table")
    assert target.path == gen_docs.FEATURES_DOC
    table = target.render_text(gen_docs.Model.load())
    assert "| base | tier | optional |" in table
    assert "| `library` | `full` | `scraping`, `mcp` |" in table
    assert "| `cli` | `best_effort` |  |" in table
    assert "[support.md](support.md)" in table, "the summary must link the full matrix beside it"


def _ragged_tables(text: str) -> list[str]:
    """Pipe-table blocks whose rows disagree on the column count."""
    lines = text.splitlines()
    problems: list[str] = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("|"):
            index += 1
            continue
        start = index
        columns: set[int] = set()
        while index < len(lines) and lines[index].startswith("|"):
            columns.add(lines[index].count("|") - lines[index].count("\\|"))
            index += 1
        if len(columns) != 1:
            problems.append(f"table at line {start + 1} mixes {sorted(columns)} columns")
    return problems


def test_generated_tables_are_well_formed():
    """No generated table may smuggle in a `|` (repo_name's default has one).

    An unescaped pipe splits a row into extra columns, which the `--check`
    gate cannot see: it compares text, not markdown.
    """
    model = gen_docs.Model.load()
    problems = [
        f"{target.block} ({target.path.name}): {problem}"
        for target in gen_docs.generated_blocks()
        for problem in _ragged_tables(target.render_text(model))
    ]
    assert problems == []


def test_questionnaire_model_is_the_committed_questionnaire():
    """Sanity: the model reads the real questionnaire, not a fixture."""
    questions, _settings = questionnaire.load_questions()
    names = [question.name for question in questions]
    assert "project_type" in names
    assert gen_docs.Model.load().question("project_type").choices[:3] == ["library", "web_api", "cli"]
