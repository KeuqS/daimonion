#!/usr/bin/env python3
"""Run a JSONL batch of copier requests and verdict each one mechanically.

One JSON object per line describes one generation request plus the checks
that decide whether it succeeded. The runner executes the lines in order,
judges every check itself, and exits nonzero on the first failure class it
finds -- so a batch run needs no eyeballing: either it exits 0 or it names
the request, the check and the observed value that failed.

Why this exists rather than more pytest cases: the same request list can be
produced by a human, by CI, or by a generator (see notes/PLAN-improvements.md
W3, which turns Z3 witnesses of the questionnaire into exactly this format),
and it runs the *real* copier against the *real* template working tree.

Schema (one line per request; unknown keys anywhere are an error):

    id            unique string, required. Also the default destination dir.
    note          free text, ignored by the runner.
    src           template path or git URL. Default: this repository.
    ref           git ref for the template. Default: "HEAD".
    answers       copier data (inline object).
    answers_file  YAML answers file, relative to --repo. Merged *under*
                  `answers`, so inline values win.
    dest          destination subdirectory of the work dir. Default: `id`.
    update        optional second phase, run after the copy:
                    ref, answers, answers_file, conflict ("inline"|"rej")
                  The destination is git-committed first, because copier
                  only updates git-tracked subprojects. The template tree
                  must itself be clean: copier records the synthetic commit
                  it creates for a dirty tree, which a later update cannot
                  check out again (the line fails with that reason instead
                  of generating something unusable).
    commands      optional list of shell commands run in the destination:
                    run (required), cwd (".", relative to dest), timeout,
                    exit, stdout_regex, stderr_regex
    expect        optional static checks against the final destination:
                    files    globs that must match at least one path
                    absent   globs that must match no path
                    matches  [{path, regex}] must match the file text
                    unmatches[{path, regex}] must not match
                    toml     [{path, key, equals}] dotted-key lookup in a
                             TOML file (integer segments index lists)

`expect` and `commands` are judged against the state *after* `update`, if
that phase is present.

Usage:
    python tools/batch.py batches/smoke.jsonl
    python tools/batch.py batches/smoke.jsonl --only web-api --keep
    python tools/batch.py batches/smoke.jsonl --json > verdict.json
    python tools/batch.py tests/matrix/witnesses.jsonl --json --jobs 16

Concurrency (`--jobs N`, default 1 = strictly serial in file order):

Every request owns its work dir -- `dest` is a subdirectory of `--work`, and
the loader rejects duplicate or nested dests -- plus the temp clones copier
makes for itself. So the verdicts do not depend on completion order: the human
report, `--json` and the exit code all follow the JSONL, whichever request
happens to finish first.

The workers are *processes*, not threads, because rendering is not thread-safe
in this process: for a local template copier's `clone()` wraps its checkout in
plumbum's `local.cwd(...)`, which is `os.chdir` -- process-wide state. Two
renders interleaved in one process chdir into each other's clone (measured:
`fatal: not a git repository: '.git'`). Jinja rendering is GIL-bound on top of
that: the same 24 leaves of this repo's witness file took 13.0s in one thread
and 11.6s spread over 8 (1.1x, one line lost to the race above), where
`--jobs 16` renders the whole witness file in 10.2s against 113.8s serial
(11x; measured at the 205-leaf tree). Processes also keep `--prepare` installs and request commands from
sharing a cwd.

What `--jobs` does *not* make independent: the template tree itself. Every
render runs `git status --porcelain` on it (copier's dirty-tree check, plus
`update_precondition` for lines with an `update` phase) and clones it, all
read-only; a git `index.lock` collision there surfaces as a failed line, not
as a wrong verdict. And `--jobs` never parallelizes *within* a request: its
phases and commands still run in the declared order. `--fail-fast` under
`--jobs N` stops starting new requests at the first failure and drains the
in-flight ones, so it can report more than one failing line.

Exit codes: 0 all lines passed, 1 a check failed, 2 the input is invalid.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Generator
from concurrent.futures import FIRST_COMPLETED
from concurrent.futures import Future
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import wait
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import Literal

import copier
import yaml
from copier._main import Worker

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools.git import GIT  # noqa: E402
from tools.git import run as run_git  # noqa: E402

REQUEST_KEYS = frozenset(
    {"id", "note", "src", "ref", "answers", "answers_file", "dest", "update", "commands", "expect"}
)
UPDATE_KEYS = frozenset({"ref", "answers", "answers_file", "conflict"})
COMMAND_KEYS = frozenset({"run", "cwd", "timeout", "exit", "stdout_regex", "stderr_regex"})
EXPECT_KEYS = frozenset({"files", "absent", "matches", "unmatches", "toml", "agents_md"})
MATCH_KEYS = frozenset({"path", "regex"})
TOML_KEYS = frozenset({"path", "key", "equals"})
AGENTS_MD_KEYS = frozenset({"present", "absent"})

DEFAULT_TIMEOUT = 300
OUTPUT_LIMIT = 2000

ANSWERS_FILE = ".copier-answers.yml"
"""Where copier records a render's answers -- and its per-render stamps."""

