r"""The render inputs, and the fingerprints that identify one tree state.

A copier render is a pure function of the answers and the template tree, so the
tree state can be named by a content digest instead of a git revision: copier
renders a *dirty* working tree as it finds it (it warns `DirtyLocalWarning`),
which is exactly what the tests and the MCP tools want to key on.

This module owns the render's file-level vocabulary, so the consumers cannot
drift apart (TODO.md §28.3 3c / §28.5 R3): the test suite's on-disk render
cache (`tests/render_cache.py`, which namespaces its entries and records the
consumed inputs) and the render twin (`tools/render_delta.py`, which narrows
the re-render candidates) both read the watched-path list, the include graph
and the output-name rule from here, and the repo MCP server's
`template_fingerprint()` tool reports the digest to an agent deciding whether
the render it holds is stale.

What is covered: every file under `template/` and `_shared/`, plus `copier.yml`
and `_tasks.jinja`, as `sha256(relative path + \\0 + sha256(content))` over the
sorted paths. Symlinks are followed, because copier follows them
(`preserve_symlinks` is off): the template's payload links
(`template/.vscode -> ../.vscode`, `template/.../tests/conftest.py -> the repo's
tests/conftest.py`, ...) put the *linked* bytes into the render, so editing
either side of a link must change the digest. `Path.rglob` does not descend a
symlinked directory and a trailing `**` matches directories rather than the
files inside them, so directory links are queued explicitly; the queue is keyed
on resolved paths, so a link pointing back into a tree already walked cannot
loop.

The answers half of a render's inputs has its own fingerprint
(`context_fingerprint`): `copier.yml`, `questions/*.yml` and the witness leaf
list -- what a leaf's render context depends on when the template body does
not.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

TOP = Path(__file__).resolve().parent.parent


def digest_bytes(data: bytes) -> str:
    """The sha256 hex digest of `data` (the one byte-hash every manifest uses)."""
    return hashlib.sha256(data).hexdigest()


def _yaml_error_details(error: Exception) -> str:
    """The one-line detail for a YAML failure (message without the mark context)."""
    text = str(error).strip().splitlines()
    return text[0] if text else type(error).__name__


def read_yaml_mapping(path: Path) -> dict[str, Any]:
    """The YAML mapping at `path`, or a loud error naming it.

    The one "read a YAML file that must hold a mapping" helper: every preset
    reader, answers-file reader and support/manifest loader routes through it,
    so a missing file, unparsable YAML and a non-mapping payload fail the same
    way. Raises the builtin `FileNotFoundError`/`ValueError` subclasses the
    callers already catch -- never a new error type -- so the callers' except
    clauses only move, never change meaning.
    """
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        msg = f"{path} is not valid YAML: {_yaml_error_details(error)}"
        raise ValueError(msg) from error
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        msg = f"{path} is not a mapping"
        raise TypeError(msg)
    return loaded


RENDER_INPUT_DIRS = ("template", "_shared")
"""The trees a render expands: every file under them is a render input."""

RENDER_INPUT_FILES = ("copier.yml", "_tasks.jinja")
"""The questions, defaults, `_exclude` patterns and task list that steer it."""

INCLUDE_TAG = re.compile(r'\{%-?\s+(?:include|import)\s+"([^"]+)"')
"""The include/import tags whose target the graph can attribute: a plain
double-quoted literal. A dynamic target (`{% include some_var %}`) renders
fine but resolves to nothing here; tests/test_machine_gate.py keeps the render
inputs free of them rather than teaching this regex expressions."""

CONTEXT_HASH_SCHEME = "answers-only-v1"
"""Bumped when the context-fingerprint recipe changes, so caches written under
the old recipe are never served under the new one -- the same clean break
tests/render_cache.py's CACHE_SCHEME performs for the template side. The name
records what the hashed contexts are: copier's answers without the
underscore-prefixed plumbing."""


def render_input_paths(root: Path = TOP) -> list[Path]:
    """Every file a render reads under `root`, sorted by relative path."""
    inputs: list[Path] = []
    walked: set[Path] = set()
    queue = [root / name for name in RENDER_INPUT_DIRS]
    while queue:
        directory = queue.pop()
        real = directory.resolve()
        if real in walked:
            continue
        walked.add(real)
        for path in directory.rglob("*"):
            if path.is_dir():
                if path.is_symlink():
                    queue.append(path)
            elif path.is_file():
                inputs.append(path)
    inputs += [root / name for name in RENDER_INPUT_FILES if (root / name).is_file()]
    return sorted(inputs)


def render_fingerprint(root: Path = TOP) -> tuple[str, int, int]:
    """`(digest, path count, total bytes)` of `root`'s render inputs.

    Sorted paths make the digest independent of directory iteration order, and
    the counts let a caller report what it hashed.
    """
    digest = hashlib.sha256()
    total = 0
    paths = render_input_paths(root)
    for path in paths:
        body = path.read_bytes()
        total += len(body)
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(body).digest())
    return digest.hexdigest(), len(paths), total


def watched_relative_paths(root: Path = TOP) -> list[str]:
    """Every render input, as a root-relative POSIX path (the watched-file key).

    This is the key format every consumer compares by: a manifest entry, an
    include-graph node, a `{% include %}` target all name watched files this
    way. The same symlink descent as `render_input_paths`, for the same
    reason -- the linked bytes are render inputs, so the link's contents are
    watched files.
    """
    return [path.relative_to(root).as_posix() for path in render_input_paths(root)]


def resolve_include_target(target: str, watched: set[str]) -> str | None:
    """An include tag's target, resolved against the watched files.

    Include tags are repo-root-relative ("_shared/x.jinja" from a file in
    template/), so the raw target matches a watched file only when the file
    lives at that level; the suffix fallback covers tags written relative to
    the including file. None = the target names nothing we watch.
    """
    if target in watched:
        return target
    matches = [path for path in watched if path.endswith("/" + target)]
    return matches[0] if len(matches) == 1 else None


def include_graph(root: Path = TOP) -> dict[str, set[str]]:
    """template-side file -> the files it pulls in via literal include/import tags.

    Only watched files are nodes (a tag naming an unwatched file resolves to
    nothing), and only literal targets are edges -- see INCLUDE_TAG. Consumers
    close this graph in their own direction: the render cache forward (the
    bytes a render consumed), the render twin backward (the leaves a changed
    byte can reach).
    """
    graph: dict[str, set[str]] = {}
    watched = set(watched_relative_paths(root))
    for rel in watched:
        if not rel.endswith((".jinja", ".yml")):
            continue
        text = (root / rel).read_text(encoding="utf-8")
        for match in INCLUDE_TAG.finditer(text):
            resolved = resolve_include_target(match.group(1), watched)
            if resolved is not None:
                graph.setdefault(rel, set()).add(resolved)
    return graph


def output_name(template_rel: str) -> str:
    """The destination name a template path renders to, tags and `.jinja` stripped.

    The leading `template/` directory (copier's `_subdirectory`) strips out
    too, so the name is what appears in the rendered tree. `{{ pkg_dir }}`
    interpolations strip out as well, so the comparison to manifest keys is
    by suffix: over-inclusive on collisions, the safe direction for any
    "could this template file have produced that output" rule.
    """
    stripped = re.sub(r"{%.*?%}|{{.*?}}|{#.*?#}", "", template_rel)
    stripped = stripped.removeprefix("template/")
    return stripped.removesuffix(".jinja") if stripped.endswith(".jinja") else stripped


def context_fingerprint(root: Path = TOP) -> str:
    """Digest of what a leaf's render context depends on besides the template body.

    `copier.yml`, `questions/*.yml` and the witness leaf list: the context is
    a function of the questionnaire and the answers, so a template body edit
    must not invalidate a context cache. ``CONTEXT_HASH_SCHEME`` heads the
    digest so a recipe change is a clean break instead of two definitions
    mixing in one cache directory.

    The one context-cache key of the repository -- tools/answers_for.py's
    context pass and tools/render_delta.py's per-leaf context hashes both
    name their caches by it, so they cannot disagree about staleness.
    """
    parts = [root / "copier.yml", root / "tests" / "matrix" / "witnesses.jsonl"]
    parts += sorted((root / "questions").glob("*.yml"))
    digest = hashlib.sha256()
    digest.update(CONTEXT_HASH_SCHEME.encode())
    digest.update(b"\0")
    for path in parts:
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
