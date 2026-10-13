"""The docs engines and the quality/CI gates: which docs tree each docs_type
renders, what the generated workflows jobs run, hygiene/secrets, the license +
FAIR/security metadata, and the ruff/basedpyright configurations the generated
projects are checked with."""

import json
import re
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

import jinja2
import pytest
import yaml
from copier import run_copy

from support import TOP
from support import ci_requested_tasks
from support import copy_project
from support import copy_project_recommended
from support import make_venv

sys.path.insert(0, str(TOP))

from tools import questionnaire  # noqa: E402


def _renovate_rules(path: Path) -> list[dict]:
    """The generated renovate.json's packageRules."""
    return json.loads(path.read_text())["packageRules"]


def _renovate_disables(path: Path, action: str) -> bool:
    """True if renovate is told to leave this action's version to copier."""
    return any(
        action in rule.get("matchPackageNames", []) and rule.get("enabled") is False for rule in _renovate_rules(path)
    )


def _renovate_mentions(path: Path, needle: str) -> bool:
    return any(needle in name for rule in _renovate_rules(path) for name in rule.get("matchPackageNames", []))


@pytest.mark.heavy
@pytest.mark.network
def test_template_with_extra_code_and_api_docs(tmp_path: Path):
    copy_project(tmp_path, docs_type="sphinx", project_type="library")
    run = make_venv(tmp_path)
    # add some code
    init = tmp_path / "src" / "daimonion_example" / "__init__.py"
    init.write_text(
        init.read_text()
        .replace(
            "__version__: str\ntry:",
            "from daimonion_example import extra_pkg\n\n__version__: str\ntry:",
        )
        .replace(
            'version("ConstitutiveTemplates-daimonion-example")\n\n__all__ = ["__version__"]',
            'version("ConstitutiveTemplates-daimonion-example")\n\n\nclass TopCls:\n    """A top level class."""\n\n\n__all__ = ["TopCls", "__version__", "extra_pkg"]',
        )
    )
    extra_pkg = tmp_path / "src" / "daimonion_example" / "extra_pkg"
    extra_pkg.mkdir()
    (extra_pkg / "__init__.py").write_text('"""Extra Package."""\n')
    code = '''"""A module."""


class Thing:
    """A docstring."""
'''
    (extra_pkg / "extra_module.py").write_text(code)
    run("git add .")  # track the added code so the docs build sees it
    # Build
    run("uvx --from go-task-bin task check")
    run("uvx --from go-task-bin task docs")
    # Check it generates the right output
    api_dir = tmp_path / "build" / "html" / "_api"
    top_html = api_dir / "daimonion_example.html"
    assert "extra_pkg" in top_html.read_text()
    assert "Extra Package." in top_html.read_text()
    assert "TopCls" in top_html.read_text()
    assert "A top level class." in top_html.read_text()
    assert "__version__" in top_html.read_text()
    assert "setuptools_scm" in top_html.read_text()
    package_html = api_dir / "daimonion_example.extra_pkg.html"
    assert "extra_module" in package_html.read_text()
    assert "A module." in package_html.read_text()
    module_html = api_dir / "daimonion_example.extra_pkg.extra_module.html"
    assert "Thing" in module_html.read_text()
    assert "A docstring." in module_html.read_text()


def test_template_pyrefly(tmp_path: Path):
    copy_project(tmp_path, type_checker="pyrefly")
    pyproject = (tmp_path / "pyproject.toml").read_text()
    assert "[tool.basedpyright]" in pyproject
    assert "[tool.pyrefly]" in pyproject


def test_template_ty(tmp_path: Path):
    copy_project(tmp_path, type_checker="ty")
    pyproject = (tmp_path / "pyproject.toml").read_text()
    # basedpyright is always present; ty is the secondary checker.
    assert "[tool.basedpyright]" in pyproject
    assert "[tool.ty]" in pyproject


def test_template_no_docs(tmp_path: Path):
    copy_project(tmp_path, docs_type="README")
    # README-only: no docs site config, no docs/ tree, no docs build task
    assert not (tmp_path / "zensical.toml").exists()
    assert not (tmp_path / "docs").exists()
    assert "task docs" not in (tmp_path / "Taskfile.yml").read_text()


def test_template_no_precommit_hygiene_in_ci(tmp_path: Path):
    """pre-commit is replaced by: task-runner lint/fix tasks (ruff, local)
    plus a hygiene workflow (secrets, workflow linting, YAML/EOF, conventional
    commits, REUSE/CFF — CI-only)."""
    copy_project(tmp_path, task_runner="task")
    # nothing pre-commit-shaped ships in the generated project
    assert not (tmp_path / ".pre-commit-config.yaml").exists()
    taskfile = (tmp_path / "Taskfile.yml").read_text()
    assert "pre-commit" not in taskfile
    assert "ruff format --check ." in taskfile
    pyproject = (tmp_path / "pyproject.toml").read_text()
    assert "pre-commit" not in pyproject
    # the hygiene workflow exists, is a reusable workflow, and pins actions
    hygiene = (tmp_path / ".github" / "workflows" / "_hygiene.yml").read_text()
    assert "workflow_call:" in hygiene
    assert "GITLEAKS_VERSION: " in hygiene  # pinned binary, not the license-gated action
    assert "reviewdog" not in hygiene  # actionlint runs via the digest-pinned docker step
    assert "docker://rhysd/actionlint@sha256:" in hygiene
    # CI calls it and includes it in the required-checks gate
    ci = (tmp_path / ".github" / "workflows" / "ci.yml").read_text()
    assert "uses: ./.github/workflows/_hygiene.yml" in ci
    assert "needs: [hygiene, lint, test" in ci
    # the fix task exists as the pre-commit replacement
    assert "fix:" in taskfile


