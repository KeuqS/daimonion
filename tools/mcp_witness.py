#!/usr/bin/env python3
"""Witness and suite surface: leaves, inverse lookup, tier runners, resources.

Responsibility: the witness ledger (`list_witnesses`, `recommend_answers`,
`run_witness`), the repository's own suite tiers (`run_tests`), the pytest
plumbing both runners share (`_output_tail`, `_build_pytest_command`,
`_format_pytest_tier_result`, `_run_pytest_tier`), and the four read-only
resources (`template://questionnaire`, `template://witnesses`,
`template://support`, `template://ethics`). The tier tables
(`WITNESS_MARKERS`, `WITNESS_TIMEOUTS`, `TIER_TASKS`, `TIER_LEDGER`,
`TIER_TIMEOUTS`) live with the runners that read them.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any
from typing import Literal

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402
from tools import answers_for  # noqa: E402
from tools import batch  # noqa: E402
from tools import ethics  # noqa: E402
from tools import questionnaire  # noqa: E402
from tools import support_ledger  # noqa: E402
from tools.mcp_shared import OUTPUT_LIMIT  # noqa: E402
from tools.render_inputs import RENDER_INPUT_DIRS  # noqa: E402
from tools.render_inputs import RENDER_INPUT_FILES  # noqa: E402
from tools.render_inputs import render_fingerprint as _render_fingerprint  # noqa: E402

WITNESS_LIST = TOP / "tests" / "matrix" / "witnesses.jsonl"
"""The declared leaves: a JSONL request list, which batch.load_requests validates."""
WITNESS_LEDGER = TOP / "tests" / "matrix" / "witnesses.json"
"""The committed coverage artifact: per-leaf tier and result, plus the counters."""
WITNESS_TESTS = TOP / "tests" / "test_witness_matrix.py"
"""The suite that executes the leaves; run_witness shells out to it."""

WITNESS_MARKERS = {
    "fast": "not heavy and not slow",
    "slow": "slow",
    "full": "full",
}
"""Tier -> pytest marker expression (`--help`-style cost of each in run_witness)."""
WITNESS_TIMEOUTS = {"fast": 900, "slow": 900, "full": 7200}
"""Per-tier wall-clock budget in seconds; the full tier builds venvs, slowest first."""

# The suite tiers a caller can ask for, and the ledger row each one is. The
# marker expressions themselves are NOT repeated here: tests/matrix/tiers.json
# records them per task (and tests/test_marker_drift.py already holds that file
# against Taskfile.yml), so this reads the row instead of keeping a copy that
# could drift from the task it claims to run.
TIER_TASKS = {"fast": "test-fast", "heavy": "test-heavy", "slow": "test-slow", "meta": "test-meta", "all": "test"}
TIER_LEDGER = TOP / "tests" / "matrix" / "tiers.json"
TIER_TIMEOUTS = {"fast": 1800, "heavy": 3600, "slow": 1800, "meta": 900, "all": 7200}
"""Per-tier wall-clock budget in seconds, generous enough for a cold cache."""


def _paths() -> tuple[Path, Path, Path, Path]:
    """Resolve the witness/ledger paths against the (possibly monkeypatched) shim TOP."""
    from tools.mcp_shared import repo_root  # noqa: E402, PLC0415  -- the shim owns TOP; leaves read it lazily.

    top = repo_root()
    return (
        top / "tests" / "matrix" / "witnesses.jsonl",
        top / "tests" / "matrix" / "witnesses.json",
        top / "tests" / "test_witness_matrix.py",
        top / "tests" / "matrix" / "tiers.json",
    )


def witness_inventory() -> dict[str, Any]:
    """The declared leaves, each with the tier and result last recorded for it."""
    witness_list, witness_ledger, _witness_tests, _tier_ledger = _paths()
    try:
        requests = batch.load_requests([witness_list])
    except (batch.SpecError, OSError) as exc:
        msg = f"cannot read {witness_list}: {exc}"
        raise ToolError(msg) from exc
    ledger: dict[str, Any] = json.loads(witness_ledger.read_text(encoding="utf-8")) if witness_ledger.is_file() else {}
    recorded: dict[str, dict[str, Any]] = {entry["id"]: entry for entry in ledger.get("leaves", [])}
    leaves = [
        {
            "id": request.id,
            "tier": recorded.get(request.id, {}).get("tier", "unrecorded"),
            "result": recorded.get(request.id, {}).get("result", "not-run"),
        }
        for request in requests
    ]
    return {
        "total": len(leaves),
        "coverage": ledger.get("coverage", {}),
        "tiers": dict(sorted(Counter(leaf["tier"] for leaf in leaves).items())),
        "results": dict(sorted(Counter(leaf["result"] for leaf in leaves).items())),
        "leaves": leaves,
    }


def output_tail(stdout: str, stderr: str) -> str:
    """The tail of a subprocess' output: enough to see why it did not run."""
    return (stdout + stderr).strip()[-OUTPUT_LIMIT:]


