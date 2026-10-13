"""Tests for tools/adopt.py: adoption that can be undone.

The point of the driver is the guarantee, not the render: every test here
either checks the plan (ref judgement, dry run), checks that a failed run
leaves the project exactly as it was, or kills a real run -- or the rollback
or recovery undoing it -- and checks that the journal puts the project back
byte for byte.
"""

import hashlib
import json
import os
import signal
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import adopt  # noqa: E402
from tools import batch  # noqa: E402


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
    )


def make_project(root: Path) -> Path:
    """A minimal pre-existing project that collides with the template."""
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("# MY OWN CI\n")
    (root / "README.md").write_text("# mine\n")
    (root / "pyproject.toml").write_text('[project]\nname = "legacy"\nversion = "0"\n')
    (root / "renovate.json").write_text('{"custom": true}\n')
    return root


def tree(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def dirs(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_dir()}


def digest(root: Path) -> str:
    """One hash over the tree: every path and every file's bytes."""
    accumulator = hashlib.sha256()
    for relative, content in sorted(tree(root).items()):
        accumulator.update(f"{relative}\0".encode())
        accumulator.update(hashlib.sha256(content).digest())
    return accumulator.hexdigest()


def without_journal(snapshot: dict[str, bytes]) -> dict[str, bytes]:
    """A tree snapshot minus the journal, which is the run's own bookkeeping."""
    return {name: content for name, content in snapshot.items() if name != adopt.JOURNAL_NAME}


def pre_existing(snapshot: dict[str, bytes], before: dict[str, bytes]) -> dict[str, bytes]:
    """The part of a tree snapshot that was there before the run started."""
    return {name: content for name, content in snapshot.items() if name in before}


def run_cli(project: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    """tools/adopt.py as a subprocess, the way a user runs it (and dies)."""
    command = [sys.executable, str(TOP / "tools" / "adopt.py"), str(project), *args]
    return subprocess.run(command, capture_output=True, text=True, env={**os.environ, **env}, check=False, timeout=300)


def run_recover(project: Path, *, json_output: bool = False, **env: str) -> subprocess.CompletedProcess[str]:
    return run_cli(project, "--recover", *(["--json"] if json_output else []), **env)


def test_resolve_ref_uses_a_tag_only_when_it_carries_the_questionnaire(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The stale-tag trap, decided rather than assumed."""
    template = tmp_path / "template-repo"
    (template / "questions").mkdir(parents=True)
    (template / "copier.yml").write_text("---\n!include questions/a.yml\n")
    (template / "questions" / "a.yml").write_text("alpha:\n    type: str\n")
    git(template, "init", "-q", "-b", "main")
    git(template, "add", "-A")
    git(template, "commit", "-qm", "one question")
    git(template, "tag", "v1")
    monkeypatch.setattr(adopt, "TOP", template)

    ref, reason = adopt.resolve_ref()
    assert ref == "v1", "a tag with this questionnaire is the right default"
    assert "v1" in reason, "the judgement names the tag it chose"

    # the template grows a question the tag does not have -> the tag is stale
    (template / "questions" / "b.yml").write_text("beta:\n    type: str\n")
    (template / "copier.yml").write_text("---\n!include questions/a.yml\n---\n!include questions/b.yml\n")
    git(template, "add", "-A")
    git(template, "commit", "-qm", "second question")

    ref, reason = adopt.resolve_ref()
    assert ref == "main", "a tag missing a question must not be used"
    assert "beta" in reason, "the judgement names the question the tag lacks"
    assert adopt.resolve_ref("HEAD")[0] == "HEAD", "an explicit ref is honoured"


def test_dry_run_writes_nothing(tmp_path: Path):
    project = make_project(tmp_path)
    before = tree(project)

    result = adopt.adopt(project, ref="HEAD", dry_run=True)

    assert result.ok and not result.applied
    assert result.mode == "adopt"
    assert result.skip == [".github/workflows/ci.yml", "renovate.json"]
    assert tree(project) == before


def test_adoption_keeps_existing_files_and_adds_the_rest(tmp_path: Path):
    project = make_project(tmp_path)

    result = adopt.adopt(project, ref="HEAD")

    assert result.ok and result.applied
    assert result.error is None
    assert (project / ".github" / "workflows" / "ci.yml").read_text() == "# MY OWN CI\n"
    assert (project / "renovate.json").read_text() == '{"custom": true}\n'
    assert (project / "README.md").read_text() == "# mine\n"
    assert (project / "pyproject.toml").read_text().startswith("[project]")
    assert (project / ".gitleaks.toml").exists()
    assert (project / ".github" / "workflows" / "_hygiene.yml").exists()
    assert sorted(result.unchanged) == [".github/workflows/ci.yml", "README.md", "pyproject.toml", "renovate.json"]
    assert result.created and not result.removed and not result.restored
    assert adopt.JOURNAL_NAME not in result.created, "the journal is the run's own bookkeeping"
    assert not (project / adopt.JOURNAL_NAME).exists(), "a committed run leaves no journal"


def test_a_collision_that_was_not_skipped_rolls_the_project_back(tmp_path: Path):
    """The guarantee: a failed run leaves the project exactly as it was.

    `skip=[]` stands for any collision the plan did not cover (a protection
    token deselected, an answer-dependent path): copier stops on the first
    one, and everything it wrote before that stop is undone.
    """
    project = make_project(tmp_path)
    before = tree(project)

    result = adopt.adopt(project, ref="HEAD", skip=[])

    assert not result.ok and not result.applied
    assert result.error is not None, "the collision must be reported"
    assert result.removed, "files created before the stop are removed"
    assert tree(project) == before, "every file is back to its old bytes"
    directories = {str(path.relative_to(project)) for path in project.rglob("*") if path.is_dir()}
    assert directories == {".github", ".github/workflows"}, "not even an empty directory is left behind"
    assert not (project / adopt.JOURNAL_NAME).exists(), "a rolled-back run leaves no journal"


def test_adoption_merges_the_template_dependencies(tmp_path: Path):
    """Dependencies are the one part of the adopter's config that is merged."""
    project = make_project(tmp_path)
    (project / "pyproject.toml").write_text(
        '[project]\nname = "legacy"\nversion = "0"\n# my pin\ndependencies = ["structlog>=9"]\n'
    )

    result = adopt.adopt(project, ref="HEAD")

    assert result.ok and result.deps is not None
    assert result.deps["added"]["dev"], "the dev toolchain is merged"
    assert result.deps["kept"]["runtime"] == ["structlog"], "the dependency they already declare is left alone"
    text = (project / "pyproject.toml").read_text()
    assert "# my pin" in text, "the adopter's file is edited, not replaced"
    merged = tomllib.loads(text)
    assert "structlog>=9" in merged["project"]["dependencies"], "their constraint survives"
    assert "dependency-groups" in merged
    assert any("structlog" in line for line in result.deps["differing"]), "their pin wins, and is reported"


def test_runtime_dependencies_of_a_layer_are_merged(tmp_path: Path):
    """Adopting with a layer (web_api here) brings that layer's runtime deps."""
    project = make_project(tmp_path)
    (project / "pyproject.toml").write_text('[project]\nname = "legacy"\nversion = "0"\ndependencies = []\n')

    result = adopt.adopt(project, ref="HEAD", answers={"project_type": "web_api"})

    assert result.ok and result.deps is not None
    added = result.deps["added"]["runtime"]
    assert any(spec.startswith("fastapi") for spec in added), added
    assert any(spec.startswith("sqlalchemy") for spec in added), added
    assert (project / "app" / "main.py").is_file(), "the layer itself is rendered"
    assert "fastapi" in (project / "pyproject.toml").read_text()


def test_adoption_merges_gitignore_makefile_and_ci(tmp_path: Path):
    """The files an adopter usually already has are merged, not skipped."""
    project = make_project(tmp_path)
    (project / ".gitignore").write_text("*.pyc\n# mine\ncustom/\n")
    (project / "Makefile").write_text("mine:\n\techo mine\n")
    workflows = project / ".github" / "workflows"
    (workflows / "ci.yml").write_text("# MY OWN CI\n")

    result = adopt.adopt(
        project,
        ref="HEAD",
        answers={"use_recommended_toolchain": False, "package_manager": "uv", "task_runner": "make"},
    )

    assert result.ok
    merged = {entry["path"]: entry for entry in result.files_merged}
    assert any(path.endswith(".gitignore") for path in merged)
    assert set(merged).intersection({str(project / ".gitignore"), str(project / "Makefile")})

    assert (project / ".gitignore").read_text().startswith("*.pyc\n# mine\ncustom/\n")
    assert ".pytest_cache/" in (project / ".gitignore").read_text()
    assert (project / "Makefile").read_text().startswith("mine:\n\techo mine\n")
    assert "check:" in (project / "Makefile").read_text()
    assert (workflows / "ci.yml").read_text() == "# MY OWN CI\n", "their workflow is never rewritten"
    caller = workflows / "copier-ci.yml"
    assert caller.is_file()
    assert yaml.safe_load(caller.read_text())["name"] == "Copier CI", "their workflow name is not reused"


def test_adoption_merges_tool_config_but_not_project_paths(tmp_path: Path):
    project = make_project(tmp_path)
    (project / "pyproject.toml").write_text(
        '[project]\nname = "legacy"\nversion = "0"\n\n[tool.ruff]\nline-length = 100\n'
    )

    result = adopt.adopt(project, ref="HEAD")

    assert result.ok and result.tool_config is not None
    parsed = tomllib.loads((project / "pyproject.toml").read_text())
    assert parsed["tool"]["ruff"]["line-length"] == 100, "their setting survives"
    assert parsed["tool"]["ruff"]["lint"]["select"] == ["ALL"], "the template's lint rule set is merged in"
    assert "src" not in parsed["tool"]["ruff"], "the template's path-shaped value is not copied"
    assert any("tool.ruff.line-length" in line for line in result.tool_config["kept"])
    assert result.tool_config["needs_your_value"], "path-shaped values are reported, not copied"


def test_confirmation_yes_applies_the_merges(tmp_path: Path):
    project = make_project(tmp_path)
    (project / ".gitignore").write_text("*.pyc\n")

    result = adopt.adopt(project, ref="HEAD", ask=lambda _question: "yes")

    assert result.ok and not result.cancelled
    assert "__pycache__" in (project / ".gitignore").read_text()


def test_confirmation_no_keeps_the_render_and_skips_the_merges(tmp_path: Path):
    project = make_project(tmp_path)
    (project / ".gitignore").write_text("*.pyc\n")

    result = adopt.adopt(project, ref="HEAD", ask=lambda _question: "no")

    assert result.ok and not result.cancelled
    assert (project / ".gitignore").read_text() == "*.pyc\n", "their file is untouched"
    assert (project / ".gitleaks.toml").exists(), "the render still happened"


def test_confirmation_cancel_rolls_the_render_back(tmp_path: Path):
    project = make_project(tmp_path)
    before = tree(project)

    result = adopt.adopt(project, ref="HEAD", ask=lambda _question: "cancel")

    assert result.cancelled and not result.ok and result.error is None
    assert tree(project) == before, "nothing of the adoption is left behind"


def test_confirmation_can_approve_a_project_specific_value(tmp_path: Path):
    """The values the merge refuses to copy blind are exactly what to ask about."""
    project = make_project(tmp_path)
    (project / "src" / "legacy").mkdir(parents=True)
    (project / "src" / "legacy" / "__init__.py").write_text("")
    (project / "pyproject.toml").write_text('[project]\nname = "legacy"\nversion = "0"\ndependencies = []\n')

    asked: list[str] = []

    def answer(question: str) -> str:
        asked.append(question)
        return "yes"

    result = adopt.adopt(project, ref="HEAD", ask=answer)

    assert result.ok
    assert any("tool.basedpyright.include" in question for question in asked), asked[:3]
    text = (project / "pyproject.toml").read_text()
    assert "src/legacy" in text, "the approved value is the adapted one, for their layout"
    assert "src/my_package" not in text


def test_confirmation_all_approves_every_remaining_value(tmp_path: Path):
    """One "all" answers the rest of the project-specific questions."""
    project = make_project(tmp_path)
    (project / "src" / "legacy").mkdir(parents=True)
    (project / "src" / "legacy" / "__init__.py").write_text("")
    (project / "pyproject.toml").write_text('[project]\nname = "legacy"\nversion = "0"\ndependencies = []\n')

    asked: list[str] = []

    def answer(question: str) -> str:
        asked.append(question)
        return "all" if question.startswith("add ") else "yes"

    result = adopt.adopt(project, ref="HEAD", ask=answer)

    assert result.ok
    value_questions = [question for question in asked if question.startswith("add ")]
    assert len(value_questions) == 1, "everything after the first 'all' is approved without asking"
    text = (project / "pyproject.toml").read_text()
    assert "src/legacy" in text
    assert "testpaths" in text, "later values were approved too"


def test_confirmation_can_approve_appending_to_the_taskfile(tmp_path: Path):
    """The task list is offered and, once approved, appended."""
    project = make_project(tmp_path)
    (project / "Taskfile.yml").write_text("version: '3'\n\ntasks:\n  mine:\n    cmds:\n      - echo mine\n")

    asked: list[str] = []

    def answer(question: str) -> str:
        asked.append(question)
        return "yes"

    result = adopt.adopt(
        project,
        ref="HEAD",
        ask=answer,
        answers={"use_recommended_toolchain": False, "package_manager": "uv", "task_runner": "task"},
    )

    assert result.ok
    assert any("Taskfile" in question for question in asked), "the task list is offered for approval"
    document = yaml.safe_load((project / "Taskfile.yml").read_text())
    assert "mine" in document["tasks"], "their task survives"
    assert "lint" in document["tasks"], "the approved tasks were appended"


def test_taskfile_is_left_alone_without_approval(tmp_path: Path):
    project = make_project(tmp_path)
    (project / "Taskfile.yml").write_text("version: '3'\n\ntasks:\n  mine:\n    cmds:\n      - echo mine\n")
    before = (project / "Taskfile.yml").read_text()

    result = adopt.adopt(project, ref="HEAD", ask=lambda _question: "no")

    assert result.ok
    assert (project / "Taskfile.yml").read_text() == before


def test_plan_and_report_share_one_merge_summary(tmp_path: Path):
    """The prompt's plan and the report's outcome are formatted once.

    `_merge_summary_from` (a plan dict, the prompt's view) and `_merge_summary`
    (an Adoption, the report's view) were two hand-rolled copies of the same
    lines (TODO.md §28.5 R6) -- exactly the drift a summary exists to prevent.
    The second is now an adapter over the first, and this pin holds both
    entrances to the same lines on a real plan.
    """
    project = make_project(tmp_path)
    result = adopt.adopt(project, ref="HEAD", dry_run=True)

    plan = {"dependencies": result.deps, "tool_config": result.tool_config, "files": result.files_merged}
    summary = adopt._merge_summary(result)  # noqa: SLF001
    assert summary == adopt._merge_summary_from(plan)  # noqa: SLF001
    assert summary, "the fixture has something to merge; an empty summary makes the equality vacuous"


@pytest.mark.parametrize("ask", [lambda _question: "yes", None], ids=["interactive", "automatic"])
def test_one_run_renders_the_fresh_scaffold_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ask: Callable[[str], str] | None
):
    """The confirm-then-apply flow renders one fresh scaffold, not one per step.

    The plan a human confirms and the merge that applies it need the same
    scaffold, and nothing between the prompt and the answer can change the
    answers or the template tree -- so the second scaffold the interactive flow
    used to render (three copier renders per adoption) was byte-identical to
    the first. The pin counts real renders, both ways of running: a merge step
    growing its own render back fails here.
    """
    project = make_project(tmp_path)
    (project / ".gitignore").write_text("*.pyc\n")
    real = batch.render
    renders = 0

    def counting(*args: Any, **kwargs: Any) -> None:
        nonlocal renders
        renders += 1
        real(*args, **kwargs)

    monkeypatch.setattr(batch, "render", counting)
    result = adopt.adopt(project, ref="HEAD", ask=ask)

    assert result.ok and not result.cancelled
    assert renders == 2, "the render into the target plus the one shared fresh scaffold"
    assert "__pycache__" in (project / ".gitignore").read_text(), "the merge still applied"


def test_adoption_does_not_merge_when_asked_not_to(tmp_path: Path):
    project = make_project(tmp_path)
    before = (project / "pyproject.toml").read_text()

    result = adopt.adopt(project, ref="HEAD", merge_generated=False)

    assert result.ok and result.deps is None
    assert (project / "pyproject.toml").read_text() == before


def test_dry_run_reports_the_dependency_plan_without_writing(tmp_path: Path):
    project = make_project(tmp_path)
    before = (project / "pyproject.toml").read_text()

    result = adopt.adopt(project, ref="HEAD", dry_run=True)

    assert result.ok and result.deps is not None
    assert "structlog" in result.deps["added"]["runtime"]
    assert (project / "pyproject.toml").read_text() == before


def test_merge_verification_detects_a_rewritten_requirement(tmp_path: Path):
    """The guard behind the rollback: a merge may only add."""
    project = make_project(tmp_path)
    target = project / "pyproject.toml"
    target.write_text('[project]\nname = "legacy"\nversion = "0"\ndependencies = ["httpx>=0.20"]\n')
    before = target.read_bytes()

    assert adopt.merge_problem(target, before) is None, "unchanged file is fine"

    target.write_text('[project]\nname = "legacy"\nversion = "0"\ndependencies = ["httpx>=0.20", "structlog"]\n')
    assert adopt.merge_problem(target, before) is None, "appending is not a violation"

    target.write_text('[project]\nname = "legacy"\nversion = "0"\ndependencies = ["httpx>=0.99"]\n')
    problem = adopt.merge_problem(target, before)
    assert problem is not None and "httpx" in problem

    target.write_text("this is not toml\n")
    assert adopt.merge_problem(target, before), "an unparsable file is a merge problem"

    # ... but only when it parsed *before*: the merge refuses to touch a file
    # that never parsed, so blaming it there refused the whole adoption with a
    # misleading message (found by the stateful adopt run).
    assert adopt.merge_problem(target, b"this is not toml\n") is None, "the merge did not break it"


def test_refuses_a_project_this_template_already_generated(tmp_path: Path):
    (tmp_path / ".copier-answers.yml").write_text("_src_path: https://github.com/ConstitutiveTemplates/daimonion.git\n")
    with pytest.raises(adopt.AdoptError):
        adopt.adopt(tmp_path, ref="HEAD")


def test_refuses_a_foreign_template_until_takeover(tmp_path: Path):
    make_project(tmp_path)
    (tmp_path / ".copier-answers.yml").write_text("_src_path: https://github.com/other/template.git\n")
    with pytest.raises(adopt.OwnershipError):
        adopt.adopt(tmp_path, ref="HEAD")

    result = adopt.adopt(tmp_path, ref="HEAD", takeover=True, dry_run=True)
    assert result.ok and result.mode == "adopt"


def test_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    project = make_project(tmp_path)
    assert adopt.main([str(project), "--ref", "HEAD", "--dry-run", "--no-merge"]) == 0
    assert capsys.readouterr().out.strip(), "a dry run still reports"

    # an uncovered collision: exit 1, and the project is back to its old self
    before = tree(project)
    assert adopt.main([str(project), "--ref", "HEAD", "--no-merge", "--skip", "nothing-actually-collides"]) == 1
    assert tree(project) == before

    other = tmp_path / "other"
    other.mkdir()
    (other / ".copier-answers.yml").write_text("_src_path: https://github.com/other/template.git\n")
    assert adopt.main([str(other), "--ref", "HEAD"]) == 3
    assert capsys.readouterr().err.strip(), "the refusal explains itself on stderr"


def test_main_rejects_a_missing_directory(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert adopt.main([str(tmp_path / "nope")]) == 2
    assert capsys.readouterr().err.strip(), "the refusal explains itself on stderr"


# The crash drills: a real run, killed hard at a named point, then recovered.
CRASH_POINTS = [
    pytest.param("render:1", id="after-the-first-file"),
    pytest.param("render:20", id="mid-render"),
    pytest.param("merge:1", id="after-a-merge-write"),
    pytest.param("verify", id="before-the-final-verify"),
]


@pytest.mark.parametrize("crash_at", CRASH_POINTS)
def test_a_killed_adoption_is_recovered_byte_for_byte(tmp_path: Path, crash_at: str):
    """SIGKILL at any point, and the journal gives the project back exactly.

    The killed run cannot clean up after itself -- that is the point -- so the
    journal it wrote before its first write is the only way back, and what it
    restores is checked against the tree as it was before the run started.
    """
    project = make_project(tmp_path)
    before = tree(project)
    before_dirs = dirs(project)
    identity = digest(project)

    killed = run_cli(project, "--ref", "HEAD", "--yes", COPIER_ADOPT_CRASH_AT=crash_at)
    assert killed.returncode == -signal.SIGKILL, killed.stderr
    assert (project / adopt.JOURNAL_NAME).is_file(), "the journal has to survive the kill"
    assert tree(project) != before, "the drill has to have written something to be worth recovering"

    recovered = run_recover(project)
    assert recovered.returncode == 0, recovered.stderr
    assert "recovered" in recovered.stdout
    assert tree(project) == before, "every file is back to its old bytes"
    assert dirs(project) == before_dirs, "not even an empty directory the run made is left"
    assert digest(project) == identity
    assert not (project / adopt.JOURNAL_NAME).exists(), "the journal goes with the interrupted run"

    again = run_recover(project)
    assert again.returncode == 0
    assert "nothing to recover" in again.stdout
    assert tree(project) == before, "recovering twice changes nothing"
    assert digest(project) == identity


def test_a_kill_during_the_rollback_is_recovered_byte_for_byte(tmp_path: Path):
    """SIGKILL inside the undo itself: the journal finishes the rollback.

    A rollback is a crash region like the render -- the protocol model crashes
    in every state, the undo included -- so a kill while it is still deleting
    has to leave the journal (dropped only once the undo is done) over a
    half-undone tree, and `--recover` finishes what the kill interrupted.
    """
    project = make_project(tmp_path)
    before = tree(project)
    before_dirs = dirs(project)
    identity = digest(project)

    # `--skip` naming a path that does not exist is the uncovered collision:
    # the render writes, the run fails, and the rollback starts.
    killed = run_cli(
        project, "--ref", "HEAD", "--yes", "--skip", "nothing-actually-collides", COPIER_ADOPT_CRASH_AT="rollback"
    )
    assert killed.returncode == -signal.SIGKILL, killed.stderr
    assert (project / adopt.JOURNAL_NAME).is_file(), "the journal outlives a rollback killed mid-undo"
    interrupted = without_journal(tree(project))
    assert interrupted != before, "the drill has to catch the undo in progress, not before it"
    assert set(interrupted) - set(before), "some of what the run created is still there for recovery to remove"
    assert pre_existing(interrupted, before) == before, (
        "the undo was killed putting old bytes back and deleting, not rewriting: the adopter's files are intact"
    )

    recovered = run_recover(project)
    assert recovered.returncode == 0, recovered.stderr
    assert "recovered" in recovered.stdout
    assert tree(project) == before, "recovery finished the rollback the kill interrupted"
    assert dirs(project) == before_dirs, "not even an empty directory survives the finished undo"
    assert digest(project) == identity
    assert not (project / adopt.JOURNAL_NAME).exists(), "the journal goes once the undo is done"

    again = run_recover(project)
    assert again.returncode == 0
    assert "nothing to recover" in again.stdout
    assert digest(project) == identity, "recovering after a finished undo changes nothing"


@pytest.mark.parametrize(
    "killed_at",
    [pytest.param("render:20", id="after-a-render-write"), pytest.param("merge:1", id="after-a-merge-write")],
)
def test_a_kill_during_the_recovery_converges_on_the_next_one(tmp_path: Path, killed_at: str):
    """SIGKILL inside `--recover`: the next `--recover` finishes the undo.

    The recovery drops the journal last precisely so that a kill while it
    applies -- old bytes going back, the run's files being deleted -- leaves
    the same journal it started from, and every step it applies is decided by
    what the tree holds now: the next run converges instead of doubling.
    """
    project = make_project(tmp_path)
    before = tree(project)
    before_dirs = dirs(project)
    identity = digest(project)

    killed = run_cli(project, "--ref", "HEAD", "--yes", COPIER_ADOPT_CRASH_AT=killed_at)
    assert killed.returncode == -signal.SIGKILL, killed.stderr
    assert (project / adopt.JOURNAL_NAME).is_file()

    dying = run_recover(project, COPIER_ADOPT_CRASH_AT="recover")
    assert dying.returncode == -signal.SIGKILL, dying.stderr
    assert (project / adopt.JOURNAL_NAME).is_file(), "the journal survives the recovery it was mid-way through"
    interrupted = without_journal(tree(project))
    assert interrupted != before, "the drill has to catch the recovery in progress, not before it"
    assert pre_existing(interrupted, before) == before, (
        "the recovery died with the original bytes already back: only the run's own files are in question"
    )
    assert set(interrupted) - set(before), "and some of what the run created is still there to remove"

    recovered = run_recover(project)
    assert recovered.returncode == 0, recovered.stderr
    assert "recovered" in recovered.stdout
    assert tree(project) == before, "the second recovery finishes what the first could not"
    assert dirs(project) == before_dirs
    assert digest(project) == identity
    assert not (project / adopt.JOURNAL_NAME).exists()

    again = run_recover(project)
    assert again.returncode == 0
    assert "nothing to recover" in again.stdout
    assert digest(project) == identity, "a recovery after a converged one changes nothing"


def test_the_journal_records_the_old_bytes_and_what_was_there(tmp_path: Path):
    """The journal is written before the first change, so it cannot be missing
    anything the run did next -- and it never mistakes its own file for part of
    the project it is about to change."""
    project = make_project(tmp_path)
    before = tree(project)

    killed = run_cli(project, "--ref", "HEAD", "--yes", COPIER_ADOPT_CRASH_AT="render:1")
    assert killed.returncode == -signal.SIGKILL

    journal = json.loads((project / adopt.JOURNAL_NAME).read_text())
    assert journal["version"] == 1
    assert journal["target"] == str(project), "the journal names the project it belongs to"
    assert sorted(journal["old"]) == sorted(before), "the old bytes of every file the run may modify are recorded"
    assert sorted(journal["existing"]) == sorted(before), "and every file that was there is listed"
    assert adopt.JOURNAL_NAME not in journal["existing"], "the journal itself is not one of the files it records"
    assert journal["dirs"] == [".github", ".github/workflows"], "the directories, so recovery can remove empty ones"


def test_a_stale_journal_refuses_a_new_adoption(tmp_path: Path):
    """Nobody chose this state, so a plan built from it would be about an accident."""
    project = make_project(tmp_path)
    killed = run_cli(project, "--ref", "HEAD", "--yes", COPIER_ADOPT_CRASH_AT="render:20")
    assert killed.returncode == -signal.SIGKILL
    interrupted = tree(project)

    refused = run_cli(project, "--ref", "HEAD", "--yes")
    assert refused.returncode == 4
    assert "--recover" in refused.stderr, "the refusal says how to get out"
    assert tree(project) == interrupted, "the refusal wrote nothing"
    assert (project / adopt.JOURNAL_NAME).is_file(), "and it left the journal alone"

    with pytest.raises(adopt.StaleJournalError):
        adopt.adopt(project, ref="HEAD")


def test_recovery_reports_json_and_succeeds_when_there_is_nothing_to_do(tmp_path: Path):
    project = make_project(tmp_path)
    before = tree(project)
    killed = run_cli(project, "--ref", "HEAD", "--yes", COPIER_ADOPT_CRASH_AT="render:20")
    assert killed.returncode == -signal.SIGKILL

    recovered = run_recover(project, json_output=True)
    assert recovered.returncode == 0
    payload = json.loads(recovered.stdout)
    assert payload["found"] is True and payload["applied"] is True
    assert payload["removed"], "the files the render created are named"
    assert payload["restored"] == [], "nothing existing had been changed yet"
    assert tree(project) == before

    nothing = run_recover(project, json_output=True)
    assert nothing.returncode == 0
    payload = json.loads(nothing.stdout)
    assert payload["found"] is False and payload["applied"] is False
    assert payload["restored"] == [] and payload["removed"] == []

    refusal = run_cli(project, "--recover", "--dry-run")
    assert refusal.returncode == 2, "the two flags promise opposite things"
    assert "dry-run" in refusal.stderr


def test_recovery_refuses_a_journal_from_another_project(tmp_path: Path):
    """Recovery writes recorded bytes back, so it must be sure about the tree."""
    project = make_project(tmp_path)
    killed = run_cli(project, "--ref", "HEAD", "--yes", COPIER_ADOPT_CRASH_AT="render:20")
    assert killed.returncode == -signal.SIGKILL
    elsewhere = make_project(tmp_path / "elsewhere")
    (elsewhere / adopt.JOURNAL_NAME).write_bytes((project / adopt.JOURNAL_NAME).read_bytes())
    untouched = tree(elsewhere)

    refused = run_recover(elsewhere)

    assert refused.returncode == 2
    assert "records" in refused.stderr, "the refusal says whose journal it is"
    assert tree(elsewhere) == untouched


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM], ids=["SIGINT", "SIGTERM"])
def test_a_signal_mid_run_rolls_the_project_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signum: int):
    """SIGINT/SIGTERM take the same way back as any other failure.

    SIGKILL cannot be caught at all; the journal above is the answer to that.
    """
    project = make_project(tmp_path)
    before = tree(project)
    render = batch.render

    def interrupted(*args: Any, **kwargs: Any) -> None:
        render(*args, **kwargs)
        signal.raise_signal(signum)
        for _ in range(100):  # the handler runs at the next bytecode boundary
            pass
        message = "the signal did not interrupt the run"
        raise AssertionError(message)

    monkeypatch.setattr(batch, "render", interrupted)
    result = adopt.adopt(project, ref="HEAD")

    assert not result.ok and not result.applied
    assert result.error is not None and "interrupted" in result.error, result.error
    assert tree(project) == before, "a signal is a rollback, not a half-written project"
    assert not (project / adopt.JOURNAL_NAME).exists(), "the journal goes with the rollback"