RENDER_STAMPS = ("_commit", "_src_path")
"""The `.copier-answers.yml` keys that vary per render instead of with the answers.

`_commit` names the template revision the render came from (for a *dirty*
template, a synthetic commit copier creates per render), `_src_path` the
absolute checkout. Two renders of identical answers can differ in both, so
every comparison of renders takes them out first (TODO.md §28.3 3c / §28.5
R3: this tuple is the one declaration -- a new stamp is a one-line edit here,
and the two readers below follow it)."""

MANIFEST_FILE = ".daimonion-manifest.yml"
"""The composition contract: the public record beside the answers file."""

MANIFEST_STAMPS = ("template_ref",)
"""The manifest keys that vary per render instead of with the composition.

`template_ref` is the answers file's `_commit` under the manifest's own key
(tools/verify.py holds the two to each other), so it varies exactly when
`_commit` does -- including the synthetic-commit churn of dirty-template
renders. The two readers below take it out alongside RENDER_STAMPS; a key
absent from the parsed file is a no-op pop/miss, so neither reader needs to
know which file its bytes came from."""


def strip_render_stamps(data: bytes) -> bytes:
    """Render-record bytes without the stamps, canonically re-encoded.

    The comparison form: a manifest hash of a rendered tree, so two renders of
    the same answers hash equal whatever checkout or revision produced them.
    The canonical re-encoding (sorted-key JSON) is part of the definition --
    the YAML key order copier chose is not worth carrying. Applies to both the
    answers file (RENDER_STAMPS) and the composition manifest (MANIFEST_STAMPS):
    each file carries only its own keys, so the other's pop is a no-op.
    """
    parsed = yaml.safe_load(data.decode("utf-8")) or {}
    for key in (*RENDER_STAMPS, *MANIFEST_STAMPS):
        parsed.pop(key, None)
    return json.dumps(parsed, sort_keys=True).encode("utf-8")


def answers_body(answers: dict[str, Any]) -> dict[str, Any]:
    """The answers without copier's per-render stamps (tools/verify.py's drift view reads them this way)."""
    return {key: value for key, value in answers.items() if key not in RENDER_STAMPS}


def mask_render_stamps(data: bytes, mask: str = "<per-render>") -> bytes:
    """The stamps' values masked in place (`_commit: <per-render>`), line shape kept.

    The display form, for a unified diff: the YAML stays line-readable and two
    renders of the same answers still compare equal -- only the values are
    hidden, not the keys or the file's shape. Covers both stamp sets (see
    strip_render_stamps): a key the file does not carry matches nothing.
    """
    for key in (*RENDER_STAMPS, *MANIFEST_STAMPS):
        data = re.sub(rf"^{re.escape(key)}:.*$".encode(), f"{key}: {mask}".encode(), data, flags=re.MULTILINE)
    return data


class SpecError(Exception):
    """The request list itself is invalid (not a failing expectation)."""


@dataclass
class Check:
    """One judged condition, with the evidence needed to debug a failure."""

    name: str
    ok: bool
    detail: str = ""


@dataclass
class LineResult:
    """The verdict for one JSONL line."""

    id: str
    index: int
    checks: list[Check] = field(default_factory=list)
    seconds: float = 0.0
    error: str | None = None
    dest: str = ""
    note: str = ""

    @property
    def ok(self) -> bool:
        """True when the line ran and every check passed."""
        return self.error is None and all(check.ok for check in self.checks)

    def as_dict(self) -> dict[str, Any]:
        """Serializable form used by --json."""
        return {
            "id": self.id,
            "index": self.index,
            "ok": self.ok,
            "seconds": round(self.seconds, 3),
            "dest": self.dest,
            "note": self.note,
            "error": self.error,
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks],
        }


@dataclass
class Request:
    """A parsed and validated JSONL line."""

    id: str
    index: int
    src: str
    ref: str
    answers: dict[str, Any]
    answers_file: str | None
    dest: str
    update: dict[str, Any] | None
    commands: list[dict[str, Any]]
    expect: dict[str, Any]
    note: str = ""


def _reject_unknown(where: str, value: dict[str, Any], allowed: frozenset[str]) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        msg = f"{where}: unknown key(s) {', '.join(unknown)}; allowed: {', '.join(sorted(allowed))}"
        raise SpecError(msg)


def _as_object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        msg = f"{where}: expected an object, got {type(value).__name__}"
        raise SpecError(msg)
    return value


def _as_list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        msg = f"{where}: expected a list, got {type(value).__name__}"
        raise SpecError(msg)
    return value