def test_template_zensical_docs(tmp_path: Path):
    copy_project(tmp_path, docs_type="zensical")
    pyproject_toml = tmp_path / "pyproject.toml"
    assert '"zensical"' in pyproject_toml.read_text()
    assert (tmp_path / "zensical.toml").exists()
    assert (tmp_path / "docs").exists()


def test_template_great_docs(tmp_path: Path):
    copy_project(tmp_path, docs_type="great-docs")
    assert (tmp_path / "great-docs.yml").exists()
    assert (tmp_path / "index.qmd").exists()


def test_template_library_sphinx_version_command(tmp_path: Path):
    """Non-web_api types keep the CLI --version check, named exactly."""
    copy_project(tmp_path, docs_type="README")
    ci = (tmp_path / ".github" / "workflows" / "ci.yml").read_text()
    assert "version-command: python -m daimonion_example --version" in ci
    # The guess-based fallback stays only as the reusable workflow's default.
    dist = (tmp_path / ".github" / "workflows" / "_dist.yml").read_text()
    assert "version-command" in dist


def test_template_no_ci(tmp_path: Path):
    copy_project(tmp_path, ci_provider="none")
    assert not (tmp_path / ".github" / "workflows").exists()
    # GitHub-specific files are still generated
    assert (tmp_path / ".github" / "actionlint.yaml").exists()


def _action_names(workflow: dict) -> set[str]:
    """Third-party `uses:` owners of one parsed workflow (renovate's view)."""
    names = set()
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            action = step.get("uses")
            if action and not action.startswith("./"):
                names.add(action.split("@")[0].removeprefix("docker://"))
    return names


def _assert_update_workflow_shape(text: str) -> dict:
    """The actionlint contract a generated template-update.yml must satisfy."""
    assert "{% if" not in text and "{%" not in text.replace("{% raw %}", ""), (
        "unrendered Jinja left in template-update.yml"
    )
    workflow = yaml.safe_load(text)
    assert "permissions" in workflow, "top-level permissions block required"
    assert workflow.get("permissions") == {"contents": "read"}, (
        f"top-level must be read-only, got {workflow.get('permissions')}"
    )
    assert "timeout-minutes" not in workflow, "timeout-minutes belongs on jobs, not the workflow"
    assert "concurrency" in workflow, "concurrency group required (no overlapping trials)"
    job = workflow["jobs"]["update"]
    assert job.get("timeout-minutes"), "the update job needs timeout-minutes"
    assert job.get("permissions") == {"contents": "write", "pull-requests": "write"}, (
        f"minimal PR scopes required, got {job.get('permissions')}"
    )
    # PyYAML reads YAML 1.1, where `on:` parses as boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert triggers is not None, "the workflow needs an `on:` block"
    assert "workflow_dispatch" in triggers, "manual dispatch required"
    assert "schedule" in triggers, "weekly schedule required"
    runs = " ".join(str(step.get("run", "")) for step in job["steps"])
    assert "copier update" in runs, "the trial must run copier update"
    assert "gh pr create" in runs, "the trial must open its PR with gh"
    assert "TEMPLATE_UPDATE" in text, "the opt-in guard must be present"
    assert "persist-credentials: false" in text, "checkout must not persist credentials"
    sha_re = re.compile(r"^[0-9a-f]{40}$")
    for step in job["steps"]:
        uses = step.get("uses", "")
        if uses and not uses.startswith("./"):
            _owner, _, ref = uses.partition("@")
            assert sha_re.match(ref), f"uses {uses!r} must be SHA-pinned"
    return workflow


def test_template_update_workflow_ships_on_github_actions(tmp_path: Path):
    copy_project(tmp_path)
    path = tmp_path / ".github" / "workflows" / "template-update.yml"
    assert path.exists(), "github_actions must ship the update workflow"
    workflow = _assert_update_workflow_shape(path.read_text())
    # The update workflow's actions stay inside renovate's tracked set, so
    # digest pinning keeps moving them (the equality the parametrized
    # contract below holds for the whole workflows dir).
    config_actions: set[str] = set()
    for rule in json.loads((tmp_path / "renovate.json").read_text())["packageRules"]:
        if rule.get("matchManagers") == ["github-actions"]:
            config_actions.update(rule.get("matchPackageNames", []))
    assert _action_names(workflow) <= config_actions, (
        f"update workflow uses actions renovate does not track: {_action_names(workflow) - config_actions}"
    )
    readme = (tmp_path / "README.md").read_text()
    assert "TEMPLATE_UPDATE" in readme, "README must document the opt-in variable"
    assert "never merges itself" in readme, "README must say the PR is never auto-merged"


def test_template_update_workflow_absent_without_github_actions(tmp_path: Path):
    no_ci = tmp_path / "no-ci"
    copy_project(no_ci, ci_provider="none")
    assert not (no_ci / ".github" / "workflows" / "template-update.yml").exists()
    gitlab = tmp_path / "gitlab"
    copy_project(gitlab, git_platform="gitlab.com", gitlab_group="mygroup")
    assert not (gitlab / ".github").exists()


