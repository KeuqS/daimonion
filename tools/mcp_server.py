#!/usr/bin/env python3
"""MCP server exposing this template's own tooling to an agent.

`tools/batch.py`, `tools/detect.py` and `tools/questionnaire.py` are already
the machine-readable layer over this repository; this server is how an MCP
host (Claude Desktop, an IDE agent, the MCP Inspector) calls them instead of
shelling out and parsing text.

Run it over stdio (how an MCP host launches a server):

    uv run python tools/mcp_server.py

Or serve it over HTTP, for a host that connects to a URL:

    uv run python tools/mcp_server.py --transport streamable-http

Debug it with the MCP Inspector:

    uv run mcp dev tools/mcp_server.py

Editing this repository needs no setup: the root `.mcp.json` registers the
stdio command below (the same one `task mcp` runs), and
docs/how-to/mcp-tools.md is the one-page tour of the tools.

Binding to a non-local address (--host 0.0.0.0) requires MCP_ALLOWED_HOSTS:
the SDK arms its DNS-rebinding protection only while the server binds to
localhost, so a publicly bound server would accept any Host header without an
explicit allowlist. This server refuses to start in that state. GET /health is
the liveness probe for an orchestrator; like every SDK custom route it is
unauthenticated and bypasses the host allowlist, and exposes no data.
tests/test_mcp_server.py runs the real server and pins both halves: a foreign
Host gets 421 on /mcp, and /health stays 200.

Two protocol facts shape the implementation:

- **stdout belongs to the protocol.** Copier prints progress to stdout, so
  every render here runs inside `batch.report_stream_only()` (fd 1 redirected
  to stderr). A stray print would corrupt the session.
- **Tools are the contract.** Each docstring below is what the model reads to
  decide when to call it, so they state the cost (rendering, installing,
  network) and what is returned.
  tests/test_mcp_server.py fails when a tool's docstring stops saying both.

The generated scaffold's MCP server (`_shared/mcp_server.py.jinja`, rendered
into a `cli` / `web_api` project when `include_mcp` is on) is a **separate
server on purpose**. That one is the worked example a generated project
starts from -- typed tools, a `ToolError`, resources, a prompt, the
`mcp-server-<name>` console script -- while this one serves the template's
maintenance loop: render, inspect, adopt, verdict a batch, list witnesses.
They share no code and import nothing from each other, because a generated
project must never depend on this repository. The single idea that appears in
both is the MCP_ALLOWED_HOSTS rule plus /health, ~30 lines of SDK glue
re-derived from the SDK API in each; keeping the second copy is what lets
either side change its transport settings without a release coupling. Fix a
generated server in the scaffold, fix a template tool here -- see
docs/how-to/mcp-tools.md.

None of these tools guess the questionnaire: the shape questions
(`project_type`, `include_*`, ...) stay the caller's decision, per
notes/SPEC-adoption.md section 12.

Layout: this module is the entry point only. The `server` object lives in
`tools/mcp_shared.py`; each `tools/mcp_*.py` module registers one
responsibility slice against it (`mcp_questionnaire`, `mcp_project`,
`mcp_render_loop`, `mcp_witness`); the render-tree comparison primitives live
in `tools/mcp_render.py`. The names below are re-exported here so existing
callers (`tools/mcp_server.py` as `python tools/mcp_server.py`, `task mcp`,
`.mcp.json`, `tests/test_mcp_server.py`) keep working unchanged.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from typing import Literal
from typing import cast

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
from tools.mcp_project import register_project  # noqa: E402
from tools.mcp_project import run_adoption  # noqa: E402
from tools.mcp_questionnaire import explain_text  # noqa: E402
from tools.mcp_questionnaire import register_questionnaire  # noqa: E402
from tools.mcp_render import DIFF_FILE_LIMIT  # noqa: E402
from tools.mcp_render import DIFF_LINES  # noqa: E402
from tools.mcp_render import checkout_stamp  # noqa: E402
from tools.mcp_render import compare_shared_files  # noqa: E402
from tools.mcp_render import compared  # noqa: E402
from tools.mcp_render import render_into  # noqa: E402
from tools.mcp_render import tree  # noqa: E402
from tools.mcp_render import unified  # noqa: E402
from tools.mcp_render_loop import build_rendered_files_inventory  # noqa: E402
from tools.mcp_render_loop import lint_checks  # noqa: E402
from tools.mcp_render_loop import manifest_diff  # noqa: E402
from tools.mcp_render_loop import register_render_loop  # noqa: E402
from tools.mcp_render_loop import render_and_prepare  # noqa: E402
from tools.mcp_render_loop import validate_diff_target  # noqa: E402
from tools.mcp_shared import OUTPUT_LIMIT  # noqa: E402
from tools.mcp_shared import server  # noqa: E402
from tools.mcp_witness import TIER_LEDGER  # noqa: E402
from tools.mcp_witness import TIER_TASKS  # noqa: E402
from tools.mcp_witness import TIER_TIMEOUTS  # noqa: E402
from tools.mcp_witness import WITNESS_LEDGER  # noqa: E402
from tools.mcp_witness import WITNESS_LIST  # noqa: E402
from tools.mcp_witness import WITNESS_MARKERS  # noqa: E402
from tools.mcp_witness import WITNESS_TESTS  # noqa: E402
from tools.mcp_witness import WITNESS_TIMEOUTS  # noqa: E402
from tools.mcp_witness import build_pytest_command  # noqa: E402
from tools.mcp_witness import format_pytest_tier_result  # noqa: E402
from tools.mcp_witness import output_tail  # noqa: E402
from tools.mcp_witness import register_witness  # noqa: E402
from tools.mcp_witness import run_pytest_tier  # noqa: E402
from tools.mcp_witness import witness_inventory  # noqa: E402

register_questionnaire(server)
register_project(server)
register_render_loop(server)
register_witness(server)

__all__ = [
    "DIFF_FILE_LIMIT",
    "DIFF_LINES",
    "OUTPUT_LIMIT",
    "TIER_LEDGER",
    "TIER_TASKS",
    "TIER_TIMEOUTS",
    "TOP",
    "WITNESS_LEDGER",
    "WITNESS_LIST",
    "WITNESS_MARKERS",
    "WITNESS_TESTS",
    "WITNESS_TIMEOUTS",
    "_allowed_hosts",
    "_build_pytest_command",
    "_build_rendered_files_inventory",
    "_checkout_stamp",
    "_compare_shared_files",
    "_compared",
    "_explain_text",
    "_format_pytest_tier_result",
    "_lint_checks",
    "_manifest_diff",
    "_output_tail",
    "_render_and_prepare",
    "_render_into",
    "_run_adoption",
    "_run_pytest_tier",
    "_tree",
    "_unified",
    "_validate_diff_target",
    "_witness_inventory",
    "adopt_project",
    "build_pytest_command",
    "build_rendered_files_inventory",
    "check_ethics",
    "checkout_stamp",
    "compare_shared_files",
    "compared",
    "explain_choice",
    "explain_text",
    "format_pytest_tier_result",
    "inspect_project",
    "lint_checks",
    "lint_render",
    "list_batch_requests",
    "list_presets",
    "list_questions",
    "list_witnesses",
    "main",
    "manifest_diff",
    "output_tail",
    "recommend_answers",
    "render_and_prepare",
    "render_diff",
    "render_into",
    "render_project",
    "run_adoption",
    "run_batch",
    "run_pytest_tier",
    "run_tests",
    "run_witness",
    "server",
    "suggest_config",
    "template_fingerprint",
    "template_status",
    "tree",
    "unified",
    "validate_answers",
    "validate_diff_target",
    "witness_inventory",
]

# Back-compat private aliases: the pre-split module spelled these with a
# leading underscore; tests and out-of-tree callers may still import them.
_explain_text = explain_text
_run_adoption = run_adoption
_validate_diff_target = validate_diff_target
_render_and_prepare = render_and_prepare
_build_rendered_files_inventory = build_rendered_files_inventory
_manifest_diff = manifest_diff
_render_into = render_into
_tree = tree
_compared = compared
_checkout_stamp = checkout_stamp
_unified = unified
_compare_shared_files = compare_shared_files
_lint_checks = lint_checks
_witness_inventory = witness_inventory
_output_tail = output_tail
_build_pytest_command = build_pytest_command
_format_pytest_tier_result = format_pytest_tier_result
_run_pytest_tier = run_pytest_tier


@server.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    """Liveness probe for an orchestrator (unauthenticated, no data).

    A custom route is a plain Starlette route, so it bypasses the Host
    allowlist that guards /mcp -- the same trade the generated scaffold makes,
    and why this one answers nothing but "the process is up".
    """
    return JSONResponse({"status": "ok"})


def _allowed_hosts() -> TransportSecuritySettings | None:
    """Turn MCP_ALLOWED_HOSTS / MCP_ALLOWED_ORIGINS into the SDK's settings."""
    raw_hosts = os.environ.get("MCP_ALLOWED_HOSTS")
    if not raw_hosts:
        return None
    hosts = [host.strip() for host in raw_hosts.split(",") if host.strip()]
    raw_origins = os.environ.get("MCP_ALLOWED_ORIGINS")
    if not raw_origins:
        return TransportSecuritySettings(allowed_hosts=hosts)
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins)


