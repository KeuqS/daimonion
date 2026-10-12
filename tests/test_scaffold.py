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
    assert 'when: "not oj_bare"' in captured
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
    """scaffold_layer outputs guided blocks for questions, invariants, and templates."""
    rc = scaffold.scaffold_layer("redis_cache", description="Redis caching layer", dry_run=True)
    assert rc == 0
    captured = capsys.readouterr().out
    assert "include_redis_cache" in captured
    assert "include=include_redis_cache" in captured
    assert "template/{% if include_redis_cache %}redis_cache{% endif %}" in captured


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
