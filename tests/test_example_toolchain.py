"""The toolchain axes -- package_manager x task_runner x log_library: which
runner file serializes the same task model, and which logging dependency and
setup each choice produces."""

import json
import tomllib
from pathlib import Path

import pytest

from support import copy_project
from support import copy_project_recommended
from support import make_venv


def test_template_log_library_default_is_structlog(tmp_path: Path):
    copy_project_recommended(tmp_path, project_type="cli")
    pyproject_toml = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    deps = pyproject_toml["project"]["dependencies"]
    assert "structlog" in deps
    assert "loguru" not in deps
    assert "picologging" not in deps
    logging_setup = (tmp_path / "src" / "recommended_example" / "logging_setup.py").read_text()
    assert "import structlog" in logging_setup


@pytest.mark.heavy
@pytest.mark.network
def test_template_log_library_loguru(tmp_path: Path):
    copy_project(tmp_path, log_library="loguru")
    pyproject_toml = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert "loguru" in pyproject_toml["project"]["dependencies"]
    logging_setup = (tmp_path / "src" / "daimonion_example" / "logging_setup.py").read_text()
    assert "from loguru import logger" in logging_setup
    run = make_venv(tmp_path)
    run("uvx --from go-task-bin task check")
    # logger.bind(...).info(event, **kv) works the same as the structlog default
    run(
        "uv run --locked python -c "
        '"from daimonion_example.logging_setup import logger; '
        "logger.bind(task_id='T-123').info('job_done', chunks=3)\""
    )


@pytest.mark.heavy
@pytest.mark.network
def test_template_log_library_picologging(tmp_path: Path):
    copy_project(tmp_path, log_library="picologging")
    pyproject_toml = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert "picologging" in pyproject_toml["project"]["dependencies"]
    logging_setup = (tmp_path / "src" / "daimonion_example" / "logging_setup.py").read_text()
    assert "import picologging as logging" in logging_setup
    run = make_venv(tmp_path)
    run("uvx --from go-task-bin task check")


@pytest.mark.heavy
@pytest.mark.network
def test_template_log_library_stdlib(tmp_path: Path):
    copy_project(tmp_path, log_library="logging")
    pyproject_toml = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    deps = pyproject_toml["project"]["dependencies"]
    assert not {"structlog", "loguru", "picologging"} & set(deps)
    logging_setup = (tmp_path / "src" / "daimonion_example" / "logging_setup.py").read_text()
    assert "import logging" in logging_setup
    run = make_venv(tmp_path)
    run("uvx --from go-task-bin task check")


@pytest.mark.heavy
@pytest.mark.network
@pytest.mark.parametrize("log_library", ["structlog", "loguru", "picologging", "logging"])
def test_template_log_library_gcp_json_fields(tmp_path: Path, log_library: str, monkeypatch: pytest.MonkeyPatch):
    """With cloud_provider=gcp, LOG_FORMAT=json should use the field names
    Cloud Logging's structured-log parser recognises (severity/message/time)
    instead of each library's own default (level/event/timestamp), so the
    generated project's logs get severity colouring/filtering for free.
    """
    copy_project(tmp_path, log_library=log_library, cloud_provider="gcp")
    run = make_venv(tmp_path)
    run("uvx --from go-task-bin task check")
    monkeypatch.setenv("LOG_FORMAT", "json")
    output = run(
        "uv run --locked python -c "
        '"from daimonion_example.logging_setup import logger; '
        "logger.bind(task_id='T-123').info('job_done', chunks=3)\""
    )
    payload = json.loads(output)
    assert payload["severity"] == "INFO"
    assert payload["message"] == "job_done"
    assert "time" in payload
    assert "level" not in payload
    assert "event" not in payload
    assert "timestamp" not in payload


def test_template_poetry(tmp_path: Path):
    copy_project(tmp_path, package_manager="poetry")
    # poetry.lock is NOT shipped: a placeholder lock makes poetry install
    # fail on lock inconsistency. The first `poetry install` generates it.
    assert not (tmp_path / "poetry.lock").exists()
    pyproject_toml = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    # poetry cannot interpret a setuptools-scm dynamic version: static
    # version for poetry projects
    assert pyproject_toml["project"]["version"] == "0.1.0"
    assert "version" not in pyproject_toml["project"].get("dynamic", [])
    # Poetry 2.x auto-discovery misses a src/ package renamed by the
    # questionnaire, so the package is listed explicitly.
    packages = pyproject_toml["tool"]["poetry"]["packages"]
    assert packages == [{"include": "daimonion_example", "from": "src"}]
    # The poetry env never gets a setuptools-scm _version.py: the import
    # falls back to the installed distribution's metadata version.
    init = (tmp_path / "src" / "daimonion_example" / "__init__.py").read_text()
    assert "from ._version import __version__" in init
    assert "from importlib.metadata import version" in init
    readme = (tmp_path / "README.md").read_text()
    # only the uv-tested matrix gets the full "3.11 | 3.12 | 3.13 | 3.14" range
    assert "Python-3.11-3776AB" in readme


def test_template_task_runner_just(tmp_path: Path):
    copy_project(tmp_path, task_runner="just")
    assert (tmp_path / "justfile").exists()
    assert not (tmp_path / "Taskfile.yml").exists()
    assert not (tmp_path / "Makefile").exists()
    assert "lint:" in (tmp_path / "justfile").read_text()


def test_template_task_runner_make(tmp_path: Path):
    copy_project(tmp_path, task_runner="make")
    assert (tmp_path / "Makefile").exists()
    assert not (tmp_path / "Taskfile.yml").exists()
    assert "lint:" in (tmp_path / "Makefile").read_text()


def test_template_task_runner_poe(tmp_path: Path):
    copy_project(tmp_path, task_runner="poe")
    assert not (tmp_path / "Taskfile.yml").exists()
    pyproject_toml = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert "lint" in pyproject_toml["tool"]["poe"]["tasks"]
    dev = pyproject_toml["dependency-groups"]["dev"]
    assert any(d.startswith("poethepoet") for d in dev)


def test_template_task_runner_pixi_native(tmp_path: Path):
    copy_project(tmp_path, package_manager="pixi", task_runner_pixi="pixi")
    assert not (tmp_path / "Taskfile.yml").exists()
    pyproject_toml = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    tasks = pyproject_toml["tool"]["pixi"]["feature"]["dev"]["tasks"]
    # same task set as the other runners; `fix` carries no typos step --
    # typos -w rewrites identifiers for single-correction dictionary words,
    # silently, so the spellchecker is report-only: type-check fails, a human decides
    assert {"lint", "fix", "type-check", "test", "check"} <= set(tasks)
    assert "typos -w" not in tasks["fix"]["cmd"]
    assert "typos ." in tasks["type-check"]["cmd"]
    assert "ruff format --check" in tasks["lint"]["cmd"]


def test_template_task_runner_pixi_with_task(tmp_path: Path):
    copy_project(tmp_path, package_manager="pixi", task_runner_pixi="task")
    assert (tmp_path / "Taskfile.yml").exists()
    pyproject = (tmp_path / "pyproject.toml").read_text()
    assert "[tool.pixi.feature.dev.tasks]" not in pyproject


@pytest.mark.heavy
@pytest.mark.network
def test_template_task_runner_just_works(tmp_path: Path):
    copy_project(tmp_path, task_runner="just")
    run = make_venv(tmp_path)
    run("uvx --from rust-just just lint")