# Back-compat plain tool functions: the pre-split module exposed these as
# module-level callables (tests call e.g. `mcp_server.template_status()`
# directly and monkeypatch `mcp_server.TOP`). They delegate to the registered
# implementations, which are the same function objects.
def _tool(name: str) -> Any:
    return server._tool_manager._tools[name].fn  # type: ignore[attr-defined]  # noqa: SLF001  -- the SDK keeps no public accessor for the registered function; the shim re-exports the same object.


list_questions = _tool("list_questions")
list_presets = _tool("list_presets")
explain_choice = _tool("explain_choice")
suggest_config = _tool("suggest_config")
validate_answers = _tool("validate_answers")
inspect_project = _tool("inspect_project")
template_status = _tool("template_status")
check_ethics = _tool("check_ethics")
adopt_project = _tool("adopt_project")
render_project = _tool("render_project")
list_batch_requests = _tool("list_batch_requests")
run_batch = _tool("run_batch")
render_diff = _tool("render_diff")
lint_render = _tool("lint_render")
list_witnesses = _tool("list_witnesses")
recommend_answers = _tool("recommend_answers")
run_witness = _tool("run_witness")
run_tests = _tool("run_tests")
template_fingerprint = _tool("template_fingerprint")


def main(args: Sequence[str] | None = None) -> None:
    """Run the MCP server with stdio (default) or Streamable HTTP."""
    parser = argparse.ArgumentParser(description="MCP server for daimonion")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (streamable-http)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (streamable-http)")
    parsed = parser.parse_args(args)
    transport = cast(Literal["stdio", "streamable-http"], parsed.transport)
    if transport == "streamable-http":
        host = cast(str, parsed.host)
        if host not in ("127.0.0.1", "localhost", "::1") and not os.environ.get("MCP_ALLOWED_HOSTS"):
            parser.error(
                "binding to a non-local host requires MCP_ALLOWED_HOSTS "
                "(comma-separated host allowlist) so the server does not "
                "accept every Host header"
            )
        server.run(transport=transport, host=host, port=cast(int, parsed.port), transport_security=_allowed_hosts())
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
