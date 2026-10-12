#!/usr/bin/env python3
"""Shared MCP server instance and path conventions for the template's own tooling.

This is the one owner of the `server` object: every `tools/mcp_*.py` module
registers its `@server.tool()` / `@server.resource()` / `@server.custom_route()`
handlers against this instance at import time, and `tools/mcp_server.py`
(the compat entry point) re-exports it. Registration takes the server as a
*parameter* of `register_*()`, never as a module global imported from the
shim, so the leaves stay importable without a cycle back to the entry point.

`repo_root()` is the one read of the checkout root: the shim owns `TOP`
(tests monkeypatch `tools.mcp_server.TOP`), and the leaves call this lazily
at tool time rather than binding the path at import.
"""

from __future__ import annotations

import sys
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from mcp.server import MCPServer  # noqa: E402
from tools import batch  # noqa: E402

OUTPUT_LIMIT = batch.OUTPUT_LIMIT

server = MCPServer("daimonion")


def repo_root() -> Path:
    """This checkout's root: the `TOP` the shim owns (monkeypatched in tests)."""
    mod = sys.modules.get("tools.mcp_server")
    top = getattr(mod, "TOP", None) if mod is not None else None
    if isinstance(top, Path):
        return top
    return TOP