def test_template_license_check_task(tmp_path: Path):
    """Recommended path ships pip-licenses + a standalone license-check task.

    The task stays out of local `type-check`/`check` (both must run
    offline): CI's lint job calls `lint,type-check,license-check` together
    instead (see ci.yml / .gitlab-ci.yml). Opting out drops the dep and
    the task.
    """
    copy_project(tmp_path, project_type="cli")
    pyproject = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert any(d.startswith("pip-licenses") for d in pyproject["dependency-groups"]["dev"])
    tasks = yaml.safe_load((tmp_path / "Taskfile.yml").read_text())["tasks"]
    assert any("pip-licenses" in str(command) for command in tasks["license-check"]["cmds"])
    assert not any("pip-licenses" in str(command) for command in tasks["type-check"]["cmds"]), (
        "type-check must stay runnable offline"
    )
    assert "license-check" in ci_requested_tasks(tmp_path / ".github" / "workflows" / "ci.yml")

    off_path = tmp_path / "off"
    copy_project(
        off_path,
        project_type="cli",
        use_recommended_security=False,
        security_policy=True,
        scorecard=False,
        license_check=False,
    )
    off_pyproject = tomllib.loads((off_path / "pyproject.toml").read_text())
    assert not any(d.startswith("pip-licenses") for d in off_pyproject["dependency-groups"]["dev"])
    assert "license-check" not in (off_path / "Taskfile.yml").read_text()


def test_license_check_gate_is_armed_for_every_offered_license():
    """The copyleft gate ships a policy for every license the questionnaire offers.

    `test_template_license_check_task` proves the task exists; this proves it
    can *fail*. The policy is derived from the project license, and it used to
    be a membership list -- every license outside it (Proprietary,
    Confidential, MPL-2.0, Zlib, EPL-2.0, ...) silently rendered
    `pip-licenses --partial-match` with **no** `--fail-on`, i.e. a gate that
    can never fail, while _shared/ethics/REGISTRY.yml reported the license
    rule's enforcement as L2 (a real gate) for all of them. Proprietary and
    Confidential are the worst of the set: absorbing copyleft into a
    closed-source product is precisely what that gate is for.

    The policy expression is evaluated as the Jinja the renderer evaluates,
    against every choice the questionnaire offers -- not a Python restatement
    of its branches, which would agree with any rewrite of the template.
    """
    source = (TOP / "_tasks.jinja").read_text(encoding="utf-8")
    match = re.search(r"\{% set license_fail_on = (.+?)%\}", source)
    assert match, "the license fail-on policy moved or was renamed"

    licenses = next(q for q in questionnaire.load_questions()[0] if q.name == "license").choices
    assert len(licenses) >= 40, f"the license question shrank to {len(licenses)} choices"

    # The same Jinja the template parses under; the expression is a plain
    # conditional over one variable, so no copier-specific global is needed.
    # Jinja renders bare text literally, so the expression needs its `{{ }}`.
    env = jinja2.Environment()
    template = env.from_string("{{ " + match.group(1).strip() + " }}")
    resolved = {spdx: template.render(license_effective=spdx).strip() for spdx in licenses}

    unarmed = sorted(spdx for spdx, policy in resolved.items() if not policy)
    assert unarmed == ["AGPL-3.0"], (
        "every offered license except AGPL-3.0 (nothing stronger exists to fail on)"
        f" must arm the gate; these would ship an inert license-check: {unarmed}"
    )
    # What each policy actually trips, under --partial-match: a
    # case-insensitive *substring* test against the license string
    # `pip-licenses` reports. These strings are the ones it really emits
    # (measured: the dist-info metadata for GPL/LGPL/AGPL/MPL/MIT packages),
    # and the exit codes below were measured against `pip-licenses 5.5.5`.
    # Note the substring subtlety the strings carry: "GPL" is *not* a
    # substring of "GNU General Public License v3" spelled out, but it is of
    # the "(GPLv3)" pip-licenses actually appends -- so the policy works
    # because of the parenthesised tag, which is worth pinning here.
    emitted = {
        "gpl": "GNU General Public License v3 (GPLv3)",
        "lgpl": "GNU Library or Lesser General Public License (LGPL)",
        "agpl": "GNU Affero General Public License v3.0 (AGPLv3)",
        "mit": "MIT License",
        "mpl": "Mozilla Public License 2.0 (MPL 2.0)",
    }

    def trips(policy: str, dependency_license: str) -> bool:
        # An empty policy means `--fail-on` is omitted entirely (the template
        # drops the flag rather than passing an empty value), so nothing trips.
        return bool(policy) and policy.lower() in dependency_license.lower()

    for spdx in licenses:
        policy = resolved[spdx]
        family = {
            "GPL": ("gpl", "lgpl", "agpl"),
            "AGPL": ("agpl",),
            "": (),
        }[policy]
        for key, text in emitted.items():
            assert trips(policy, text) == (key in family), (
                f"{spdx} (fail-on={policy!r}) against {key!r} ({text!r}): expected"
                f" {'a trip' if key in family else 'no trip'}"
            )
    assert resolved["MIT"] == "GPL" and resolved["Proprietary"] == "GPL", (
        "permissive/closed projects fail on all copyleft"
    )
    assert resolved["GPL-3.0"] == "AGPL", "a GPL project tolerates its own family and fails only on AGPL"
    assert resolved["AGPL-3.0"] == "", "nothing is stronger than AGPL to fail on"


def test_template_ci_runs_license_check(tmp_path: Path):
    """CI lint calls the standalone license-check; GitLab matches."""
    copy_project(tmp_path, project_type="cli")
    assert "license-check" in ci_requested_tasks(tmp_path / ".github" / "workflows" / "ci.yml")

    gitlab_path = tmp_path / "gitlab"
    copy_project(
        gitlab_path,
        project_type="cli",
        git_platform="gitlab.com",
        gitlab_group="mygroup",
    )
    gitlab = yaml.safe_load((gitlab_path / ".gitlab-ci.yml").read_text())
    assert any("license-check" in line for line in gitlab["lint"]["script"]), "GitLab's lint job matches"


