"""Tests for tools/mcp_server.py: the tooling exposed over MCP.

The in-process client below is the same pattern the generated MCP scaffold
ships in its own tests (`mcp.Client` against the server object, no
subprocess, no port), so this file also documents how to call the server from
your own code. The HTTP tests at the end go the other way: they launch
`tools/mcp_server.py` for real, so the Host allowlist and /health are checked
by a running server rather than by a mock of it.
"""

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from typing import cast

import pytest
import yaml
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import LATEST_PROTOCOL_VERSION
from mcp.types import TextContent
from mcp.types import TextResourceContents

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import answers  # noqa: E402
from tools import answers_for  # noqa: E402
from tools import mcp_server  # noqa: E402

# The shared Project Details (tools/answers.py) with this tool's own package
# name; repo_name/distribution_name are copier's derivation, not restated here.
BASE_ANSWERS = {**answers.BASE, "package_name": "mcp_example"}

TOOL_NAMES = {
    "adopt_project",
    "check_ethics",
    "explain_choice",
    "inspect_project",
    "lint_render",
    "list_batch_requests",
    "list_questions",
    "list_presets",
    "list_witnesses",
    "recommend_answers",
    "render_diff",
    "render_project",
    "run_batch",
    "run_tests",
    "run_witness",
    "suggest_config",
    "validate_answers",
    "template_fingerprint",
    "template_status",
}

# The convention docs/how-to/test-loop.md states: the docstring is the tool
# description the model reads, so it says what the call costs and what comes
# back. The cost half is checked as a vocabulary rather than a phrase: any of
# these words names a price the caller pays (a render, an install, the
# network, ...).
COST_WORDS = ("render", "network", "venv", "install", "filesystem", "hashes", "shells")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[Client]:
    async with Client(mcp_server.server, raise_exceptions=True) as c:
        yield c


async def call(client: Client, name: str, arguments: dict | None = None) -> Any:
    result = await client.call_tool(name, arguments or {})
    assert result.is_error is False, result.content
    assert isinstance(result.content[0], TextContent)
    return json.loads(result.content[0].text)


@pytest.mark.anyio
async def test_every_tool_is_registered_with_a_description(client: Client):
    """A tool without a docstring is a tool the model cannot choose."""
    tools = (await client.list_tools()).tools
    assert {tool.name for tool in tools} == TOOL_NAMES
    for tool in tools:
        assert tool.description, f"{tool.name} needs a docstring (it is the tool description)"


@pytest.mark.anyio
async def test_every_tool_description_states_its_cost_and_return_shape(client: Client):
    """test-loop.md's rule, enforced: a description that hides the cost is how
    a model picks a two-minute render when it wanted a file listing."""
    for tool in (await client.list_tools()).tools:
        description = (tool.description or "").lower()
        assert re.search(r"\breturns?\b", description), f"{tool.name} must say what it returns"
        assert any(word in description for word in COST_WORDS), f"{tool.name} must say what it costs"


@pytest.mark.anyio
async def test_list_questions_filters_internal_variables(client: Client):
    asked = (await call(client, "list_questions"))["questions"]
    everything = (await call(client, "list_questions", {"asked_only": False}))["questions"]
    assert len(everything) > len(asked)
    assert all(entry["internal"] is False for entry in asked)
    # the filter drops the derived variables, and the payload still describes
    # the entries it keeps
    assert "micropython_pkg" not in {entry["name"] for entry in asked}
    assert "micropython_pkg" in {entry["name"] for entry in everything}
    assert asked[0]["name"] == "project_type"
    assert {"help", "default"} <= asked[0].keys()


@pytest.mark.anyio
async def test_questionnaire_resource(client: Client):
    result = await client.read_resource("template://questionnaire")
    assert isinstance(result.contents[0], TextResourceContents)
    payload = json.loads(result.contents[0].text)
    everything = (await call(client, "list_questions", {"asked_only": False}))["questions"]
    assert payload["questions"] == everything, "the resource serves the same questionnaire as the tool"
    assert payload["questions"][0]["name"] == "project_type"


@pytest.mark.anyio
async def test_template_status_reports_the_checkout(client: Client):
    status = await call(client, "template_status")
    assert isinstance(status, dict)
    everything = (await call(client, "list_questions", {"asked_only": False}))["questions"]
    assert status["questions"] == len(everything), "the status counts the questionnaire the tools serve"
    assert status["asked_questions"] < status["questions"]
    assert isinstance(status["dirty"], bool)
    assert status["latest_tag"], "the checkout has tags; the trap is that they are stale"
    assert mcp_server.template_status()["repo"] == str(TOP), "the plain function is the same call"