def _require_str(entry: dict[str, Any], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value:
        msg = f"{where}: {key!r} is required and must be a non-empty string"
        raise SpecError(msg)
    return value


def _parse_update(request_id: str, raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    obj = _as_object(raw, f"{request_id}: update")
    _reject_unknown(f"{request_id}: update", obj, UPDATE_KEYS)
    if obj.get("conflict", "inline") not in ("inline", "rej"):
        msg = f"{request_id}: update.conflict must be 'inline' or 'rej'"
        raise SpecError(msg)
    return obj


def _parse_commands(request_id: str, raw: Any) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    for command in _as_list(raw, f"{request_id}: commands"):
        obj = _as_object(command, f"{request_id}: command")
        _reject_unknown(f"{request_id}: command", obj, COMMAND_KEYS)
        _require_str(obj, "run", f"{request_id}: command")
        commands.append(obj)
    return commands


def _expect_globs(request_id: str, expect: dict[str, Any], key: str) -> None:
    for pattern in _as_list(expect.get(key, []), f"{request_id}: expect.{key}"):
        if not isinstance(pattern, str) or not pattern:
            msg = f"{request_id}: expect.{key} entries must be non-empty glob strings"
            raise SpecError(msg)


def _expect_matches(request_id: str, expect: dict[str, Any]) -> None:
    for key in ("matches", "unmatches"):
        for entry in _as_list(expect.get(key, []), f"{request_id}: expect.{key}"):
            obj = _as_object(entry, f"{request_id}: expect.{key} entry")
            _reject_unknown(f"{request_id}: expect.{key}", obj, MATCH_KEYS)
            _require_str(obj, "path", f"{request_id}: expect.{key}")
            _require_str(obj, "regex", f"{request_id}: expect.{key}")


def _expect_toml(request_id: str, expect: dict[str, Any]) -> None:
    for entry in _as_list(expect.get("toml", []), f"{request_id}: expect.toml"):
        obj = _as_object(entry, f"{request_id}: expect.toml entry")
        _reject_unknown(f"{request_id}: expect.toml", obj, TOML_KEYS)
        _require_str(obj, "path", f"{request_id}: expect.toml")
        _require_str(obj, "key", f"{request_id}: expect.toml")
        if "equals" not in obj:
            msg = f"{request_id}: expect.toml entries need an 'equals' value (any JSON type)"
            raise SpecError(msg)


def _expect_agents_md(request_id: str, expect: dict[str, Any]) -> None:
    for entry in _as_list(expect.get("agents_md", []), f"{request_id}: expect.agents_md"):
        obj = _as_object(entry, f"{request_id}: expect.agents_md entry")
        _reject_unknown(f"{request_id}: expect.agents_md", obj, AGENTS_MD_KEYS)
        for key in ("present", "absent"):
            for section_id in _as_list(obj.get(key, []), f"{request_id}: expect.agents_md.{key}"):
                if not isinstance(section_id, str) or not section_id:
                    msg = f"{request_id}: expect.agents_md.{key} entries must be section ids"
                    raise SpecError(msg)


def _parse_expect(request_id: str, raw: Any) -> dict[str, Any]:
    expect = _as_object(raw, f"{request_id}: expect")
    _reject_unknown(f"{request_id}: expect", expect, EXPECT_KEYS)
    for key in ("files", "absent"):
        _expect_globs(request_id, expect, key)
    _expect_matches(request_id, expect)
    _expect_toml(request_id, expect)
    _expect_agents_md(request_id, expect)
    return expect


def _parse_request(raw: Any, index: int) -> Request:
    obj = _as_object(raw, f"line {index + 1}")
    _reject_unknown(f"line {index + 1}", obj, REQUEST_KEYS)

    request_id = obj.get("id")
    if not isinstance(request_id, str) or not request_id:
        msg = f"line {index + 1}: 'id' is required and must be a non-empty string"
        raise SpecError(msg)

    dest = obj.get("dest", request_id)
    if not isinstance(dest, str) or not dest:
        msg = f"{request_id}: 'dest' must be a non-empty string"
        raise SpecError(msg)
    dest_path = Path(dest)
    if dest_path.is_absolute() or ".." in dest_path.parts:
        msg = f"{request_id}: 'dest' must stay inside the work dir (got {dest!r})"
        raise SpecError(msg)

    answers_file = obj.get("answers_file")
    if answers_file is not None and not isinstance(answers_file, str):
        msg = f"{request_id}: 'answers_file' must be a string"
        raise SpecError(msg)

    return Request(
        id=request_id,
        index=index,
        note=str(obj.get("note", "")),
        src=str(obj.get("src", str(TOP))),
        ref=str(obj.get("ref", "HEAD")),
        answers=_as_object(obj.get("answers", {}), f"{request_id}: answers"),
        answers_file=answers_file,
        dest=dest,
        update=_parse_update(request_id, obj.get("update")),
        commands=_parse_commands(request_id, obj.get("commands", [])),
        expect=_parse_expect(request_id, obj.get("expect", {})),
    )


def _check_dests(requests: list[Request]) -> None:
    """Every request must own its work dir: no duplicate and no nested dests.

    `run_request` wipes `work / dest` before rendering, so two requests
    sharing a dest -- or one request's dest living inside another's -- would
    have them destroy each other's render. That is a request-list bug, not a
    failing expectation, so it is refused up front; it is also what makes
    `--jobs N` safe to hand each request to its own worker.
    """
    owner: dict[Path, str] = {}
    for request in requests:
        dest = Path(request.dest)
        for other, other_id in owner.items():
            if dest == other or dest in other.parents or other in dest.parents:
                msg = (
                    f"{request.id}: dest {request.dest!r} overlaps {str(other)!r} ({other_id})"
                    " -- each request needs its own work dir"
                )
                raise SpecError(msg)
        owner[dest] = request.id


def load_requests(paths: list[Path]) -> list[Request]:
    """Parse and validate every JSONL file, rejecting duplicate ids and dests."""
    requests: list[Request] = []
    seen: set[str] = set()
    index = 0
    for path in paths:
        for lineno, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = text.strip()
            if not stripped or stripped.startswith("//"):
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as exc:
                msg = f"{path}:{lineno}: invalid JSON: {exc}"
                raise SpecError(msg) from exc
            request = _parse_request(raw, index)
            if request.id in seen:
                msg = f"{path}:{lineno}: duplicate id {request.id!r}"
                raise SpecError(msg)
            seen.add(request.id)
            request.index = index
            requests.append(request)
            index += 1
    if not requests:
        msg = "no requests found"
        raise SpecError(msg)
    _check_dests(requests)
    return requests


def _answers_for(request: Request, phase: dict[str, Any] | None, repo: Path) -> dict[str, Any]:
    """Merge answers_file (base) with inline answers (winning) for one phase."""
    source = phase if phase is not None else request.__dict__
    answers_file = source.get("answers_file", request.answers_file)
    data: dict[str, Any] = {}
    if answers_file:
        path = Path(answers_file)
        if not path.is_absolute():
            path = repo / path
        if not path.is_file():
            msg = f"{request.id}: answers_file not found: {path}"
            raise SpecError(msg)
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        data.update(_as_object(loaded, f"{request.id}: {path}"))
    inline = source.get("answers", request.answers)
    data.update(_as_object(inline, f"{request.id}: answers"))
    return data


def git(where: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git in `where`, capturing output (exit code is the caller's business)."""
    return run_git(where, *args, timeout=DEFAULT_TIMEOUT)


def update_precondition(request: Request) -> Check:
    """An update needs a committed template ref.

    copier commits a dirty local template into its own clone before rendering
    and records that synthetic commit in `.copier-answers.yml`. A later
    `copier update` clones afresh and cannot check that commit out again, so
    an update request from a dirty tree can only ever fail -- better to say so
    before generating anything.
    """
    name = "update-precondition: clean template tree"
    src = Path(request.src)
    if not src.is_dir():
        return Check(name=name, ok=True, detail=f"{request.src} is not a local path; not checked")
    status = git(src, "status", "--porcelain")
    if status.returncode != 0:
        return Check(name=name, ok=False, detail=status.stderr.strip()[-OUTPUT_LIMIT:])
    dirty = [line[3:] for line in status.stdout.splitlines() if line.strip()]
    if dirty:
        detail = f"uncommitted: {', '.join(dirty[:5])} (an update cannot check out copier's synthetic dirty commit)"
        return Check(name=name, ok=False, detail=detail)
    return Check(name=name, ok=True, detail="no uncommitted changes")


def git_snapshot(  # noqa: PLR0913  WHYNOT: dest plus the four git-metadata knobs; a bag object would hide the argv being built.
    dest: Path,
    label: str,
    *,
    message: str = "batch: copy",
    branch: str | None = None,
    user: str = "batch",
    email: str = "batch@example.invalid",
) -> Check:
    """Init, add, and commit `dest` so copier will accept an update of it.

    The one "make this rendered tree updatable" helper: copier only updates
    git-tracked subprojects, and the state both callers replay is the same --
    a user's project right after `copier copy`, i.e. one commit. The commit's
    message, identity and branch name are not part of any contract (copier
    never reads them); they only say who staged the snapshot when a failed
    line's output is being debugged, so callers pass their own.
    """
    init = [GIT, "init", "-q", *(["-b", branch] if branch else [])]
    commands = [
        init,
        [GIT, "add", "-A"],
        [GIT, "-c", f"user.name={user}", "-c", f"user.email={email}", "commit", "-qm", message],
    ]
    for command in commands:
        proc = subprocess.run(  # noqa: S603  WHYNOT: fixed argv, no user input.
            command, cwd=dest, capture_output=True, text=True, check=False, timeout=DEFAULT_TIMEOUT
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()[-OUTPUT_LIMIT:]
            return Check(name=f"{label}: git {' '.join(command[1:3])}", ok=False, detail=detail)
    return Check(name=f"{label}: git snapshot", ok=True)


def render(  # noqa: PLR0913  WHYNOT: a thin wrapper over copier's own 19-parameter API; a bag object would hide the flags that matter.
    src: str,
    dest: Path,
    data: dict[str, Any],
    ref: str = "HEAD",
    *,
    skip_if_exists: tuple[str, ...] = (),
    overwrite: bool = True,
    defaults: bool = True,
    skip_tasks: bool = False,
) -> Worker:
    """Render `src` into `dest` — the one copier `copy` invocation convention.

    Every tool in this repository that renders a project goes through here
    (batch, adopt, cli, mcp_server, update_rehearsal); a direct
    `copier.run_copy` anywhere else breaks the convention, and a guard test
    (tests/test_render_convention.py) fails when one appears. The flags the
    convention pins: `unsafe` (copier's `--trust`, this template's tasks need
    it) and `quiet`. The knobs callers may turn:

    `overwrite=False` turns a collision into an error instead of a
    replacement, which is how tools/adopt.py stays transactional: `skip` (and
    the adopt-mode file-name conditions) should prevent every collision, and
    anything left reaches the caller as an exception it can roll back from.
    `skip_if_exists` redirects collisions instead of failing.

    `defaults=False` lets copier prompt for the questions `data` leaves out --
    how tools/cli.py makes a preset-less run interactive -- instead of taking
    each unset question's default (the pinned-True behaviour everything else
    wants).

    `skip_tasks=True` renders without running the template's post-generation
    tasks -- how update_rehearsal renders, because what it rehearses is the
    merge, not the tasks.

    `copier.update` is a different copier verb, not this function's business:
    its sanctioned direct call sites are this module's update phase and
    tools/update_rehearsal.py, whose subject is the update itself.
    """
    return copier.run_copy(
        src_path=src,
        dst_path=dest,
        data=data,
        vcs_ref=ref,
        unsafe=True,
        defaults=defaults,
        overwrite=overwrite,
        skip_if_exists=skip_if_exists,
        skip_tasks=skip_tasks,
        quiet=True,
    )


def _run_phase(request: Request, dest: Path, repo: Path, phase: dict[str, Any] | None) -> None:
    """Run copier copy, and the requested update on top of it."""
    data = _answers_for(request, None, repo)
    render(request.src, dest, data, request.ref)
    if phase is None:
        return
    snapshot = git_snapshot(dest, request.id)
    if not snapshot.ok:
        msg = f"{request.id}: cannot update: {snapshot.detail}"
        raise SpecError(msg)
    update_data = _answers_for(request, phase, repo)
    conflict: Literal["inline", "rej"] = "rej" if phase.get("conflict") == "rej" else "inline"
    copier.run_update(
        dst_path=dest,
        data=update_data,
        vcs_ref=str(phase.get("ref", request.ref)),
        unsafe=True,
        defaults=True,
        overwrite=True,
        quiet=True,
        conflict=conflict,
    )


def check_files(dest: Path, patterns: list[str]) -> list[Check]:
    """Every glob must match at least one path (directories included)."""
    checks: list[Check] = []
    for pattern in patterns:
        hits = sorted(str(p.relative_to(dest)) for p in dest.glob(pattern))
        checks.append(Check(name=f"files {pattern}", ok=bool(hits), detail=f"matched {hits[:5]}"))
    return checks


def check_absent(dest: Path, patterns: list[str]) -> list[Check]:
    """No glob may match anything."""
    checks: list[Check] = []
    for pattern in patterns:
        hits = sorted(str(p.relative_to(dest)) for p in dest.glob(pattern))
        checks.append(Check(name=f"absent {pattern}", ok=not hits, detail=f"found {hits[:5]}"))
    return checks


def check_matches(dest: Path, entries: list[dict[str, Any]], *, want: bool) -> list[Check]:
    """`want` selects matches (regex found) or unmatches (regex absent)."""
    checks: list[Check] = []
    label = "matches" if want else "unmatches"
    for entry in entries:
        rel = str(entry["path"])
        pattern = str(entry["regex"])
        target = dest / rel
        name = f"{label} {rel} /{pattern}/"
        if not target.is_file():
            checks.append(Check(name=name, ok=False, detail=f"{rel} does not exist"))
            continue
        text = target.read_text(encoding="utf-8", errors="replace")
        found = re.search(pattern, text, re.MULTILINE) is not None
        checks.append(Check(name=name, ok=found is want, detail="found" if found else "not found"))
    return checks


def toml_lookup(data: Any, key: str) -> Any:
    """Walk a dotted key ("tool.ruff.line-length"); integers index lists."""
    current = data
    for segment in key.split("."):
        if isinstance(current, list):
            current = current[int(segment)]
        elif isinstance(current, dict):
            if segment not in current:
                msg = f"missing key {segment!r}"
                raise KeyError(msg)
            current = current[segment]
        else:
            msg = f"cannot descend into {type(current).__name__} at {segment!r}"
            raise KeyError(msg)
    return current


def check_agents_md(dest: Path, entries: list[dict[str, Any]]) -> list[Check]:
    """Ethics-section pins against the generated AGENTS.md.

    Each entry names registry ids under `present`/`absent`; the id resolves
    through the registry to the section's h1 title (the marker the appendix
    renders), so a batch line pins the *rule* rather than repeating a marker
    string that drifts when the prose is reworded.
    """
    sys.path.insert(0, str(TOP))
    from tools import ethics  # noqa: PLC0415 -- deferred: yaml/jinja deps stay lazy

    checks: list[Check] = []
    path = dest / "AGENTS.md"
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    titles = {str(row["id"]): ethics.section_title(row) for row in ethics.load_registry()}
    for entry in entries:
        for key, want in (("present", True), ("absent", False)):
            for section_id in entry.get(key, []):
                title = titles.get(str(section_id))
                name = f"agents_md {key} {section_id}"
                if title is None:
                    checks.append(Check(name=name, ok=False, detail="no such registry row"))
                    continue
                if not title:
                    checks.append(Check(name=name, ok=False, detail="registry row has no h1 title"))
                    continue
                found = title in text
                checks.append(Check(name=name, ok=found is want, detail="found" if found else "not found"))
    return checks


def check_toml(dest: Path, entries: list[dict[str, Any]]) -> list[Check]:
    """Compare values in TOML files by dotted key (integers index lists)."""
    checks: list[Check] = []
    for entry in entries:
        rel = str(entry["path"])
        key = str(entry["key"])
        expected = entry.get("equals")
        name = f"toml {rel}:{key} == {expected!r}"
        target = dest / rel
        if not target.is_file():
            checks.append(Check(name=name, ok=False, detail=f"{rel} does not exist"))
            continue
        try:
            data = tomllib.loads(target.read_text(encoding="utf-8"))
            actual = toml_lookup(data, key)
        except (tomllib.TOMLDecodeError, KeyError, ValueError, IndexError) as exc:
            checks.append(Check(name=name, ok=False, detail=str(exc)))
            continue
        checks.append(Check(name=name, ok=actual == expected, detail=f"actual {actual!r}"))
    return checks


def _judge_single_command(dest: Path, command: dict[str, Any], request_id: str) -> list[Check]:
    """Run one shell command and judge its exit code and regex matchers."""
    run = str(command["run"])
    cwd = dest / str(command.get("cwd", "."))
    timeout = int(command.get("timeout", DEFAULT_TIMEOUT))
    try:
        proc = subprocess.run(  # noqa: S602  WHYNOT: request files are trusted input, like a Makefile.
            run,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return [Check(name=f"{request_id}: run {run!r}", ok=False, detail=f"timeout after {timeout}s")]
    expected_exit = int(command.get("exit", 0))
    output = (proc.stdout or "") + (proc.stderr or "")
    checks = [
        Check(
            name=f"run {run!r} exit {expected_exit}",
            ok=proc.returncode == expected_exit,
            detail=f"exit {proc.returncode}: {output.strip()[-OUTPUT_LIMIT:]}",
        )
    ]
    for key, stream in (("stdout_regex", proc.stdout or ""), ("stderr_regex", proc.stderr or "")):
        if key in command:
            pattern = str(command[key])
            found = re.search(pattern, stream, re.MULTILINE) is not None
            checks.append(
                Check(
                    name=f"run {run!r} {key} /{pattern}/",
                    ok=found,
                    detail=(stream.strip()[-OUTPUT_LIMIT:] if not found else "found"),
                )
            )
    return checks


def check_commands(dest: Path, commands: list[dict[str, Any]], request_id: str) -> list[Check]:
    """Run shell commands in the destination and judge exit code and output."""
    checks: list[Check] = []
    for command in commands:
        checks.extend(_judge_single_command(dest, command, request_id))
    return checks


LINT_TIMEOUT = 300
LINT_COMMANDS: tuple[tuple[str, ...], ...] = (("format", "--check"), ("check",))
"""The generated project's lint recipe: the two ruff invocations its own Taskfile runs."""


def ruff_bin() -> Path:
    """This repository's ruff: the repo venv's, then the interpreter's, then PATH.

    A rendered project has no environment of its own -- that is the point of
    rendering it -- so the lint comes from the venv of whatever process runs
    this module (the MCP server's, a test session's). The repo venv is probed
    first because pytest-xdist workers may run under a different interpreter.
    """
    for candidate in (TOP / ".venv" / "bin" / "ruff", Path(sys.executable).parent / "ruff"):
        if candidate.is_file():
            return candidate
    found = shutil.which("ruff")
    if found:
        return Path(found)
    msg = "ruff not found in TOP/.venv/bin, next to the running interpreter, or on PATH"
    raise FileNotFoundError(msg)


def ruff_checks(dest: Path) -> list[Check]:
    """The ruff verdicts for a rendered tree, or nothing when it cannot be linted.

    Only where the generated lint applies: a render that ships no Python (bare
    workspaces) or no ``[tool.ruff]`` has nothing for it to judge, which is
    what tests/test_generated_lint.py assumes too.
    """
    if not any(dest.rglob("*.py")):
        return []
    pyproject = dest / "pyproject.toml"
    if not pyproject.is_file() or "[tool.ruff" not in pyproject.read_text(encoding="utf-8"):
        return []
    ruff = ruff_bin()
    checks: list[Check] = []
    for args in LINT_COMMANDS:
        proc = subprocess.run(  # noqa: S603  WHYNOT: fixed argv, the render supplies the input.
            [str(ruff), *args, "--no-cache", "."],
            cwd=dest,
            capture_output=True,
            text=True,
            check=False,
            timeout=LINT_TIMEOUT,
        )
        detail = "" if proc.returncode == 0 else (proc.stdout + proc.stderr).strip()[-OUTPUT_LIMIT:]
        checks.append(Check(name=f"ruff {' '.join(args)}", ok=proc.returncode == 0, detail=detail))
    return checks


def junit_verdicts(report: Path) -> tuple[list[LineResult], dict[str, int]]:
    """Turn a pytest JUnit XML report into one LineResult per executed test.

    The verdict machinery behind any "run a pytest tier, return structured
    verdicts" caller (TODO.md §28.3 3e): a failure or error is a failed check
    carrying pytest's message, a skip is an ok check named `skipped`, and the
    counts summarize the run. Line ids are `classname::name`, so they read
    like pytest's own node ids.
    """
    import xml.etree.ElementTree as ET  # noqa: PLC0415  WHYNOT: stdlib; junit parsing only matters to callers that launch pytest.

    lines: list[LineResult] = []
    counts = {"passed": 0, "failed": 0, "skipped": 0}
    # WHYNOT: the report is written by the pytest process the caller launches
    # over a fixed argv; no XML here comes from a peer.
    root = ET.parse(report).getroot()  # noqa: S314
    for index, case in enumerate(root.iter("testcase")):
        failure = case.find("failure") if case.find("failure") is not None else case.find("error")
        skipped = case.find("skipped")
        if failure is not None:
            verdict, name, detail = False, "pytest", (failure.get("message") or failure.text or "").strip()
        elif skipped is not None:
            # A W4 `tier: none` opt-out: not a failure, and not a verified leaf.
            verdict, name, detail = True, "skipped", (skipped.get("message") or "").strip()
        else:
            verdict, name, detail = True, "pytest", ""
        counts["failed" if failure is not None else "skipped" if skipped is not None else "passed"] += 1
        lines.append(
            LineResult(
                id=f"{case.get('classname')}::{case.get('name')}",
                index=index,
                checks=[Check(name=name, ok=verdict, detail=detail[-OUTPUT_LIMIT:])],
                seconds=float(case.get("time") or 0.0),
            )
        )
    return lines, counts


def prepare_command(dest: Path) -> list[str] | None:
    """The package-manager install command for a rendered project.

    Chosen from the files the render produced rather than from the answers:
    whatever the project actually is, this is what installs it.
    """
    if (dest / "pixi.toml").is_file():
        return ["pixi", "install"]
    if (dest / "poetry.lock").is_file():
        return ["poetry", "install"]
    if (dest / "uv.lock").is_file() or (dest / "pyproject.toml").is_file():
        return ["uv", "sync"]
    return None


def prepare_environment(dest: Path, request_id: str) -> Check:
    """Install the rendered project's environment (network on a cold cache)."""
    command = prepare_command(dest)
    if command is None:
        return Check(name=f"{request_id}: prepare", ok=True, detail="nothing to install")
    try:
        proc = subprocess.run(  # noqa: S603  WHYNOT: argv built from a fixed list above.
            command,
            cwd=dest,
            capture_output=True,
            text=True,
            check=False,
            timeout=DEFAULT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Check(name=f"{request_id}: prepare {' '.join(command)}", ok=False, detail=str(exc))
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()[-OUTPUT_LIMIT:]
    return Check(
        name=f"{request_id}: prepare {' '.join(command)}",
        ok=proc.returncode == 0,
        detail=f"exit {proc.returncode}: {output}" if proc.returncode else "installed",
    )


def run_request(request: Request, work: Path, repo: Path, *, prepare: bool = False) -> LineResult:
    """Execute one request end to end and judge its expectations."""
    result = LineResult(id=request.id, index=request.index, note=request.note)
    dest = (work / request.dest).resolve()
    result.dest = str(dest)
    started = time.monotonic()
    try:
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        precondition = update_precondition(request) if request.update is not None else None
        if precondition is not None:
            result.checks.append(precondition)
            if not precondition.ok:
                result.seconds = time.monotonic() - started
                return result
        _run_phase(request, dest, repo, request.update)
        files = sum(1 for path in dest.rglob("*") if path.is_file())
        result.checks.append(Check(name="render", ok=True, detail=f"{files} files"))
        expect = request.expect
        result.checks.extend(check_files(dest, [str(p) for p in expect.get("files", [])]))
        result.checks.extend(check_absent(dest, [str(p) for p in expect.get("absent", [])]))
        result.checks.extend(check_matches(dest, expect.get("matches", []), want=True))
        result.checks.extend(check_matches(dest, expect.get("unmatches", []), want=False))
        result.checks.extend(check_toml(dest, expect.get("toml", [])))
        result.checks.extend(check_commands(dest, request.commands, request.id))
        result.checks.extend(check_agents_md(dest, expect.get("agents_md", [])))
        if prepare and dest.is_dir():
            result.checks.append(prepare_environment(dest, request.id))
    except Exception as exc:  # noqa: BLE001  WHYNOT: a batch runner must report, not abort.
        result.error = f"{type(exc).__name__}: {exc}"
    result.seconds = time.monotonic() - started
    return result


def _run_one(request: Request, work: Path, repo: Path, *, prepare: bool) -> LineResult:
    """Pool entry point: one request in this worker process (see --jobs).

    Module-level so the worker can unpickle it, and the child silences its own
    stdout the same way the serial driver does -- copier and the post-render
    tasks print to fd 1, which would otherwise pollute `--json`.
    """
    with report_stream_only():
        return run_request(request, work, repo, prepare=prepare)


def _run_parallel(  # noqa: PLR0913  WHYNOT: the four options are main's own CLI flags; a bag object would hide them.
    requests: list[Request], work: Path, repo: Path, *, jobs: int, prepare: bool, fail_fast: bool
) -> list[LineResult]:
    """Run requests in `jobs` worker processes, reporting in request order."""
    slots: list[LineResult | None] = [None] * len(requests)
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        pending: dict[Future[LineResult], int] = {}
        queue = iter(enumerate(requests))
        stop = False

        def start_more() -> None:
            """Keep `jobs` requests in flight, never starting past a failure."""
            for position, request in queue:
                pending[pool.submit(_run_one, request, work, repo, prepare=prepare)] = position
                if len(pending) >= jobs:
                    return

        start_more()
        while pending:
            finished, _ = wait(list(pending), return_when=FIRST_COMPLETED)
            for future in finished:
                position = pending.pop(future)
                result = future.result()
                slots[position] = result
                if fail_fast and not result.ok:
                    stop = True
            if not stop:
                start_more()

    return [result for result in slots if result is not None]


def run_requests(  # noqa: PLR0913  WHYNOT: the four options are main's own CLI flags; a bag object would hide them.
    requests: list[Request],
    work: Path,
    repo: Path,
    *,
    jobs: int = 1,
    prepare: bool = False,
    fail_fast: bool = False,
) -> list[LineResult]:
    """Run every request and return the verdicts in request order.

    `jobs` is the number of requests in flight: 1 keeps the original serial
    behaviour (and its exact `--fail-fast` stop point); higher values spread
    them over worker processes, which is what makes a whole-file batch usable --
    see the `--jobs` notes in the module docstring, including why the worker
    is a process rather than a thread.
    """
    if jobs <= 1 or len(requests) == 1:
        results: list[LineResult] = []
        for request in requests:
            result = run_request(request, work, repo, prepare=prepare)
            results.append(result)
            if fail_fast and not result.ok:
                break
        return results
    return _run_parallel(requests, work, repo, jobs=min(jobs, len(requests)), prepare=prepare, fail_fast=fail_fast)


def _print_human(results: list[LineResult], work: Path) -> None:
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        failed = sum(1 for check in result.checks if not check.ok)
        counts = f"{len(result.checks) - failed}/{len(result.checks)} checks" if result.checks else "no checks"
        print(f"{status} {result.id:<32} {counts:>14}  {result.seconds:5.1f}s")
        if not result.ok and result.note:
            print(f"     note: {result.note}")
        if result.error:
            print(f"     error: {result.error}")
        for check in result.checks:
            if not check.ok:
                print(f"     - {check.name}: {check.detail}")
    failed_lines = [r for r in results if not r.ok]
    print()
    if failed_lines:
        names = ", ".join(r.id for r in failed_lines)
        print(f"{len(results) - len(failed_lines)} passed, {len(failed_lines)} failed: {names}")
    else:
        print(f"{len(results)} passed")
    print(f"work dir: {work}")


@contextlib.contextmanager
def report_stream_only() -> Generator[None]:
    """Send everything written to fd 1 to stderr for the duration.

    Copier and the post-generation tasks it runs print progress to stdout --
    including from child processes, which a Python-level redirect cannot
    catch. The runner's own report is the only thing that belongs on stdout
    (so `--json | jq` sees JSON and nothing else); diagnostics belong on
    stderr, where they interleave harmlessly with the human report.
    """
    saved = os.dup(1)
    try:
        os.dup2(2, 1)
        yield
    finally:
        os.dup2(saved, 1)
        os.close(saved)


def open_shell(dest: Path) -> None:
    """Hand the terminal to an interactive shell inside the rendered project."""
    shell = os.environ.get("SHELL") or "/bin/sh"
    print(f"\nshell in {dest} (exit to leave)", file=sys.stderr)
    subprocess.run([shell], cwd=dest, check=False, timeout=None)  # noqa: S603


def _jobs(value: str) -> int:
    """`--jobs N`: N >= 1, or argparse reports the bad value."""
    try:
        count = int(value)
    except ValueError as exc:
        msg = f"--jobs: {value!r} is not an integer"
        raise argparse.ArgumentTypeError(msg) from exc
    if count < 1:
        msg = "--jobs must be at least 1"
        raise argparse.ArgumentTypeError(msg)
    return count


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a JSONL batch of copier requests and verdict them.")
    parser.add_argument("jsonl", nargs="+", type=Path, help="JSONL request file(s), executed in order")
    parser.add_argument("--repo", type=Path, default=TOP, help="repository the answers_file paths are relative to")
    parser.add_argument("--work", type=Path, default=None, help="work dir for generated projects (default: a temp dir)")
    parser.add_argument("--only", default=None, help="regex: run only requests whose id matches")
    parser.add_argument(
        "--jobs",
        type=_jobs,
        default=1,
        metavar="N",
        help=(
            "run up to N requests concurrently (default 1: serial, in file order). Results stay in JSONL order; "
            "rendering is not thread-safe (copier chdirs), so the workers are processes. See the module docstring"
        ),
    )
    parser.add_argument("--keep", action="store_true", help="keep the work dir (default: delete it on success)")
    parser.add_argument(
        "--prepare", action="store_true", help="install each rendered project's environment (implies --keep)"
    )
    parser.add_argument(
        "--shell", action="store_true", help="after the run, open a shell in the last rendered project (implies --keep)"
    )
    parser.add_argument("--fail-fast", action="store_true", help="stop at the first failing request")
    parser.add_argument("--json", action="store_true", help="print a machine-readable verdict instead of text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: parse, run, report. Returns the process exit code."""
    args = _parse_args(argv)
    try:
        requests = load_requests(args.jsonl)
    except (SpecError, OSError) as exc:
        print(f"invalid request list: {exc}", file=sys.stderr)
        return 2

    if args.only:
        pattern = re.compile(args.only)
        requests = [r for r in requests if pattern.search(r.id)]
        if not requests:
            print(f"no request id matches {args.only!r}", file=sys.stderr)
            return 2

    if args.shell:
        args.keep = True
    owned_work = args.work is None
    work = args.work or Path(tempfile.mkdtemp(prefix="copier-batch-"))
    work.mkdir(parents=True, exist_ok=True)

    with report_stream_only():
        results = run_requests(
            requests, work, args.repo, jobs=args.jobs, prepare=args.prepare, fail_fast=args.fail_fast
        )

    if args.json:
        payload = {
            "ok": all(r.ok for r in results),
            "work": str(work),
            "lines": [r.as_dict() for r in results],
        }
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        _print_human(results, work)

    if owned_work and not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    elif args.shell and results:
        open_shell(Path(results[-1].dest))
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