def test_template_legal_check_task(tmp_path: Path):
    """Recommended path ships a standalone legal-check task + an AGENTS.md row.

    law-lint is network-dependent (uvx fetches it from git), so the task
    stays out of `type-check`/`check` like audit/license-check (both must
    run offline). The AGENTS.md command table iterates `agent_cmd_specs`,
    not the task model, so without a spec entry the guide silently omits it.
    """
    copy_project(tmp_path, project_type="cli")
    tasks = yaml.safe_load((tmp_path / "Taskfile.yml").read_text())["tasks"]
    assert any("law-lint" in str(command) for command in tasks["legal-check"]["cmds"])
    assert not any("law-lint" in str(command) for command in tasks["type-check"]["cmds"]), (
        "type-check must stay runnable offline"
    )
    assert "legal-check" not in tasks["check"].get("deps", []), "check must stay runnable offline"
    assert "task legal-check" in (tmp_path / "AGENTS.md").read_text()


@pytest.mark.parametrize(
    "runner, answers, runner_file, task_name",
    [
        ("task", {"use_recommended_toolchain": False, "task_runner": "task"}, "Taskfile.yml", "legal-check"),
        ("just", {"use_recommended_toolchain": False, "task_runner": "just"}, "justfile", "legal-check"),
        ("make", {"use_recommended_toolchain": False, "task_runner": "make"}, "Makefile", "legal-check"),
        ("poe", {"use_recommended_toolchain": False, "task_runner": "poe"}, "pyproject.toml", "legal-check"),
        ("invoke", {"use_recommended_toolchain": False, "task_runner": "invoke"}, "tasks.py", "legal_check"),
        ("duty", {"use_recommended_toolchain": False, "task_runner": "duty"}, "duties.py", "legal_check"),
        (
            "pixi",
            {"use_recommended_toolchain": False, "package_manager": "pixi", "task_runner_pixi": "pixi"},
            "pyproject.toml",
            "legal-check",
        ),
    ],
)
def test_legal_check_task_ships_on_every_runner(
    tmp_path: Path, runner: str, answers: dict[str, Any], runner_file: str, task_name: str
):
    """Every runner serializes the legal-check task and AGENTS.md lists it."""
    target = tmp_path / runner
    copy_project(target, project_type="cli", **answers)
    rendered = (target / runner_file).read_text()
    assert task_name in rendered, f"{runner} drops the legal-check task"
    assert "law-lint" in rendered, f"{runner} legal-check lost its law-lint command"
    assert "legal-check" in (target / "AGENTS.md").read_text(), f"{runner} AGENTS.md omits legal-check"


def test_template_gitleaks_blocks_deidentification_salt(tmp_path: Path):
    """The generated gitleaks config carries the deidentification-salt rule."""
    copy_project(tmp_path, project_type="cli")
    gitleaks = (tmp_path / ".gitleaks.toml").read_text()
    assert "deidentification-salt" in gitleaks
    assert "secret_salt" in gitleaks


# The render inputs of test_template_author_orcid_validator, composed with
# tools/answers.py BASE at the call site: registered in
# tests/test_answer_fixtures.py like every other answer fixture, so a renamed
# question cannot silently rot the validator probe.
ORCID_INVALID_ANSWERS: dict[str, object] = {
    "project_type": "library",
    "use_recommended_license": False,
    "fair": True,
    "author_orcid": "not-an-orcid",
}


def test_template_author_orcid_validator(tmp_path: Path):
    """A malformed ORCID iD is rejected at question time (validator)."""
    from tools.answers import BASE

    with pytest.raises(ValueError) as excinfo:
        run_copy(
            src_path=str(TOP),
            dst_path=tmp_path,
            data={**BASE, **ORCID_INVALID_ANSWERS},
            vcs_ref="HEAD",
            defaults=True,
            unsafe=True,
            overwrite=True,
            skip_tasks=True,
        )
    assert "not-an-orcid" in str(excinfo.value), "the refusal names the rejected iD"


def test_template_license_choice(tmp_path: Path):
    copy_project(tmp_path, license="GPL-3.0")
    assert "GNU GENERAL PUBLIC LICENSE" in (tmp_path / "LICENSE").read_text()
    pyproject_toml = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert pyproject_toml["project"]["license"] == "GPL-3.0"
    assert pyproject_toml["project"]["license-files"] == ["LICENSE"]


def test_template_license_proprietary(tmp_path: Path):
    copy_project(tmp_path, license="Proprietary")
    license_text = (tmp_path / "LICENSE").read_text()
    assert "All Rights Reserved" in license_text
    assert "UNAUTHORIZED COPYING" in license_text
    pyproject_toml = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    # PEP 639 has no SPDX expression for "no license": omit the field entirely
    assert "license" not in pyproject_toml["project"]


