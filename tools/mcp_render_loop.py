#!/usr/bin/env python3
"""Render-loop surface: render, diff two renders, lint a render, run a batch.

Responsibility: the tools that render the real template -- `render_project`
(one render plus an optional manifest comparison and an optional install),
`render_diff` (two renders compared file by file), `lint_render` (one render
plus the generated project's own ruff), `list_batch_requests` / `run_batch`
(the batch verdict loop) -- plus the small helpers each one narrows to
(`_validate_diff_target`, `_render_and_prepare`,
`_build_rendered_files_inventory`, `_manifest_diff`, `_lint_checks`). The
 render itself and the byte comparison live in `tools/mcp_render.py`; this
module owns only the tool shapes around them.
"""

# WHYNOT: the functions below are registered through @server.tool()
# inside register_*(); their call edge is the decorator, invisible to
# the checker.
# pyright: reportUnusedFunction=false

from __future__ import annotations

import hashlib
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402
from tools import batch  # noqa: E402
from tools import mcp_render  # noqa: E402


def validate_diff_target(diff_against: str | None) -> Path | None:
    """Resolve and validate the optional diff-against directory."""
    if not diff_against:
        return None
    previous = Path(diff_against).resolve()
    if not previous.is_dir():
        msg = f"diff_against is not a directory: {diff_against}"
        raise ToolError(msg)
    return previous


def render_and_prepare(answers: dict[str, Any], work: Path, *, prepare: bool) -> None:
    """Render template into work directory and optionally execute prepare_environment."""
    mcp_render.render_into(answers, work)
    if not prepare:
        return
    with batch.report_stream_only():
        checks = [batch.prepare_environment(work, "render")]
    failed = [check for check in checks if not check.ok]
    if failed:
        msg = f"render succeeded but prepare failed: {failed[0].detail}"
        raise ToolError(msg)


def build_rendered_files_inventory(rendered: dict[str, Path]) -> tuple[list[dict[str, str]], list[str]]:
    """Build list of {path, sha256} records and sorted top-level directory names."""
    files = [
        {"path": name, "sha256": hashlib.sha256(body.read_bytes()).hexdigest()}
        for name, body in sorted(rendered.items())
    ]
    top_level = sorted({entry["path"].split("/")[0] for entry in files})
    return files, top_level


def manifest_diff(target: Path, rendered: dict[str, Path]) -> dict[str, Any]:
    """Manifest comparison of a previous render's directory and this render.

    The `render_diff` shape narrowed to what "render again and diff against
    the tree I already have" needs: `a` is the diff target, `b` this render,
    files equal under the stamp-masked comparison count as `same_count`, and
    the changed entries carry both sides' digests of the compared bytes. Only
    paths present on both sides can differ -- one-sided paths are listed as
    `only_in_a` / `only_in_b`, never as changes.
    """
    tree_a = mcp_render.tree(target)
    changed: list[dict[str, Any]] = []
    same = 0
    for name in sorted(set(tree_a) & set(rendered)):
        body_a, body_b = mcp_render.compared(tree_a[name], name), mcp_render.compared(rendered[name], name)
        if body_a == body_b:
            same += 1
        else:
            changed.append(
                {
                    "path": name,
                    "sha256_a": hashlib.sha256(body_a).hexdigest(),
                    "sha256_b": hashlib.sha256(body_b).hexdigest(),
                }
            )
    return {
        "same_count": same,
        "changed": changed,
        "only_in_a": sorted(set(tree_a) - set(rendered)),
        "only_in_b": sorted(set(rendered) - set(tree_a)),
    }


def lint_checks(dest: Path) -> list[batch.Check]:
    """The ruff verdicts for a rendered tree (the machinery lives in batch.ruff_checks)."""
    return batch.ruff_checks(dest)