def build_pytest_command(report: Path, expression: str | None, only: str | None, tests: Path | None) -> list[str]:
    """Assemble the pytest argv for running a tier in a subprocess."""
    command = [sys.executable, "-m", "pytest", "-q", "--junit-xml", str(report)]
    if expression:
        command += ["-m", expression]
    if only:
        command += ["-k", only]
    if tests is not None:
        command.append(str(tests))
    return command


def format_pytest_tier_result(
    proc: subprocess.CompletedProcess[str],
    report: Path,
    meta: tuple[str, str | None, float],
    command: list[str],
) -> dict[str, Any]:
    """Parse the JUnit XML report and return the structured verdict dictionary."""
    tier, only, seconds = meta
    if not report.is_file():
        return {
            "ok": False,
            "tier": tier,
            "only": only,
            "command": command,
            "seconds": seconds,
            "counts": {"passed": 0, "failed": 0, "skipped": 0},
            "output": output_tail(proc.stdout, proc.stderr),
            "lines": [],
        }
    lines, counts = batch.junit_verdicts(report)
    return {
        "ok": proc.returncode == 0,
        "tier": tier,
        "only": only,
        "command": command,
        "seconds": seconds,
        "counts": counts,
        "output": "" if proc.returncode == 0 else output_tail(proc.stdout, proc.stderr),
        "lines": [line.as_dict() for line in lines],
    }