def test_template_fair_metadata(tmp_path: Path):
    copy_project(
        tmp_path,
        fair=True,
        author_orcid="0000-0002-1825-0099",
        data_reusable=True,
        data_ethics=True,
    )
    cff = (tmp_path / "CITATION.cff").read_text()
    assert "cff-version: 1.2.0" in cff
    assert 'title: "daimonion-example"' in cff
    assert 'repository-code: "https://github.com/ConstitutiveTemplates/daimonion-example"' in cff
    assert 'license: "Apache-2.0"' in cff
    assert 'orcid: "https://orcid.org/0000-0002-1825-0099"' in cff
    reuse_toml = (tmp_path / "REUSE.toml").read_text()
    assert 'SPDX-License-Identifier = "Apache-2.0"' in reuse_toml
    hygiene = (tmp_path / ".github" / "workflows" / "_hygiene.yml").read_text()
    assert "uvx cffconvert==2.0.0 --validate" in hygiene
    assert "fsfe/reuse-action@" in hygiene
    assert (tmp_path / "data" / "DUO.md").exists()
    assert (tmp_path / "data" / "CARE.md").exists()
    assert "Traceability & provenance" in (tmp_path / "data" / "CARE.md").read_text()
    fair_workflow = tmp_path / ".github" / "workflows" / "fair-software.yml"
    assert fair_workflow.exists()
    uses = [
        step["uses"]
        for job in yaml.safe_load(fair_workflow.read_text())["jobs"].values()
        for step in job.get("steps") or []
        if str(step.get("uses", "")).startswith("fair-software/howfairis-github-action")
    ]
    assert uses, "the FAIR workflow must run howfairis"
    assert all(re.fullmatch(r"fair-software/howfairis-github-action@[0-9a-f]{40}", ref) for ref in uses), uses
    assert _renovate_disables(tmp_path / "renovate.json", "fair-software/howfairis-github-action"), (
        "the action's version is owned by copier update, not renovate"
    )


def test_template_fair_off(tmp_path: Path):
    copy_project(tmp_path, fair=False)
    assert not (tmp_path / "CITATION.cff").exists()
    assert not (tmp_path / "REUSE.toml").exists()
    assert not (tmp_path / ".github" / "workflows" / "fair-software.yml").exists()
    assert not _renovate_mentions(tmp_path / "renovate.json", "howfairis"), "no FAIR rule without the FAIR workflow"


@pytest.mark.parametrize("restricted_license", ["Proprietary", "Confidential"])
def test_template_fair_restricted_license(tmp_path: Path, restricted_license: str):
    copy_project(tmp_path, fair=True, license=restricted_license)
    cff = (tmp_path / "CITATION.cff").read_text()
    assert "cff-version: 1.2.0" in cff
    # CFF has no SPDX expression for "all rights reserved": omit the field
    assert "license:" not in cff
    # reuse only applies to open-source licenses
    assert not (tmp_path / "REUSE.toml").exists()
    hygiene = (tmp_path / ".github" / "workflows" / "_hygiene.yml").read_text()
    assert "uvx cffconvert==2.0.0 --validate" in hygiene
    assert "fsfe/reuse-action@" in hygiene


def test_template_license_confidential(tmp_path: Path):
    copy_project(tmp_path, license="Confidential")
    license_text = (tmp_path / "LICENSE").read_text()
    assert "CONFIDENTIAL AND PROPRIETARY INFORMATION" in license_text
    assert "trade secrets" in license_text
    pyproject_toml = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert "license" not in pyproject_toml["project"]


def test_template_license_confidential_recommended_elsewhere(tmp_path: Path):
    # Opting out of just the license/FAIR gate should still leave every
    # other section (docs, quality, integrations, ...) on its recommended
    # default.
    copy_project_recommended(
        tmp_path,
        use_recommended_license=False,
        license="Confidential",
        fair=False,
    )
    license_text = (tmp_path / "LICENSE").read_text()
    assert "CONFIDENTIAL AND PROPRIETARY INFORMATION" in license_text
    assert not (tmp_path / "CITATION.cff").exists()


def test_template_changelog(tmp_path: Path):
    copy_project(tmp_path)
    assert (tmp_path / "CHANGELOG.md").exists()
    assert (tmp_path / "cliff.toml").exists()


def test_template_gitlab(tmp_path: Path):
    copy_project(tmp_path, git_platform="gitlab.com", gitlab_group="mygroup")
    assert (tmp_path / ".gitlab-ci.yml").exists()
    assert not (tmp_path / ".github").exists()
    # SECURITY.md / Scorecard are GitHub-only (private advisories + badge
    # both require github.com), so GitLab projects skip them.
    assert not (tmp_path / "SECURITY.md").exists()
    assert "SECURITY.md" not in (tmp_path / "README.md").read_text()


def test_template_security_policy_opt_out(tmp_path: Path):
    """use_recommended_security=false + security_policy=false drops SECURITY.md."""
    copy_project(tmp_path, use_recommended_security=False, security_policy=False, scorecard=False)
    assert not (tmp_path / "SECURITY.md").exists()
    assert "SECURITY.md" not in (tmp_path / "README.md").read_text()


def test_template_scorecard_opt_in(tmp_path: Path):
    """scorecard=true adds the Scorecard workflow + README badge."""
    copy_project(tmp_path, use_recommended_security=False, scorecard=True, security_policy=True)
    assert (tmp_path / "SECURITY.md").exists()
    assert (tmp_path / ".github" / "workflows" / "scorecard.yml").exists()
    readme = (tmp_path / "README.md").read_text()
    assert "api.scorecard.dev/projects/github.com/ConstitutiveTemplates/daimonion-example/badge" in readme