def register_render_loop(server: Any) -> None:  # noqa: C901  -- registers render_project, then delegates to the batch and diff helpers below.
    """Register the render-loop tools on `server`."""

    @server.tool()
    def render_project(
        answers: dict[str, Any], *, dest: str | None = None, prepare: bool = False, diff_against: str | None = None
    ) -> dict[str, Any]:
        """Render the template with `answers` and report what it produced.

        `answers` are the copier answers; unset questions fall back to their
        defaults (this is `--defaults`), so usually only `project_type` and the
        Project Details are needed. The render happens from this checkout, so
        uncommitted template changes are included -- run `inspect_project` first
        if the target may be an existing project.

        `dest` defaults to a fresh temporary directory. `prepare=True` also runs
        the project's install command (`uv sync` / `pixi install` / `poetry
        install`, chosen from what was rendered), which needs the network on a
        cold cache.

        Returns the destination path, the file count, `top_level` and `files`: one
        entry per rendered file, {path, sha256} with the digest over the file's
        own bytes, so the payload feeds a regression check without re-reading the
        tree.

        `diff_against` optionally names a previous render's directory: the payload
        then also carries `diff`, the manifest comparison in `render_diff`'s shape
        with `a` the diff target and `b` this render -- `same_count` (paths on
        both sides with equal bytes), `changed` ({path, sha256_a, sha256_b} per
        differing path), `only_in_a` (paths only in the diff target) and
        `only_in_b` (paths only in this render). `.copier-answers.yml` is compared
        with copier's per-render stamps masked, like every render comparison here.
        A `diff_against` path that is not a directory raises before anything is
        rendered. One render plus a byte comparison; no install, no network unless
        `prepare`.
        """
        previous = validate_diff_target(diff_against)
        work = Path(dest).resolve() if dest else Path(tempfile.mkdtemp(prefix="mcp-render-"))
        work.mkdir(parents=True, exist_ok=True)
        render_and_prepare(answers, work, prepare=prepare)
        rendered = mcp_render.tree(work)
        files, top_level = build_rendered_files_inventory(rendered)
        payload: dict[str, Any] = {
            "dest": str(work),
            "file_count": len(files),
            "files": files,
            "top_level": top_level,
        }
        if previous is not None:
            payload["diff"] = manifest_diff(previous, rendered)
        return payload

    _register_batch_tools(server)


def _register_batch_tools(server: Any) -> None:  # noqa: C901  -- two batch tools; the bodies are the pre-split implementations.
    """Register the batch listing/runner tools on `server`."""

    @server.tool()
    def list_batch_requests(jsonl: str) -> dict[str, Any]:
        """List the requests in a batch file (see docs/how-to/batch.md).

        Returns {"count", "requests"}: each request's id, note, destination and
        whether it carries an `update` phase, so a caller can pick one to run
        instead of running all of them. Filesystem only -- no render, no network,
        while `run_batch` on the same file renders every request it selects. A
        malformed request list raises rather than returning a partial listing.
        """
        try:
            requests = batch.load_requests([Path(jsonl)])
        except (batch.SpecError, OSError) as exc:
            msg = f"cannot read {jsonl}: {exc}"
            raise ToolError(msg) from exc
        listed = [
            {
                "id": request.id,
                "note": request.note,
                "dest": request.dest,
                "has_update": request.update is not None,
                "checks": len(request.commands),
            }
            for request in requests
        ]
        return {"count": len(listed), "requests": listed}

    @server.tool()
    def run_batch(
        jsonl: str, *, only: str | None = None, prepare: bool = False, keep: bool = False, jobs: int = 1
    ) -> dict[str, Any]:
        """Run a batch of generation requests and return the verdict.

        `jsonl` is a request list (docs/how-to/batch.md); `only` is a regular
        expression selecting ids. Each line renders with the real template, runs
        its commands and judges its `expect` block, so this is the "did the
        change break a combination" check. `ok` is true only when every selected
        line passed; `lines[].checks[].detail` carries the observed value for a
        failure. Renders are real (uncommitted template changes included) and
        `prepare=True` additionally installs each project (network on a cold
        cache). `jobs` renders up to that many requests concurrently in worker
        processes (default 1: serial, in file order; rendering is not
        thread-safe). `keep=True` leaves the rendered projects on disk and reports
        their directory.
        """
        try:
            requests = batch.load_requests([Path(jsonl)])
        except (batch.SpecError, OSError) as exc:
            msg = f"cannot read {jsonl}: {exc}"
            raise ToolError(msg) from exc
        if only:
            pattern = re.compile(only)
            requests = [request for request in requests if pattern.search(request.id)]
            if not requests:
                msg = f"no request id matches {only!r}"
                raise ToolError(msg)

        work = Path(tempfile.mkdtemp(prefix="mcp-batch-"))
        with batch.report_stream_only():
            results = batch.run_requests(requests, work, TOP, jobs=jobs, prepare=prepare)
        return {
            "ok": all(result.ok for result in results),
            "work": str(work) if keep else None,
            "lines": [result.as_dict() for result in results],
        }

    _register_diff_tools(server)