def run_pytest_tier(
    tier: str, expression: str | None, tests: Path | None, *, only: str | None, timeout: int
) -> dict[str, Any]:
    """Run one pytest selection in a subprocess and return the structured verdict.

    The one body behind run_witness and run_tests (TODO.md §28.3 3e -- the two
    tools were ~60 duplicated lines each): `expression` is the ``-m`` marker
    selection (None omits it), `tests` an optional file to run, `only` the
    ``-k`` narrowing. The verdict machinery (junit -> LineResult) is
    batch.junit_verdicts.
    """
    from tools.mcp_shared import repo_root  # noqa: E402, PLC0415  -- the shim owns TOP; leaves read it lazily.

    report = Path(tempfile.mkdtemp(prefix="mcp-pytest-")) / "report.xml"
    command = build_pytest_command(report, expression, only, tests)
    started = time.monotonic()
    try:
        proc = subprocess.run(  # noqa: S603  WHYNOT: fixed argv; `only` is passed to pytest, not a shell.
            command, cwd=repo_root(), capture_output=True, text=True, check=False, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        msg = f"the {tier} tier did not finish within {timeout}s"
        raise ToolError(msg) from None
    seconds = round(time.monotonic() - started, 3)
    return format_pytest_tier_result(proc, report, (tier, only, seconds), command)


def register_witness(server: Any) -> None:
    """Register the witness/suite tools and the read-only resources on `server`."""
    _register_witness_tools(server)
    _register_suite_tools(server)
    _register_mcp_resources(server)


def _register_witness_tools(server: Any) -> None:  # noqa: C901  -- two witness tools; the bodies are the pre-split implementations.
    """Register the witness-ledger tools on `server`."""

    @server.tool()
    def list_witnesses() -> dict[str, Any]:
        """List the questionnaire's Z3 witness leaves and what has executed them.

        The 272 leaves are `tests/matrix/witnesses.jsonl` -- the request list
        `tools/z3_witnesses.py` enumerates, one answer combination each -- and
        `tier` / `result` are the deepest verdict `tests/matrix/witnesses.json`
        records for that leaf, so this is the "what is already verified" answer.
        Returns `total`, `coverage` (the ledger's counters), `tiers` and `results`
        (leaf counts per value) and `leaves`: {id, tier, result} in declaration
        order. Filesystem only -- no render, no network.
        """
        return witness_inventory()

    @server.tool()
    def recommend_answers(constraints: list[str], *, render: bool = False) -> dict[str, Any]:
        """Find the witness answers that produce the features you name (the inverse template).

        Each constraint is `name`, `name=value`, `-name` or `name!=value`, naming
        any question or derived internal the render context exposes (`docker`,
        `mcp_effective`, `sphinx`, `license_effective`, ...); an unknown name is
        rejected with the closest real names. Returns {"constraints", "matched",
        "shown", "leaves", "diagnostic", "render"}: every matching witness leaf
        with its full `answers`, the same answers as a `--data-file`-ready YAML
        string (`answers_yaml`) and the artifacts its class ships (`ships`). The
        match is exact over the declared 272-leaf space, so a combination no leaf
        carries is reported as such, not guessed: with no match, `diagnostic`
        names the constraint that eliminated the most leaves and the nearest leaf
        with what it misses. `render=True` also renders the top match and proves
        every constraint against the rendered tree (a fresh context pass over the
        render's own recorded answers, plus the name-gated artifacts -- e.g.
        `docker` -> `.dockerignore`, `use_gpu_effective` -> `Dockerfile.gpu`);
        that is one real render (~1-2s, no install, no network). Without it:
        filesystem + copier's questionnaire pass -- ~50 ms warm, ~25 s on the
        first call (cached under `.cache/answers-for/` until the questionnaire or
        the witnesses move).
        """
        try:
            return answers_for.recommend(constraints, render=render, keep=True)
        except answers_for.ConstraintError as exc:
            raise ToolError(str(exc)) from exc

    @server.tool()
    def run_witness(
        tier: Literal["fast", "slow", "full"], *, only: str | None = None, timeout: int | None = None
    ) -> dict[str, Any]:
        """Run one tier of the witness suite and return a verdict per test.

        `tests/test_witness_matrix.py` executes the leaves; this runs it in a
        subprocess so a caller gets its verdict instead of pytest's text. `tier` is
        the marker expression: `fast` renders and lints every leaf (no venv; a few
        seconds under the suite's `-n auto`), `slow` runs the serial 272-leaf batch
        runner (~2 min), `full` adds the sampled leaves' venv builds and their
        network. `only` narrows the selection with pytest's `-k` expression -- a
        leaf keyword, for one case -- and `timeout` overrides the tier's budget
        (seconds).

        Returns `ok` (pytest's exit status), the exact `command` so it can be
        rerun by hand, `seconds`, `counts` (passed / failed / skipped), `output`
        (the tail, only when the run failed) and `lines`: one entry per executed
        test in `run_batch`'s verdict shape -- `id`, `ok`, `seconds`, `checks`
        ({name, ok, detail}) -- with a skip reported as `name: "skipped"` rather
        than a failure.
        """
        if tier not in WITNESS_MARKERS:
            msg = f"unknown tier {tier!r}; expected one of {', '.join(sorted(WITNESS_MARKERS))}"
            raise ToolError(msg)
        limit = timeout or WITNESS_TIMEOUTS[tier]
        _witness_list, _witness_ledger, witness_tests, _tier_ledger = _paths()
        return run_pytest_tier(tier, WITNESS_MARKERS[tier], witness_tests, only=only, timeout=limit)


def _register_suite_tools(server: Any) -> None:  # noqa: C901  -- three suite/fingerprint tools; the bodies are the pre-split implementations.
    """Register the suite-tier runners and the fingerprint tool on `server`."""

    @server.tool()
    def run_tests(
        tier: Literal["fast", "heavy", "slow", "meta", "all"], *, only: str | None = None, timeout: int | None = None
    ) -> dict[str, Any]:
        """Run one tier of this repository's own suite and return a verdict per test.

        `run_witness` covers the witness tiers; this is the rest of the suite, so a
        caller gets a structured verdict instead of pytest's text. `tier` names a
        Taskfile task: `fast` is the edit loop (no venv, no network), `heavy`
        builds virtualenvs and installs dependencies, `slow` is the serial
        272-leaf batch runner (~2 min), `meta` runs the cost ledger's own guards,
        `all` runs everything (~80 s warm, minutes cold). The marker expression is
        read from `tests/matrix/tiers.json`, the record the suite's own drift
        guard holds against `Taskfile.yml`. `only` narrows the selection with
        pytest's `-k` expression, and `timeout` overrides the tier's budget
        (seconds).

        Returns `ok` (pytest's exit status), `tier`, `only`, the exact `command`
        so it can be rerun by hand, `seconds`, `counts` (passed / failed /
        skipped), `output` (the tail, only when the run failed) and `lines`: one
        entry per executed test in `run_batch`'s verdict shape -- `id`, `ok`,
        `seconds`, `checks` ({name, ok, detail}) -- with a skip reported as
        `name: "skipped"` rather than a failure.
        """
        task = TIER_TASKS.get(tier)
        if task is None:
            msg = f"unknown tier {tier!r}; expected one of {', '.join(sorted(TIER_TASKS))}"
            raise ToolError(msg)
        _witness_list, _witness_ledger, _witness_tests, tier_ledger = _paths()
        try:
            rows = json.loads(tier_ledger.read_text(encoding="utf-8"))["tiers"]
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            msg = f"cannot read the tier ledger {tier_ledger}: {exc}"
            raise ToolError(msg) from exc
        expression = str(rows.get(task, {}).get("expression", "")) or None
        limit = timeout or TIER_TIMEOUTS[tier]
        return run_pytest_tier(tier, expression, None, only=only, timeout=limit)

    @server.tool()
    def template_fingerprint() -> dict[str, Any]:
        """Report the sha256 of the render inputs -- what a render is a function of.

        The digest covers every file present under `template/` and `_shared/`, plus
        `copier.yml` and `_tasks.jinja`, as sorted relative path + content hash.
        Copier renders a *dirty* working tree as it finds it, so this is a
        content-based key rather than a git revision: an unchanged fingerprint
        means the same answers still render the same bytes, and a changed one means
        every render you are holding -- the one in `dest` of a previous call, a
        project's checked-in `.copier-answers.yml` render, the suite's session
        render cache -- is stale. Returns that `fingerprint`, the `algorithm`, and
        `inputs`: the trees and files covered, the path count and the total bytes.
        Hashes the working tree only -- no render, no network (~224 paths, 0.8 MB,
        ~5 ms). The digest comes from `tools/render_inputs.py`, the same one the
        test suite's render cache namespaces its entries by, so the two cannot
        disagree.
        """
        from tools.mcp_shared import repo_root  # noqa: E402, PLC0415  -- the shim owns TOP; leaves read it lazily.

        fingerprint, paths, total = _render_fingerprint(repo_root())
        return {
            "fingerprint": fingerprint,
            "algorithm": "sha256(relative path + \\0 + sha256(content)) over the sorted inputs",
            "inputs": {
                "dirs": list(RENDER_INPUT_DIRS),
                "files": list(RENDER_INPUT_FILES),
                "paths": paths,
                "bytes": total,
            },
        }

    _register_mcp_resources(server)


def _register_mcp_resources(server: Any) -> None:
    """Register the read-only template resources on `server`."""

    @server.resource("template://questionnaire")
    def questionnaire_resource() -> str:
        """The full questionnaire as JSON, including the internal variables."""
        _questions, settings = questionnaire.load_questions()
        entries = questionnaire.schema_entries()
        return json.dumps({"questions": entries, "settings": settings}, indent=2, default=str)

    @server.resource("template://witnesses")
    def witnesses_resource() -> str:
        """The witness leaves with their recorded tier and result, as JSON.

        Sorted keys and declaration order make the payload deterministic, so a
        caller can diff it between runs.
        """
        return json.dumps(witness_inventory(), indent=2, sort_keys=True)

    @server.resource("template://support")
    def support_resource() -> str:
        """The declared support contract (`support.yml`) as JSON.

        What the project promises to have executed, per combination and per leaf
        class, each entry carrying the measured `why`. Read through
        tools/support_ledger.py -- the one reader of the file, shared with the
        generated docs blocks and tests/test_support_matrix.py -- so a caller sees
        the live declaration rather than a second reading of it.
        """
        return json.dumps(support_ledger.load_support(), indent=2, sort_keys=True)

    @server.resource("template://ethics")
    def ethics_resource() -> str:
        """The ethics/regional rule registry (_shared/ethics/REGISTRY.yml) as JSON.

        One row per accumulated rule section -- id, lifecycle (draft / active /
        kind), enforcement (L0 doc, L1 presence assert, L2 gate), scale,
        audience, scope, primary sources, review dates and the documented
        presence trigger. The active rows are what the generated AGENTS.md
        ethics appendix ships; `check_ethics` matches text against these same
        triggers.
        """
        return json.dumps(ethics.inventory(), indent=2, sort_keys=True)