def test_template_readme_badges(tmp_path: Path):
    copy_project(tmp_path)  # example-answers.yml uses package_manager: uv
    readme = (tmp_path / "README.md").read_text()
    # only officially-documented tool badges: no unofficial/inferred ones
    # (e.g. uv, pixi have no official "used by" badge upstream)
    assert "astral-sh/ruff/main/assets/badge/v2.json" in readme
    assert "copier-org/copier/master/img/badge/badge-black.json" in readme
    # pre-commit is no longer shipped: its badge must not come back
    assert "pre--commit" not in readme
    assert "astral-sh/uv" not in readme
    assert "prefix-dev/pixi" not in readme
    assert "Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776AB" in readme


def test_pr_template_shipped(tmp_path: Path):
    copy_project(tmp_path)
    pr = tmp_path / ".github" / "PULL_REQUEST_TEMPLATE" / "pull_request_template.md"
    assert pr.exists()
    assert "Checks for reviewer" in pr.read_text()


@pytest.mark.heavy
@pytest.mark.network
def test_private_member_access(tmp_path: Path):
    code = """
class MyClass:
    def __init__(self):
        self.foo: int = 1
        self._bar: int = 2

obj = MyClass()
print(obj.foo)
print(obj._bar)
"""

    copy_project(tmp_path)
    run = make_venv(tmp_path)

    # Private member access should be allowed in tests
    test_file = tmp_path / "tests" / "test_private_access.py"
    with test_file.open("w") as stream:
        stream.write(code)
    run("ruff check")

    # Private member access should not be allowed in src
    src_file = tmp_path / "src" / "daimonion_example" / "private_access.py"
    with src_file.open("w") as stream:
        stream.write(code)
    with pytest.raises(AssertionError, match=r"private-member-access: Private member accessed: `_bar`"):
        run("ruff check")


@pytest.mark.heavy
@pytest.mark.network
def test_pep8_naming(tmp_path: Path):
    code = """
myVariable = "foo"
"""

    copy_project(tmp_path)
    run = make_venv(tmp_path)

    src_file = tmp_path / "src" / "daimonion_example" / "bad_example.py"
    with src_file.open("w") as stream:
        stream.write(code)
    with pytest.raises(AssertionError, match=r"mixed-case-variable-in-global-scope.*"):
        run("ruff check")


def test_basedpyright_works_in_none_typing_mode(tmp_path: Path):
    copy_project(tmp_path, strictness="none")
    pyproject = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    tasks = yaml.safe_load((tmp_path / "Taskfile.yml").read_text())["tasks"]

    # none: pytest + ruff (minimal rules) - no basedpyright, no type-checking env
    assert "basedpyright" not in pyproject["tool"]
    assert "ruff" in pyproject["tool"]
    assert "type-check" not in tasks


def test_basedpyright_works_in_basic_mode(tmp_path: Path):
    copy_project(tmp_path, strictness="basic")
    pyproject = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    tasks = yaml.safe_load((tmp_path / "Taskfile.yml").read_text())["tasks"]

    # basic: ruff but no type checking
    assert "ruff" in pyproject["tool"]
    assert "basedpyright" not in pyproject["tool"]
    assert "type-check" not in tasks


@pytest.mark.heavy
@pytest.mark.network
def test_basedpyright_works_with_external_deps(tmp_path: Path):
    copy_project(tmp_path)
    # Add an external dependency (regex insert -- log_library picks which
    # logging package, if any, already opens the `dependencies = [...]` array)
    pyproject_toml = tmp_path / "pyproject.toml"
    text = pyproject_toml.read_text()
    text, n = re.subn(r"dependencies = \[", 'dependencies = ["numpy", ', text, count=1)
    assert n == 1, "could not find dependencies array in generated pyproject.toml"
    pyproject_toml.write_text(text)
    # And some code that uses it
    src_file = tmp_path / "src" / "daimonion_example" / "example.py"
    src_file.write_text("""
import numpy as np

def is_big(arr: np.ndarray) -> bool:
    return arr.size > 0
""")
    # Ensure basedpyright is still happy
    run = make_venv(tmp_path)
    run("uvx --from go-task-bin task type-check")


def test_audit_isolated_from_type_check(tmp_path: Path):
    # pip-audit is network-dependent (OSV/PyPI): on-demand `audit` task,
    # never inside type-check/check so offline CI stays green.
    copy_project(tmp_path)
    tasks = yaml.safe_load((tmp_path / "Taskfile.yml").read_text())["tasks"]
    assert any("pip-audit" in str(command) for command in tasks["audit"]["cmds"])
    assert not any("pip-audit" in str(command) for command in tasks["type-check"]["cmds"]), (
        "type-check must stay runnable offline"
    )


def test_full_strictness_mode(tmp_path: Path):
    copy_project(tmp_path, strictness="full")

    # Check strict mode with Any-reporting is configured
    basedpyright = tomllib.loads((tmp_path / "pyproject.toml").read_text())["tool"]["basedpyright"]
    assert basedpyright["typeCheckingMode"] == "strict"
    assert basedpyright["reportAny"] is True


@pytest.mark.heavy
@pytest.mark.network
def test_works_with_pydocstyle(tmp_path: Path):
    # Use English docstrings (allow_japanese=False) so ruff's D415
    # (punctuation check) applies cleanly.
    copy_project(tmp_path, allow_japanese=False)
    pyproject_toml = tmp_path / "pyproject.toml"
    text = (
        pyproject_toml.read_text()
        .replace('"C4",', '"C4", "D",')  # Enable all pydocstyle
        .replace(
            '"tests/**/*" = [',
            '"tests/**/*" = [\n    "D",',
        )
    )
    # Add __init__.py as a separate key at the end of the per-file-ignores table
    text += '\n"__init__.py" = ["D104"]\n'
    pyproject_toml.write_text(text)

    # Ensure ruff is still happy
    run = make_venv(tmp_path)
    run("ruff check")