def _register_diff_tools(server: Any) -> None:  # noqa: C901  -- two comparison tools; the bodies are the pre-split implementations.
    """Register the render-comparison tools on `server`."""

    @server.tool()
    def render_diff(answers_a: dict[str, Any], answers_b: dict[str, Any], *, keep: bool = False) -> dict[str, Any]:
        """Render `answers_a` and `answers_b` and compare the two trees file by file.

        Returns `identical` (every path exists on both sides with the same bytes),
        `file_count` and `identical_count`, `only_in_a` / `only_in_b` (paths on one
        side only), `answers_commit` (the `_commit` copier recorded in
        `.copier-answers.yml` on each side) and `changed`: one entry per path
        present on both sides with different bytes, carrying `bytes_a` / `bytes_b`
        / `sha256_a` / `sha256_b` and a `diff` (unified, at most 40 lines, first 25
        changed files, with `diff_truncated` when it was cut). Files that match are
        counted, not listed. Answer sets fall back to their defaults like
        `render_project`.

        `.copier-answers.yml` is compared with that `_commit` stamp normalized: for
        a dirty template copier stamps a synthetic commit it creates per render, so
        the raw file differs between two renders of *identical* answers -- the one
        difference that says nothing about the answers. Everything else is byte
        for byte.

        Two renders, no install, no network: this is the "did my change alter an
        unrelated combination" check, and the one-call form of the audit's manual
        comparison of 1684 rendered files. `keep=True` leaves both renders on disk
        and reports their directories.
        """
        work = Path(tempfile.mkdtemp(prefix="mcp-diff-"))
        first, second = work / "a", work / "b"
        for dest, answers in ((first, answers_a), (second, answers_b)):
            dest.mkdir(parents=True, exist_ok=True)
            mcp_render.render_into(answers, dest)

        tree_a, tree_b = mcp_render.tree(first), mcp_render.tree(second)
        only_in_a = sorted(set(tree_a) - set(tree_b))
        only_in_b = sorted(set(tree_b) - set(tree_a))
        identical, changed = mcp_render.compare_shared_files(tree_a, tree_b)
        return {
            "identical": not (only_in_a or only_in_b or changed),
            "dest_a": str(first) if keep else None,
            "dest_b": str(second) if keep else None,
            "file_count": {"a": len(tree_a), "b": len(tree_b)},
            "identical_count": identical,
            "changed_count": len(changed),
            "changed": changed,
            "only_in_a": only_in_a,
            "only_in_b": only_in_b,
            "answers_commit": {
                "a": mcp_render.checkout_stamp(tree_a[batch.ANSWERS_FILE]) if batch.ANSWERS_FILE in tree_a else None,
                "b": mcp_render.checkout_stamp(tree_b[batch.ANSWERS_FILE]) if batch.ANSWERS_FILE in tree_b else None,
            },
        }

    @server.tool()
    def lint_render(answers: dict[str, Any]) -> dict[str, Any]:
        """Render `answers` and lint the result the way the generated project does.

        Runs `ruff format --check` and `ruff check` under the rendered
        `pyproject.toml`, so a template change that renders unformatted or
        unlintable Python fails here instead of later in
        `tests/test_generated_lint.py`. No venv and no network: one render plus two
        ruff runs. The ruff is this checkout's (a rendered project has no
        environment of its own to lint with).

        Returns `checked` -- false when the render ships no Python or no
        `[tool.ruff]` section, in which case `note` says which -- plus the
        `run_batch` verdict shape: `ok`, `dest`, `seconds`, `error` and `checks`
        ({name, ok, detail}, one per ruff command, `detail` carrying ruff's own
        output).
        """
        work = Path(tempfile.mkdtemp(prefix="mcp-lint-"))
        work.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        mcp_render.render_into(answers, work)
        checks = lint_checks(work)
        note = "" if checks else "no Python or no [tool.ruff] section in the render; nothing to lint"
        result = batch.LineResult(
            id="lint_render", index=0, checks=checks, seconds=time.monotonic() - started, dest=str(work), note=note
        )
        return {**result.as_dict(), "checked": bool(checks)}
