"""Tests for tools/scaffold.py: question, layer, and preset generator."""

from __future__ import annotations

from typing import Any

from tools import scaffold


def test_validate_expression_satisfiable():
    """Satisfiable when expressions return True."""
    ok, msg = scaffold.validate_expression("project_type == 'library' and is_uv")
    assert ok is True
    assert "Satisfiable" in msg


def test_validate_expression_unsatisfiable():
    """Unsatisfiable when expressions return False."""
    ok, msg = scaffold.validate_expression("project_type == 'library' and project_type == 'cli'")
    assert ok is False
    assert "unsatisfiable" in msg.lower()


def test_scaffold_question_dry_run(capsys: Any):
    """scaffold_question with dry_run prints expected block without modifying files."""
    rc = scaffold.scaffold_question(
        "custom_feature_flag",
        qtype="bool",
        when="not oj_bare",
        default=True,
        help_text="Enable custom feature?",
        dry_run=True,
    )
    assert rc == 0
    captured = capsys.readouterr().out
    assert "custom_feature_flag:" in captured
    assert "type: bool" in captured
    assert 'when: "{{ not oj_bare }}"' in captured
    assert "default: true" in captured
    assert "Enable custom feature?" in captured


def test_scaffold_question_nonexistent_file():
    """scaffold_question fails cleanly when the target file does not exist."""
    rc = scaffold.scaffold_question(
        "bad_flag",
        target_file="questions/nonexistent_file_xyz.yml",
    )
    assert rc == 1


def test_scaffold_layer_dry_run(capsys: Any):
    """scaffold_layer outputs guided blocks for questions, invariants, layers matrix, and template."""
    rc = scaffold.scaffold_layer("redis_cache", description="Redis caching layer", dry_run=True)
    assert rc == 0
    captured = capsys.readouterr().out
    assert "include_redis_cache" in captured
    assert "questions/_combo.yml" in captured
    assert "include=include_redis_cache" in captured
    assert "tests/matrix/layers.yml" in captured
    assert "redis_cache_effective" in captured


def test_scaffold_preset_dry_run(capsys: Any):
    """scaffold_preset formats preset YAML properly."""
    rc = scaffold.scaffold_preset(
        "micro-service",
        description="FastAPI microservice preset",
        base_project_type="web_api",
        answers_map={"docker": True, "pypi": False},
        dry_run=True,
    )
    assert rc == 0
    captured = capsys.readouterr().out
    assert "project_type: web_api" in captured
    assert "docker: true" in captured
    assert "pypi: false" in captured


def test_scaffold_check_passes():
    """scaffold_check confirms existing questionnaire SAT and model consistency."""
    rc = scaffold.scaffold_check()
    assert rc == 0


def test_scaffold_question_emits_braced_when(capsys: Any):
    """The stub's `when` is a Jinja template: bare input gains {{ }}."""
    rc = scaffold.scaffold_question(
        "probe_braces",
        qtype="bool",
        when="project_type == 'library'",
        default=True,
        help_text="Probe?",
        dry_run=True,
    )
    assert rc == 0
    captured = capsys.readouterr().out
    assert "when: \"{{ project_type == 'library' }}\"" in captured


def test_scaffold_question_rejects_unknown_type(capsys: Any):
    """Copier has no `int` question type: scaffold refuses it instead of emitting a broken stub."""
    rc = scaffold.scaffold_question("probe_bad_type", qtype="int", dry_run=True)
    assert rc == 1
    assert "bool, str, or yaml" in capsys.readouterr().err


def test_scaffold_preset_rejects_unknown_base(capsys: Any):
    """A preset on a non-choice project_type would never render: scaffold refuses it."""
    rc = scaffold.scaffold_preset("probe-preset-xyz", base_project_type="bad_type_xyz", dry_run=True)
    assert rc == 1
    assert "unknown base project_type" in capsys.readouterr().err


def test_scaffold_preset_base_choices_match_questionnaire():
    """Every committed preset's base is a live project_type choice (no drift)."""
    from tools import answers  # noqa: PLC0415
    from tools import questionnaire  # noqa: PLC0415
    from tools import when_model  # noqa: PLC0415

    questions, _order = when_model.load_questions()
    valid = questionnaire.static_str_choices(questions["project_type"])
    for name in answers.preset_names():
        base = answers.read_preset(name).get("project_type")
        assert base in valid, f"preset {name} pins unknown base {base!r}"


def test_scaffold_question_main_rejects_int_type():
    """The CLI's --type choices match the questionnaire's real types (no `int`)."""
    import pytest  # noqa: PLC0415

    with pytest.raises(SystemExit) as exc:
        scaffold.main(["question", "probe_cli", "--type", "int", "--dry-run"])
    assert exc.value.code == 2  # argparse exits 2 on an invalid choice