@pytest.mark.parametrize(
    "override",
    [
        {},
        {"docker": True},
        {"docker": True, "docker_debug": True},
        {"pypi": True},
        {"docs_type": "sphinx"},
        {"docs_type": "zensical"},
        {"docs_type": "great-docs"},
        {"package_manager": "pixi"},
    ],
)
def test_renovate_actions_match_what_is_shipped(override: dict[str, Any], tmp_path: Path):
    # Generate a project with the given answers
    answers: dict[str, Any] = {
        "docker": False,
        "docker_debug": False,
        "pypi": False,
        "docs_type": "README",
    }
    answers.update(override)
    copy_project(tmp_path, **answers)
    # Find the GitHub actions ignored by renovate (all github-actions
    # packageRules now that they are split per category, not one block)
    renovate_config_path = tmp_path / "renovate.json"
    renovate_config = json.loads(renovate_config_path.read_text())
    config_github_actions = set()
    for rule in renovate_config["packageRules"]:
        if rule.get("matchManagers") == ["github-actions"]:
            config_github_actions.update(rule.get("matchPackageNames", []))
    used_github_actions = set[str]()
    workflow_files = list((tmp_path / ".github" / "workflows").glob("*.yml"))
    # The reusable workflows' shared setup lives in a composite action (TODO
    # archive §19); renovate's github-actions manager extracts from
    # .github/actions/**/action.yml too, so the scanner must as well.
    workflow_files += list((tmp_path / ".github" / "actions").rglob("action.yml"))
    for workflow_file in workflow_files:
        workflow = yaml.safe_load(workflow_file.read_text())
        # Workflows keep steps under jobs.<id>.steps; composite actions under
        # runs.steps.
        step_lists = [job.get("steps", []) for job in workflow.get("jobs", {}).values()]
        if "runs" in workflow:
            step_lists.append(workflow["runs"].get("steps", []))
        for steps in step_lists:
            for step in steps:
                action = step.get("uses")
                # Local references (the setup-runner composite, the reusable
                # _*.yml workflows) are not third-party: renovate skips them.
                if action and not action.startswith("./"):
                    name = action.split("@")[0]
                    # docker:// steps track the bare image name in renovate
                    name = name.removeprefix("docker://")
                    used_github_actions.add(name)
    # Check they match
    assert used_github_actions == config_github_actions


