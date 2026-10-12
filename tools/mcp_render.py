#!/usr/bin/env python3
"""Render trees: the single render entry point plus the file-tree comparison helpers.

Responsibility: everything that turns an answer set into a directory on disk
(`_render_into`), walks a rendered tree (`_tree`), and compares two trees
byte-for-byte with copier's per-render stamps masked (`_compared`,
`_checkout_stamp`, `_unified`, `_compare_shared_files`). The constants bound
that comparison: `DIFF_LINES` caps the unified diff kept per changed file (the
byte comparison itself is never truncated), and `DIFF_FILE_LIMIT` caps how many
changed files carry a diff at all.

Borrowed rule, kept local: stdout belongs to the MCP protocol, so every render
runs inside `batch.report_stream_only()` (fd 1 redirected to stderr). A stray
print would corrupt the session.
"""

from __future__ import annotations

import difflib
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402
from tools import batch  # noqa: E402

DIFF_LINES = 40
"""Unified-diff lines kept per changed file (the byte comparison is not truncated)."""
DIFF_FILE_LIMIT = 25
"""Changed files that carry a diff; beyond it the entry keeps its digests and sizes."""


def render_into(answers: dict[str, Any], dest: Path) -> None:
    """Render this checkout into `dest`, with copier's chatter on stderr.

    The single render entry point of every tool here: stdout is the MCP
    protocol channel, so a stray byte of copier progress would corrupt the
    session (`batch.report_stream_only()` moves fd 1 to stderr).
    """
    from tools.mcp_shared import repo_root  # noqa: E402, PLC0415  -- the shim owns TOP; leaves read it lazily.

    try:
        with batch.report_stream_only():
            batch.render(str(repo_root()), dest, answers)
    except Exception as exc:  # noqa: BLE001  WHYNOT: the tool must report, not crash the session.
        msg = f"render failed: {type(exc).__name__}: {exc}"
        raise ToolError(msg) from exc


def tree(root: Path) -> dict[str, Path]:
    """Every file under `root`, keyed by its POSIX relative path."""
    return {path.relative_to(root).as_posix(): path for path in root.rglob("*") if path.is_file()}


def compared(path: Path, name: str) -> bytes:
    """The bytes to compare for `name`, with copier's per-render stamps masked.

    `.copier-answers.yml` records `_commit` and `_src_path`, and for a *dirty*
    template that commit is a synthetic one copier creates per render: its sha
    changes between two renders of identical answers, so comparing it as-is
    would report every comparison of a working tree as different. The composition
    manifest carries the same stamp under `template_ref`, so it normalizes the
    same way. The stamps are masked by batch.mask_render_stamps (RENDER_STAMPS plus
    MANIFEST_STAMPS is the one stamp list, shared with the render twin and the
    rehearsal) -- the line shape stays, so a diff of genuinely different answers
    is still readable -- and the commit value is reported separately
    (`answers_commit`) instead. Every other byte is compared as it is.
    """
    body = path.read_bytes()
    if name in (batch.ANSWERS_FILE, batch.MANIFEST_FILE):
        return batch.mask_render_stamps(body)
    return body


def checkout_stamp(path: Path) -> str | None:
    """The `_commit` value copier wrote, or None when the file has no stamp."""
    match = re.search(rb"^_commit:\s*(\S+)", path.read_bytes(), re.MULTILINE)
    return match.group(1).decode() if match else None


def unified(name: str, path_a: Path, path_b: Path) -> tuple[str, bool]:
    """A bounded unified diff of one path between two renders."""
    try:
        lines_a = compared(path_a, name).decode().splitlines()
        lines_b = compared(path_b, name).decode().splitlines()
    except UnicodeDecodeError:
        return (f"{name}: binary or not UTF-8; {path_a.stat().st_size} -> {path_b.stat().st_size} bytes", False)
    diff = list(difflib.unified_diff(lines_a, lines_b, f"a/{name}", f"b/{name}", lineterm="", n=1))
    return "\n".join(diff[:DIFF_LINES]), len(diff) > DIFF_LINES


def compare_shared_files(tree_a: dict[str, Path], tree_b: dict[str, Path]) -> tuple[int, list[dict[str, Any]]]:
    """Compare files present in both trees, returning (identical_count, changed_records)."""
    changed: list[dict[str, Any]] = []
    identical = 0
    for name in sorted(set(tree_a) & set(tree_b)):
        path_a, path_b = tree_a[name], tree_b[name]
        body_a, body_b = compared(path_a, name), compared(path_b, name)
        if body_a == body_b:
            identical += 1
            continue
        text, truncated = unified(name, path_a, path_b) if len(changed) < DIFF_FILE_LIMIT else ("", False)
        changed.append(
            {
                "path": name,
                "bytes_a": len(body_a),
                "bytes_b": len(body_b),
                "sha256_a": hashlib.sha256(body_a).hexdigest(),
                "sha256_b": hashlib.sha256(body_b).hexdigest(),
                "diff": text,
                "diff_truncated": truncated,
            }
        )
    return identical, changed