@pytest.mark.anyio
async def test_inspect_project_reports_mode_and_collisions(client: Client, tmp_path: Path):
    (tmp_path / "src" / "legacy").mkdir(parents=True)
    (tmp_path / "src" / "legacy" / "__init__.py").write_text("")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "legacy"\ndescription = "legacy"\n')
    (tmp_path / "README.md").write_text("# mine\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("# mine\n")

    detection = await call(client, "inspect_project", {"path": str(tmp_path)})
    assert isinstance(detection, dict)
    assert detection["mode"] == "adopt"
    assert detection["suggested_answers"]["existing_project"] is True
    assert detection["suggested_answers"]["package_name"] == "legacy"
    assert ".github/workflows/ci.yml" in detection["collisions"]
    assert "README.md" in detection["kept"]
    assert mcp_server.inspect_project(str(tmp_path))["mode"] == "adopt"


@pytest.mark.anyio
async def test_inspect_project_reports_a_foreign_template(client: Client, tmp_path: Path):
    (tmp_path / ".copier-answers.yml").write_text("_src_path: https://github.com/other/template.git\n")
    detection = await call(client, "inspect_project", {"path": str(tmp_path)})
    assert detection["mode"] == "foreign"
    assert detection["foreign_src"] == "https://github.com/other/template.git"
    taken = await call(client, "inspect_project", {"path": str(tmp_path), "takeover": True})
    assert taken["mode"] == "adopt" and taken["took_over"] is True


@pytest.mark.anyio
async def test_render_project_keeps_stdout_clean(client: Client, tmp_path: Path, capfd: pytest.CaptureFixture[str]):
    """A stdio MCP server's stdout is the protocol channel: copier's chatter
    must land on stderr, which is what report_stream_only() guarantees."""
    dest = tmp_path / "rendered"
    result = await call(
        client,
        "render_project",
        {"answers": {**BASE_ANSWERS, "project_type": "script"}, "dest": str(dest)},
    )
    assert isinstance(result, dict)
    assert result["dest"] == str(dest)
    paths = {entry["path"] for entry in result["files"]}
    assert "pyproject.toml" in paths
    assert "README.md" in paths
    assert result["file_count"] == len(result["files"])

    captured = capfd.readouterr()
    assert captured.out == "", "rendering wrote to stdout, which would corrupt the MCP session"
    assert (dest / "pyproject.toml").is_file()


@pytest.mark.anyio
async def test_render_project_files_carry_digests_and_can_diff_against(client: Client, tmp_path: Path):
    """The payload feeds a regression check: per-file sha256, and diff_against
    names a previous render to compare against (render_diff's shape, one
    render). The answers file's per-render stamps are masked, so two renders
    of the same answers diff clean."""
    first_dest = tmp_path / "first"
    first = await call(
        client,
        "render_project",
        {"answers": {**BASE_ANSWERS, "project_type": "script"}, "dest": str(first_dest)},
    )
    digests = {entry["path"]: entry["sha256"] for entry in first["files"]}
    pyproject = first_dest / "pyproject.toml"
    assert digests["pyproject.toml"] == hashlib.sha256(pyproject.read_bytes()).hexdigest()

    second_dest = tmp_path / "second"
    second = await call(
        client,
        "render_project",
        {
            "answers": {**BASE_ANSWERS, "project_type": "script"},
            "dest": str(second_dest),
            "diff_against": str(first_dest),
        },
    )
    diff = second["diff"]
    assert diff["changed"] == [], "two renders of the same answers are identical modulo the stamps"
    assert diff["same_count"] == len(second["files"])
    assert diff["only_in_a"] == [] and diff["only_in_b"] == []

    moved = await call(
        client,
        "render_project",
        {
            # A data-supplied value applies even when its question's `when`
            # hides it (tests/test_generated_lint.py's JAPANESE_VARIANTS
            # precedent), so this flips the generated [tool.ruff] width.
            "answers": {**BASE_ANSWERS, "project_type": "script", "allow_japanese": True},
            "dest": str(tmp_path / "third"),
            "diff_against": str(first_dest),
        },
    )
    moved_diff = moved["diff"]
    assert moved_diff["same_count"] < len(moved["files"]), "an answer change must move at least one file"

    # The refusal happens before any render, so a direct call is enough
    # (the client wraps ToolErrors in is_error results; see the tier tests).
    with pytest.raises(ToolError, match="diff_against is not a directory"):
        mcp_server.render_project({"project_type": "script"}, diff_against=str(tmp_path / "gone"))


@pytest.mark.anyio
async def test_adopt_project_plans_then_applies(client: Client, tmp_path: Path):
    """dry_run plans without writing; applying keeps the adopter's files."""
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("# MY OWN CI\n")
    (tmp_path / "README.md").write_text("# mine\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "legacy"\nversion = "0"\n')

    plan = await call(client, "adopt_project", {"path": str(tmp_path), "ref": "HEAD"})
    assert plan["ok"] and plan["applied"] is False
    assert plan["skip"] == [".github/workflows/ci.yml"]
    assert plan["deps"]["added"]["dev"], "the plan includes the dependency merge"
    assert plan["tool_config"]["added"], "and the tool-config merge"
    assert (tmp_path / "README.md").read_text() == "# mine\n"

    applied = await call(client, "adopt_project", {"path": str(tmp_path), "ref": "HEAD", "dry_run": False})
    assert applied["ok"] and applied["applied"] is True
    assert applied["created_count"] > 0
    assert (tmp_path / ".github" / "workflows" / "ci.yml").read_text() == "# MY OWN CI\n"
    assert (tmp_path / "README.md").read_text() == "# mine\n"
    assert (tmp_path / ".gitleaks.toml").exists()
    assert "dependency-groups" in tomllib.loads((tmp_path / "pyproject.toml").read_text())


@pytest.mark.anyio
async def test_adopt_project_refuses_a_foreign_template(client: Client, tmp_path: Path):
    (tmp_path / ".copier-answers.yml").write_text("_src_path: https://github.com/other/template.git\n")
    result = await client.call_tool("adopt_project", {"path": str(tmp_path)})
    assert result.is_error is True
    assert "https://github.com/other/template.git" in str(result.content), "the error names the owning template"


@pytest.mark.anyio
async def test_run_batch_reports_a_verdict(client: Client, tmp_path: Path):
    jsonl = tmp_path / "requests.jsonl"
    jsonl.write_text(
        json.dumps(
            {
                "id": "script-case",
                "answers": {**BASE_ANSWERS, "project_type": "script"},
                "expect": {"files": ["mcp_example/__init__.py"], "absent": ["src"]},
            }
        )
        + "\n"
    )
    verdict = await call(client, "run_batch", {"jsonl": str(jsonl)})
    assert isinstance(verdict, dict)
    assert verdict["ok"] is True
    assert [line["id"] for line in verdict["lines"]] == ["script-case"]
    assert verdict["lines"][0]["checks"][0]["name"] == "render"


@pytest.mark.anyio
async def test_list_batch_requests_reads_the_shipped_batch(client: Client):
    requests = (await call(client, "list_batch_requests", {"jsonl": str(TOP / "batches" / "smoke.jsonl")}))["requests"]
    assert requests, "the shipped batch lists its requests"
    assert any(request["has_update"] for request in requests), "the listing reports the update phase"


@pytest.mark.anyio
async def test_list_presets_names_the_files_and_their_answers(client: Client):
    """The listing mirrors presets/ exactly: every file on disk, with the
    answer mapping the CLI would pass to copier for it."""
    payload = await call(client, "list_presets")
    names = {preset["name"] for preset in payload["presets"]}
    assert names == {path.stem for path in (TOP / "presets").glob("*.yml")}
    by_name = {preset["name"]: preset["answers"] for preset in payload["presets"]}
    assert by_name["library"] == {"project_type": "library"}
    assert by_name["online-judge-atcoder"]["oj_kind"] == "atcoder"


@pytest.mark.anyio
async def test_explain_choice_covers_preset_question_and_deviation(client: Client):
    """The explain tool answers from the questionnaire's own words, filesystem only."""
    preset = await call(client, "explain_choice", {"preset": "web-api"})
    assert "project_type = 'web_api'" in preset["explanation"]
    answer = await call(client, "explain_choice", {"question": "project_type", "value": "cli"})
    assert "project_type" in answer["explanation"]
    deviated = await call(client, "explain_choice", {"deviate_question": "project_type", "deviate_value": "cli"})
    assert "include_scraping" in deviated["explanation"]


@pytest.mark.anyio
async def test_explain_choice_rejects_bad_input(client: Client):
    """Unknown names and empty calls are tool errors, not empty explanations."""
    result = await client.call_tool("explain_choice", {"preset": "no-such-preset"})
    assert result.is_error is True
    result = await client.call_tool("explain_choice", {})
    assert result.is_error is True


@pytest.mark.anyio
async def test_suggest_config_ranks_web_api_first_for_api(client: Client):
    """The assistant's first step: requirement words in, preset candidates out."""
    payload = await call(client, "suggest_config", {"requirements": "internal API, postgres, github actions"})
    assert payload["matches"], "the acceptance requirements match nothing"
    assert payload["matches"][0]["preset"] == "web-api"
    assert payload["matches"][0]["answers"]["project_type"] == "web_api"


@pytest.mark.anyio
async def test_validate_answers_accepts_and_rejects(client: Client):
    """Approved sets pass; an unknown question is refused with its reason."""
    approved = await call(client, "validate_answers", {"answers": {"project_type": "web_api"}})
    assert approved == {"ok": True, "errors": []}
    refused = await call(client, "validate_answers", {"answers": {"project_type": "web_api", "unknown_q": 1}})
    assert refused["ok"] is False
    by_question = {error["question"]: error["reason"] for error in refused["errors"]}
    assert "unknown_q" in by_question and "unknown question" in by_question["unknown_q"]


@pytest.mark.anyio
async def test_bad_input_is_a_tool_error(client: Client):
    result = await client.call_tool("list_batch_requests", {"jsonl": "/nonexistent/requests.jsonl"})
    assert result.is_error is True
    assert "/nonexistent/requests.jsonl" in str(result.content), "the error names the file it could not read"


# --------------------------------------------------------------------------- #
# the render loop: render_diff / lint_render
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_render_diff_compares_two_renders_file_by_file(client: Client):
    """The audit compared 1684 rendered files by hand; this is that comparison."""
    script = {**BASE_ANSWERS, "project_type": "script"}
    diff = await call(
        client, "render_diff", {"answers_a": script, "answers_b": {**BASE_ANSWERS, "project_type": "cli"}}
    )

    assert diff["identical"] is False
    changed = {entry["path"]: entry for entry in diff["changed"]}
    assert "pyproject.toml" in changed, "the project type reaches pyproject.toml"
    entry = changed["pyproject.toml"]
    assert entry["sha256_a"] != entry["sha256_b"] and entry["bytes_a"] != entry["bytes_b"]
    assert entry["diff"], "a changed file carries its unified diff"
    assert entry["diff"].startswith("--- a/pyproject.toml")
    # the two layouts differ in where the package lives, which is a file-set
    # difference, not a content one
    assert diff["only_in_a"] == ["mcp_example/__init__.py", "mcp_example/__main__.py", "mcp_example/logging_setup.py"]
    assert diff["only_in_b"] == [f"src/{name}" for name in diff["only_in_a"]]
    assert diff["identical_count"] + diff["changed_count"] + len(diff["only_in_a"]) == diff["file_count"]["a"]
    assert diff["identical_count"] + diff["changed_count"] + len(diff["only_in_b"]) == diff["file_count"]["b"]
    assert diff["dest_a"] is None, "a temp render is reported only when keep=True"

    # copier's own checkout stamp is reported next to the comparison, not
    # inside it: for a dirty template the two renders carry different
    # synthetic commits, and that difference says nothing about the answers
    assert diff["answers_commit"]["a"] and diff["answers_commit"]["b"]
    assert "-project_type: script" in changed[".copier-answers.yml"]["diff"], "the answer change is what shows"


@pytest.mark.anyio
async def test_render_diff_accepts_an_identical_pair(client: Client):
    """What "the change is inert" looks like: no changed path on either side.

    The same answers twice. The one file a *dirty* template renders
    differently per render is `.copier-answers.yml`, whose `_commit` records
    the synthetic commit copier makes for the working tree -- so this verdict
    holds only because `render_diff` reports that stamp instead of comparing
    it (see `answers_commit`).
    """
    answers = {**BASE_ANSWERS, "project_type": "script"}
    diff = await call(client, "render_diff", {"answers_a": answers, "answers_b": dict(answers), "keep": True})
    assert diff["identical"] is True
    assert diff["changed"] == [] and diff["only_in_a"] == [] and diff["only_in_b"] == []
    assert diff["identical_count"] == diff["file_count"]["a"] == diff["file_count"]["b"]

    for side, answers_file in (("a", diff["dest_a"]), ("b", diff["dest_b"])):
        recorded = re.search(
            r"^_commit: (\S+)$", (Path(answers_file) / ".copier-answers.yml").read_text(), re.MULTILINE
        )
        assert recorded is not None, "copier stamps the render it was taken from"
        assert diff["answers_commit"][side] == recorded.group(1), "the stamp is reported, not compared"


@pytest.mark.anyio
async def test_lint_render_runs_the_generated_lint(client: Client):
    """test_generated_lint's fast tier, as one call: render, then ruff."""
    verdict = await call(client, "lint_render", {"answers": {**BASE_ANSWERS, "project_type": "script"}})
    assert verdict["ok"] is True
    assert verdict["checked"] is True
    assert [check["name"] for check in verdict["checks"]] == ["ruff format --check", "ruff check"]
    assert [check["detail"] for check in verdict["checks"]] == ["", ""], "a passing check carries ruff's silence"
    assert (Path(verdict["dest"]) / "pyproject.toml").is_file(), "the destination is the rendered project"


# --------------------------------------------------------------------------- #
# the witness ledger
# --------------------------------------------------------------------------- #


def _declared_witness_ids() -> list[str]:
    """The ledger's own declaration order, straight from the JSONL."""
    return [json.loads(line)["id"] for line in (TOP / "tests" / "matrix" / "witnesses.jsonl").read_text().splitlines()]


@pytest.mark.anyio
async def test_list_witnesses_reports_the_leaves_and_their_verdicts(client: Client):
    listed = await call(client, "list_witnesses")
    declared = _declared_witness_ids()
    assert listed["total"] == len(declared) == len(listed["leaves"])
    assert [leaf["id"] for leaf in listed["leaves"]] == declared
    assert sum(listed["tiers"].values()) == listed["total"]
    assert sum(listed["results"].values()) == listed["total"]
    assert listed["coverage"]["total"] == listed["total"], "the coverage block is the committed ledger's"
    assert set(listed["tiers"]) <= {"fast", "full"}, "a recorded tier, not a guess"


@pytest.mark.anyio
async def test_witnesses_resource_serves_the_same_inventory(client: Client):
    first = await client.read_resource("template://witnesses")
    assert isinstance(first.contents[0], TextResourceContents)
    assert json.loads(first.contents[0].text) == await call(client, "list_witnesses")
    second = await client.read_resource("template://witnesses")
    assert isinstance(second.contents[0], TextResourceContents)
    assert first.contents[0].text == second.contents[0].text, "the payload is deterministic"


@pytest.mark.anyio
async def test_recommend_answers_finds_the_leaves_and_refuses_unknown_names(
    client: Client, monkeypatch: pytest.MonkeyPatch
):
    """The inverse template on the MCP surface, over crafted contexts (no copier pass)."""
    contexts = {
        "project_type=cli/gate=off:use_recommended_agent": {"project_type": "cli", "docs_type": "zensical"},
        "project_type=web_api/gate=off:use_recommended_agent": {"project_type": "web_api", "docs_type": "sphinx"},
    }
    monkeypatch.setattr(answers_for, "load_contexts", lambda root=None: contexts)
    payload = await call(client, "recommend_answers", {"constraints": ["project_type=cli"]})
    assert payload["matched"] == 1
    (leaf,) = payload["leaves"]
    assert leaf["id"] == "project_type=cli/gate=off:use_recommended_agent"
    assert yaml.safe_load(leaf["answers_yaml"]) == leaf["answers"]
    assert leaf["ships"], "the ships list comes from the invariants matrix"
    no_match = await call(client, "recommend_answers", {"constraints": ["docs_type=zensical", "docs_type!=zensical"]})
    assert no_match["matched"] == 0 and no_match["diagnostic"]["nearest"]["of"] == 2
    bad = await client.call_tool("recommend_answers", {"constraints": ["doc_typ=zensical"]})
    assert bad.is_error is True and "docs_type" in str(bad.content), "the error suggests the closest real names"


@pytest.mark.anyio
async def test_support_resource_serves_the_declared_contract(client: Client):
    """The declaration the docs and the support tests read, on the MCP surface.

    The point of the resource is a caller asking "what has CI actually run?",
    so the payload must be the live `support.yml` and not a copy of it: every
    declared `supported` combination is cross-checked against the witness
    inventory the sibling tool reports.
    """
    result = await client.read_resource("template://support")
    assert isinstance(result.contents[0], TextResourceContents)
    payload = json.loads(result.contents[0].text)
    assert {"supported", "best_effort", "tier_policy"} <= set(payload)

    inventory = await call(client, "list_witnesses")
    recorded = {leaf["id"]: leaf for leaf in inventory["leaves"]}
    declared = {str(row["combination"]) for row in payload["supported"]}
    assert declared <= set(recorded), f"declared but not a witness leaf: {sorted(declared - set(recorded))}"
    assert all(recorded[leaf]["tier"] == "full" for leaf in declared), "a supported combination is a full-tier leaf"

    second = await client.read_resource("template://support")
    assert isinstance(second.contents[0], TextResourceContents)
    assert second.contents[0].text == result.contents[0].text, "the payload is deterministic"


@pytest.mark.anyio
async def test_ethics_resource_serves_the_registry(client: Client):
    """The rule registry on the MCP surface, deterministic, every row armed.

    A row without its documented presence trigger would silently vanish from
    `check_ethics` matches, so the resource payload is held to carry one per
    row (the same contract tests/test_ethics_registry.py pins on the files).
    """
    result = await client.read_resource("template://ethics")
    assert isinstance(result.contents[0], TextResourceContents)
    payload = json.loads(result.contents[0].text)
    assert payload["count"] == len(payload["sections"]) >= 10
    for row in payload["sections"]:
        assert row["trigger"].startswith("(?i)"), f"{row['id']}: missing presence trigger"
        assert {"id", "status", "enforcement", "scale", "audience", "review_by"} <= set(row)

    second = await client.read_resource("template://ethics")
    assert isinstance(second.contents[0], TextResourceContents)
    assert second.contents[0].text == result.contents[0].text, "the payload is deterministic"


@pytest.mark.anyio
async def test_check_ethics_matches_triggers_and_ranks_gates_first(client: Client):
    """Denylist identifiers warn even while draft; the L2 gate sorts first."""
    report = await call(
        client, "check_ethics", {"text": "server 133.100.9.2  # NTP, then: pip install terraform  # BUSL"}
    )
    ids = [entry["id"] for entry in report["matched"]]
    assert "region-kyushu-ntp" in ids, "a retired NTP identifier must trip its section"
    assert "baseline-license-drift" in ids, "a BUSL mention must trip the license rule"
    ranked = [entry for entry in report["matched"] if entry["id"] in ("region-kyushu-ntp", "baseline-license-drift")]
    assert [entry["id"] for entry in ranked] == [
        "baseline-license-drift",
        "region-kyushu-ntp",
    ], "the L2 gate sorts before the L0 draft"
    gate = ranked[0]
    assert gate["enforcement"] == "L2"
    assert "ライセンス変動" in gate["body"], "the match carries the section body an agent can read"

    quiet = await call(client, "check_ethics", {"text": "a plain module with no rule triggers"})
    assert quiet == {"count": 0, "matched": []}


@pytest.mark.anyio
async def test_run_witness_returns_a_verdict_per_test(client: Client):
    """One leaf, so this pins the tool's pytest plumbing (~4s), not the suite."""
    verdict = await call(client, "run_witness", {"tier": "fast", "only": "ros2 and use_recommended_license"})
    assert verdict["ok"] is True
    assert verdict["counts"] == {"passed": 1, "failed": 0, "skipped": 0}
    assert [line["id"] for line in verdict["lines"]] == [
        "tests.test_witness_matrix::test_witness_render_invariants[project_type=ros2/gate=off:use_recommended_license]"
    ]
    assert verdict["lines"][0]["checks"] == [{"name": "pytest", "ok": True, "detail": ""}]
    assert verdict["output"] == ""
    assert verdict["command"][:3] == [sys.executable, "-m", "pytest"], "the verdict reports how to rerun it"


@pytest.mark.anyio
async def test_run_tests_returns_a_verdict_per_test(client: Client):
    """One selected test, so this pins the plumbing (~2s), not the tier.

    `-k` keeps the call inside the edit loop's budget; what it verifies is the
    wiring this tool exists for: the tier's marker expression comes from the
    ledger, pytest runs in a subprocess, and the verdict is per test rather
    than pytest's text.
    """
    verdict = await call(
        client, "run_tests", {"tier": "fast", "only": "test_batch_sample_base_is_the_shared_answer_set"}
    )
    assert verdict["ok"] is True, verdict["output"]
    assert verdict["counts"] == {"passed": 1, "failed": 0, "skipped": 0}
    assert verdict["command"][:3] == [sys.executable, "-m", "pytest"], "the verdict reports how to rerun it"
    assert "not heavy and not slow and not meta and not network" in verdict["command"], (
        "the expression is the ledger's fast row"
    )
    assert [line["ok"] for line in verdict["lines"]] == [True]
    assert verdict["lines"][0]["checks"], "a verdict carries at least one check"


@pytest.mark.anyio
async def test_run_tests_rejects_an_unknown_tier(client: Client):
    """The schema rejects it for a client; the plain function must too."""
    result = await client.call_tool("run_tests", {"tier": "turbo"})
    assert result.is_error is True
    assert "turbo" in str(result.content)
    with pytest.raises(ToolError):
        mcp_server.run_tests(cast("Any", "turbo"))


@pytest.mark.anyio
async def test_run_witness_rejects_an_unknown_tier(client: Client):
    """The schema rejects it for a client; the plain function must too."""
    result = await client.call_tool("run_witness", {"tier": "turbo"})
    assert result.is_error is True
    assert "turbo" in str(result.content)
    # the Literal in the schema is not something a plain function call enforces
    with pytest.raises(ToolError):
        mcp_server.run_witness(cast("Any", "turbo"))


# --------------------------------------------------------------------------- #
# the render fingerprint
# --------------------------------------------------------------------------- #


def test_template_fingerprint_hashes_the_render_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """The digest is a function of the render inputs and of nothing else."""
    (tmp_path / "template" / "pkg").mkdir(parents=True)
    (tmp_path / "template" / "pkg" / "mod.py.jinja").write_text("x = 1\n")
    (tmp_path / "template" / "README.md.jinja").write_text("# {{ repo_name }}\n")
    (tmp_path / "copier.yml").write_text("repo_name:\n  type: str\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# not a render input\n")
    monkeypatch.setattr(mcp_server, "TOP", tmp_path)

    first = mcp_server.template_fingerprint()
    assert first["inputs"] == {
        "dirs": ["template", "_shared"],
        "files": ["copier.yml", "_tasks.jinja"],
        "paths": 3,
        "bytes": len("x = 1\n") + len("# {{ repo_name }}\n") + len("repo_name:\n  type: str\n"),
    }
    assert first["fingerprint"] == mcp_server.template_fingerprint()["fingerprint"], "deterministic"
    assert len(first["fingerprint"]) == 64

    (tmp_path / "template" / "pkg" / "mod.py.jinja").write_text("x = 2\n")
    edited = mcp_server.template_fingerprint()
    assert edited["fingerprint"] != first["fingerprint"], "a nested source counts, not just the two root files"

    (tmp_path / "docs" / "guide.md").write_text("# edited\n")
    assert mcp_server.template_fingerprint()["fingerprint"] == edited["fingerprint"], "a non-input does not count"


def test_template_fingerprint_covers_this_checkout() -> None:
    """The real tree: every template source and partial, not just copier.yml."""
    reported = mcp_server.template_fingerprint()
    assert reported["inputs"]["paths"] > 200, "template/** files are inputs; a trailing-** glob yields directories only"
    assert reported["inputs"]["bytes"] > 100_000


# --------------------------------------------------------------------------- #
# the project-scope registration
# --------------------------------------------------------------------------- #


def test_mcp_json_registers_the_command_the_how_to_documents() -> None:
    """An agent editing the template gets the server with no setup: the
    registration and the page that explains it name the same command, and it
    points at a file that exists."""
    config = json.loads((TOP / ".mcp.json").read_text())
    entry = config["mcpServers"]["daimonion"]
    command = " ".join([entry["command"], *entry["args"]])

    assert command == "uv run --locked python tools/mcp_server.py", "the stdio command `task mcp` runs"
    assert (TOP / entry["args"][-1]).is_file(), "the registered script exists"
    assert "--transport" not in entry["args"], "a host launches stdio, the default"
    documented = (TOP / "docs" / "how-to" / "mcp-tools.md").read_text()
    assert command in documented, "the how-to documents the command it registers"


# --------------------------------------------------------------------------- #
# the HTTP transport: a real server, a real Host header
# --------------------------------------------------------------------------- #
#
# These launch tools/mcp_server.py (the same command `task mcp` runs) on a
# localhost port instead of mocking `_allowed_hosts`: a mock would only assert
# that the settings object was built, and the defect this guards against -- the
# SDK arming its DNS-rebinding protection only for a localhost bind, so a
# public server accepts every Host header -- only exists at the socket. No venv
# is built and nothing leaves 127.0.0.1, so the tests carry no cost marker.

SERVER = str(TOP / "tools" / "mcp_server.py")
ALLOWED_HOST = "mcp.example"
FOREIGN_HOST = "attacker.example"
ALLOWED_ORIGIN = "https://mcp.example"
FOREIGN_ORIGIN = "https://attacker.example"
MCP_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
INITIALIZE = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": LATEST_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "test_mcp_server", "version": "0"},
        },
    }
).encode()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _request(
    url: str, *, host: str, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None
) -> tuple[int, str]:
    """One HTTP request with the Host header this test chooses (urllib keeps it)."""
    request = urllib.request.Request(url, data=body, method=method, headers={"Host": host, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return int(response.status), response.read().decode()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode()


def _await_health(port: int, log: Path) -> None:
    """Wait for the server's own readiness signal, never for a sleep."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            status, _ = _request(f"http://127.0.0.1:{port}/health", host=f"127.0.0.1:{port}")
        except OSError:
            status = 0
        if status == 200:
            return
        time.sleep(0.1)
    pytest.fail(f"the server never answered /health on 127.0.0.1:{port}:\n{log.read_text()}")


@pytest.fixture
def allowed_server(tmp_path: Path) -> Iterator[tuple[int, Path]]:
    """The real entry point over HTTP: local bind, one allowed Host."""
    port = _free_port()
    log = tmp_path / "server.log"
    with log.open("w") as stream:
        proc = subprocess.Popen(
            [sys.executable, SERVER, "--transport", "streamable-http", "--host", "127.0.0.1", "--port", str(port)],
            cwd=TOP,
            env={
                **os.environ,
                "MCP_ALLOWED_HOSTS": ALLOWED_HOST,
                "MCP_ALLOWED_ORIGINS": ALLOWED_ORIGIN,
            },
            stdout=stream,
            stderr=stream,
            text=True,
        )
        try:
            _await_health(port, log)
            yield port, log
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover - a hung server, not a failed assertion
                proc.kill()
                proc.wait(timeout=10)


def test_non_local_bind_without_an_allowlist_refuses_to_start():
    """--host 0.0.0.0 with no MCP_ALLOWED_HOSTS: exit before the socket opens."""
    port = _free_port()
    env = {name: value for name, value in os.environ.items() if name != "MCP_ALLOWED_HOSTS"}
    proc = subprocess.run(
        [sys.executable, SERVER, "--transport", "streamable-http", "--host", "0.0.0.0", "--port", str(port)],
        cwd=TOP,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 2, proc.stderr
    assert "MCP_ALLOWED_HOSTS" in proc.stderr, "the refusal names the variable that would fix it"
    assert "error: " in proc.stderr
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=1)


def test_allowlist_refuses_a_foreign_host_but_serves_health(allowed_server: tuple[int, Path]):
    """The 421 is the protection; /health staying 200 is its documented scope."""
    port, log = allowed_server
    base = f"http://127.0.0.1:{port}"

    status, body = _request(f"{base}/health", host=FOREIGN_HOST)
    assert status == 200, f"/health is a custom route and bypasses the allowlist:\n{log.read_text()}"
    assert json.loads(body) == {"status": "ok"}

    status, body = _request(f"{base}/mcp", host=FOREIGN_HOST, method="POST", body=INITIALIZE, headers=MCP_HEADERS)
    assert status == 421, f"a foreign Host must not reach the tools:\n{body}\n{log.read_text()}"
    assert "Invalid Host header" in body

    status, body = _request(f"{base}/mcp", host=ALLOWED_HOST, method="POST", body=INITIALIZE, headers=MCP_HEADERS)
    assert status == 200, f"an allowed Host completes the handshake:\n{body}\n{log.read_text()}"
    assert "daimonion" in body, "the handshake reached this server's tool list"


def test_allowlist_enforces_the_origin_variable_too(allowed_server: tuple[int, Path]):
    """MCP_ALLOWED_ORIGINS is checked on the same endpoint, after the Host."""
    port, log = allowed_server
    base = f"http://127.0.0.1:{port}"
    headers = {**MCP_HEADERS, "Origin": FOREIGN_ORIGIN}

    status, body = _request(f"{base}/mcp", host=ALLOWED_HOST, method="POST", body=INITIALIZE, headers=headers)
    assert status == 403, f"a browser client from a foreign origin is refused:\n{body}\n{log.read_text()}"
    assert "Invalid Origin header" in body

    allowed = {**MCP_HEADERS, "Origin": ALLOWED_ORIGIN}
    status, body = _request(f"{base}/mcp", host=ALLOWED_HOST, method="POST", body=INITIALIZE, headers=allowed)
    assert status == 200, f"a listed origin is let through:\n{body}\n{log.read_text()}"

    status, _ = _request(f"{base}/mcp", host=ALLOWED_HOST, method="POST", body=INITIALIZE, headers=MCP_HEADERS)
    assert status == 200, "an absent Origin is same-origin by definition and stays allowed"