def test_python_versions_match(tmp_path: Path):
    copy_project(tmp_path)
    # Grab the python versions from ci.yml
    ci_yaml = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow = yaml.safe_load(ci_yaml.read_text())
    python_versions = workflow["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    # Check .python-version is the first of these
    python_version_file = tmp_path / ".python-version"
    min_version = python_version_file.read_text().strip()
    assert python_versions[0] == min_version
    # Check pyproject.toml has correct requires-python and classifiers
    pyproject_toml = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert pyproject_toml["project"]["requires-python"] == f">={min_version}"
    for version in python_versions:
        assert f"Programming Language :: Python :: {version}" in pyproject_toml["project"]["classifiers"]


def _audit_workflow_shape(text: str) -> dict:
    """The contract a generated audit.yml must satisfy (mirrors the
    template-update shape assertion above)."""
    assert "{%" not in text.replace("{% raw %}", ""), "unrendered Jinja left in audit.yml"
    workflow = yaml.safe_load(text)
    assert workflow.get("permissions") == {"contents": "read"}, (
        f"top-level must be read-only, got {workflow.get('permissions')}"
    )
    triggers = workflow.get("on", workflow.get(True))
    assert triggers is not None, "the workflow needs an `on:` block"
    assert "workflow_dispatch" in triggers, "manual dispatch required"
    assert triggers["schedule"] == [{"cron": "0 4 * * SUN"}], (
        f"weekly Sunday 04:00 UTC schedule required, got {triggers.get('schedule')}"
    )
    assert "audit" in workflow["jobs"], "audit job missing"
    return workflow


def test_audit_workflow_dispatches_through_the_task_runner(tmp_path: Path):
    """The default render ships a weekly audit that runs the `audit` task
    through the project's task runner (the ci.yml dispatch pattern)."""
    copy_project(tmp_path, project_type="cli")
    path = tmp_path / ".github" / "workflows" / "audit.yml"
    assert path.exists(), "github_actions must ship the audit workflow"
    workflow = _audit_workflow_shape(path.read_text())
    job = workflow["jobs"]["audit"]
    assert job["uses"] == "./.github/workflows/_tasks.yml", (
        "the audit must dispatch through the shared _tasks.yml reusable workflow"
    )
    assert job["with"]["task"] == "audit", "the reusable call must run the audit task"
    assert job["with"]["task_runner"] == "task", "the reusable call must use this render's task runner"
    assert "schedule" in str(workflow.get("on", workflow.get(True)))


def test_audit_workflow_skips_without_an_audit_task(tmp_path: Path):
    """Configurations without an `audit` task (ros2, none/basic strictness)
    keep a valid workflow that skips with a notice instead of calling a task
    that does not exist."""
    bare = tmp_path / "bare"
    copy_project(bare, project_type="cli", strictness="none")
    workflow = _audit_workflow_shape((bare / ".github" / "workflows" / "audit.yml").read_text())
    runs = " ".join(str(step.get("run", "")) for step in workflow["jobs"]["audit"]["steps"])
    assert "::notice::" in runs, "the skip branch must explain itself with a notice"
    assert "_tasks.yml" not in (bare / ".github" / "workflows" / "audit.yml").read_text()

    ros2 = tmp_path / "ros2"
    copy_project(ros2, project_type="ros2")
    workflow = _audit_workflow_shape((ros2 / ".github" / "workflows" / "audit.yml").read_text())
    runs = " ".join(str(step.get("run", "")) for step in workflow["jobs"]["audit"]["steps"])
    assert "::notice::" in runs, "the ros2 branch must skip: _tasks.yml does not ship there"


def test_audit_workflow_absent_without_github_actions(tmp_path: Path):
    """ci_provider=none and GitLab renders ship no audit workflow (the
    workflows directory itself is github_actions-only)."""
    no_ci = tmp_path / "no-ci"
    copy_project(no_ci, ci_provider="none")
    assert not (no_ci / ".github" / "workflows" / "audit.yml").exists()
    gitlab = tmp_path / "gitlab"
    copy_project(gitlab, git_platform="gitlab.com", gitlab_group="mygroup")
    assert not (gitlab / ".github").exists()


@pytest.mark.parametrize(
    ("answers", "present", "absent"),
    [
        ({"package_manager": "uv"}, "uv sync", "poetry install"),
        ({"package_manager": "poetry"}, "poetry install", "uv sync"),
        ({"package_manager": "pixi", "task_runner_pixi": "pixi"}, "pixi install", "uv sync"),
    ],
)
def test_installation_tutorial_follows_the_package_manager(
    tmp_path: Path, answers: dict[str, Any], present: str, absent: str
):
    """docs/tutorials/installation.md renders the branch of its own package
    manager (the README Development-setup branches), not a venv+pip hardcode."""
    copy_project(tmp_path, project_type="cli", **answers)
    text = (tmp_path / "docs" / "tutorials" / "installation.md").read_text()
    assert present in text, f"expected the {answers['package_manager']} branch in installation.md"
    assert absent not in text, f"the {answers['package_manager']} render must not carry {absent!r}"
    assert "python3 -m venv" not in text, "the venv hardcode is replaced by the package-manager branches"


def test_readme_first_run_uses_the_task_runner(tmp_path: Path):
    """The README First-run block drives lint/test/check through the render's
    task runner (pixi renders spell the native `pixi run -e dev` prefix)."""
    copy_project(tmp_path, project_type="cli")
    readme = (tmp_path / "README.md").read_text()
    assert "### First run" in readme
    first_run = readme.split("### First run")[1].split("###")[0]
    assert "task lint" in first_run and "task test" in first_run and "task check" in first_run

    pixi = tmp_path / "pixi"
    copy_project(pixi, project_type="cli", package_manager="pixi", task_runner_pixi="pixi")
    first_run = (pixi / "README.md").read_text().split("### First run")[1].split("###")[0]
    assert "pixi run -e dev lint" in first_run, "pixi renders must use the native task prefix"


def test_readme_hides_type_check_below_recommended_strictness(tmp_path: Path):
    """At none/basic strictness the runner table must not list `type-check`
    (the task does not exist there); recommended keeps it."""
    bare = tmp_path / "bare"
    copy_project(bare, project_type="cli", strictness="none")
    table = (bare / "README.md").read_text().split("### Lint, type-check and test")[1].split("### First run")[0]
    assert "type-check" not in table, "none strictness ships no type-check task, so the table must not list it"

    recommended = tmp_path / "recommended"
    copy_project(recommended, project_type="cli")
    table = (recommended / "README.md").read_text().split("### Lint, type-check and test")[1].split("### First run")[0]
    assert "task type-check" in table, "recommended strictness keeps the type-check row"


def test_derived_toolchain_flags_match_the_answers_they_rename():
    """The _internal.yml shorthands resolve exactly like the literals they
    replace (the byte-identical-render precondition for the R1 renames)."""
    from copier._main import Worker
    from tools.answers import BASE  # noqa: E402

    with tempfile.TemporaryDirectory() as dst:
        worker = Worker(src_path=str(TOP), dst_path=Path(dst), defaults=True, quiet=True, vcs_ref="HEAD")
        cases = [
            (
                {"use_recommended_toolchain": False, "package_manager": "uv"},
                {"is_uv": True, "is_poetry": False, "is_pixi": False, "runner_just": True, "runner_task": False},
            ),
            (
                {"use_recommended_toolchain": False, "package_manager": "poetry"},
                {"is_uv": False, "is_poetry": True, "is_pixi": False, "runner_just": True, "runner_task": False},
            ),
            (
                {"use_recommended_toolchain": False, "package_manager": "pixi", "task_runner_pixi": "pixi"},
                {"is_uv": False, "is_poetry": False, "is_pixi": True, "runner_just": False, "runner_task": False},
            ),
            (
                {"use_recommended_toolchain": False, "package_manager": "uv", "task_runner": "task"},
                {"is_uv": True, "is_poetry": False, "is_pixi": False, "runner_just": False, "runner_task": True},
            ),
        ]
        for answers, expected in cases:
            worker.data = {**BASE, "project_type": "cli", **answers}
            worker._ask()  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
            context = worker._render_context()  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
            for flag, value in expected.items():
                assert context.get(flag) is value, f"{answers}: {flag} resolved to {context.get(flag)!r}"
            assert context.get("strictness_minimal") is False, "default answers ride recommended strictness"

        worker.data = {**BASE, "project_type": "cli", "use_recommended_quality": False, "strictness": "none"}
        worker._ask()  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
        context = worker._render_context()  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
        assert context.get("strictness_minimal") is True
