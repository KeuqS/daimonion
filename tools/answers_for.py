#!/usr/bin/env python3
"""The inverse template: name the features you want, get the answers that produce them.

Templates make users answer 60+ questions. This repo already *verifies* the
answer->artifact correspondence mechanically -- the 272 witness leaves in
tests/matrix/witnesses.jsonl (each a full answer set), the per-leaf render
contexts (copier's own questionnaire pass, the tools/predicates.py oracle) and
tests/matrix/invariants.yml claiming which artifacts each configuration ships.
The inverse mapping is therefore available without guessing: given the
features you WANT, find the answers that produce them. This module is that
mapping, v1: exact match over the leaf space, with honest diagnostics.

**Constraints** (the language, deliberately tiny):

    name=value   the question or internal whose context value equals the
                 string (booleans also accept `name=true` / `name=false`)
    name         the value must be truthy
    -name        the value must be falsy
    name!=value  the value must not equal the string

Mixed forms (`-name=value`, `-name!=value`) are refused: the negation of an
equality is spelled `name!=value`.

A name may be an asked question (`docker`, `docs_type`, `project_type`, ...)
or a derived internal (`mcp_effective`, `sphinx`, `use_gpu_effective`,
`license_effective`, ...) -- whatever the render context exposes, minus
copier's private plumbing (`_`-prefixed) and the render clock (`now`). An
unknown name is rejected with the closest real names suggested (difflib).

**Matching**: every leaf whose context satisfies all constraints is reported
with its id, its full answers as YAML ready for `copier copy --data-file`,
and the artifacts its class ships (tests/matrix/invariants.yml via
tools/invariants.py). When nothing matches, the report says so loudly: which
constraint eliminated the most leaves, and the nearest leaf by satisfied
constraints, with what it misses. Never a silent empty result.

**The render proof** (`--render`): the top matching leaf is rendered through
tools/batch.py (one request -- the same run a witness gets, post-generation
tasks and `expect` checks included), and every constraint is then proved
against the rendered tree twice over: the render's own `.copier-answers.yml`
drives a fresh copier pass whose context must satisfy each constraint (the
general proof), and where an internal ships a name-gated artifact
(``ARTIFACT_PROOFS``) or the license lands in pyproject.toml, the file itself
must agree. The render is the proof the answers are real.

The render contexts are cached under `.cache/answers-for/`, keyed by
tools/render_inputs.py's `context_fingerprint` (copier.yml + questions/*.yml +
witnesses.jsonl, scheme-tagged) -- the same key tools/render_delta.py names its
context hashes by -- so a template body edit never re-runs the pass; only a
questionnaire or leaf-list change does.

Usage:

    python tools/answers_for.py --require docs_type=zensical --require use_gpu_effective=true
    python tools/answers_for.py --require docker=true --render --keep
    python tools/answers_for.py --require license=MIT --json

Exit codes: 0 a leaf matched (and, with --render, the proof held);
1 no leaf matched, or the render proof failed; 2 a constraint is malformed
or names something the questionnaire never produces.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:  # tools/ is no root package (pyproject.toml)
    sys.path.insert(0, str(TOP))

from tools import batch  # noqa: E402
from tools import invariants  # noqa: E402
from tools import predicates  # noqa: E402
from tools.render_inputs import context_fingerprint  # noqa: E402
from tools.render_inputs import read_yaml_mapping  # noqa: E402

#: Where the render contexts are cached (see the module docstring for the key).
CACHE = TOP / ".cache" / "answers-for"

#: Context entries a constraint may not address: copier's private plumbing is
#: not questionnaire state, and `now` is the render clock, not an answer.
UNCONSTRAINABLE = frozenset({"now"})

#: Boolean internals whose render ships a name-gated artifact: name -> the
#: render-relative path that exists iff the internal is true. This is the
#: artifact half of the render proof; every other constraint is still proved
#: by the fresh copier pass over the render's own recorded answers.
ARTIFACT_PROOFS: dict[str, str] = {
    "docker": ".dockerignore",
    "docs": "docs",
    "mcp_effective": ".mcp.json",
    "sphinx": "docs/conf.py",
    "use_gpu_effective": "Dockerfile.gpu",
    "zensical": "zensical.toml",
}

#: The `license = "..."` line the rendered pyproject.toml carries (from
#: `license_effective`), the artifact proof for a license constraint.
LICENSE_LINE = re.compile(r'^license\s*=\s*"([^"]*)"', re.MULTILINE)


class ConstraintError(ValueError):
    """A malformed constraint, or a name the questionnaire never produces."""


@dataclass(frozen=True)
class Constraint:
    """One parsed constraint token.

    ``value is None`` is the truthiness form (`name` / `-name`); otherwise the
    equality form (`name=value` / `name!=value`), with ``negated`` saying
    which. ``raw`` is the token as given, for reports.
    """

    raw: str
    name: str
    negated: bool
    value: str | None


@dataclass(frozen=True)
class _Recorded:
    """A rendered project's recorded answers, shaped like a leaf for the oracle pass.

    Structurally a ``predicates.LeafLike`` (the oracle's own contract): a
    recorded render is not a questionnaire leaf, but the pass neither knows
    nor cares -- `id` and `answers` are all it reads.
    """

    id: str
    answers: dict[str, Any]


def parse_constraints(tokens: list[str], known: frozenset[str]) -> list[Constraint]:
    """Parse constraint tokens, rejecting unknown names with the closest real ones."""
    return [_parse_token(token, known) for token in tokens]


def _parse_token(token: str, known: frozenset[str]) -> Constraint:
    """One token -> one Constraint, or `ConstraintError` naming the problem."""
    text = token.strip()
    if not text:
        msg = "empty constraint (expected name, name=value, -name or name!=value)"
        raise ConstraintError(msg)
    negated = text.startswith("-")
    body = text[1:] if negated else text
    if negated and "!=" in body:
        msg = f"{token}: -name!=value is ambiguous -- write name!=value"
        raise ConstraintError(msg)
    if negated and "=" in body:
        msg = f"{token}: -name=value is ambiguous -- write name!=value"
        raise ConstraintError(msg)
    if "!=" in body:
        name, _, value = body.partition("!=")
        negated = True
    elif "=" in body:
        name, _, value = body.partition("=")
    else:
        name, value = body, None
    name = name.strip()
    if not name:
        msg = f"{token}: no name before '='"
        raise ConstraintError(msg)
    if value is not None and not value.strip():
        msg = f"{token}: no value after '='"
        raise ConstraintError(msg)
    if name not in known:
        close = difflib.get_close_matches(name, sorted(known), n=3, cutoff=0.6)
        suffix = f"; did you mean {', '.join(repr(n) for n in close)}?" if close else ""
        msg = f"unknown name {name!r} in {token!r} -- constraints may name any question or internal{suffix}"
        raise ConstraintError(msg)
    return Constraint(raw=token, name=name, negated=negated, value=None if value is None else value.strip())


def satisfied(constraint: Constraint, context: dict[str, Any]) -> bool:
    """Whether one render context satisfies one constraint."""
    if constraint.value is None:
        result = bool(context.get(constraint.name))
    else:
        result = _equals(context.get(constraint.name), constraint.value)
    return not result if constraint.negated else result


def _equals(observed: Any, value: str) -> bool:
    """The `name=value` comparison: string equality, with booleans read from true/false.

    A boolean context value only matches the (case-insensitive) words -- any
    other text against a boolean is a non-match, not a silent `str(True)`.
    """
    if isinstance(observed, bool):
        return value.lower() in ("true", "false") and observed == (value.lower() == "true")
    if observed is None:
        return False
    return str(observed) == value


def _observed(context: dict[str, Any], name: str) -> str:
    """A context value as a report shows it (`true`, `false`, the string, `<unset>`)."""
    value = context.get(name)
    if value is None:
        return "<unset>"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def load_witnesses(root: Path = TOP) -> list[batch.Request]:
    """The 272 leaves, as the validated batch requests the render proof reuses."""
    return batch.load_requests([root / "tests" / "matrix" / "witnesses.jsonl"])


def context_key(root: Path) -> str:
    """The cache key: the questionnaire and the leaf list, and nothing else.

    `tools/render_inputs.py`'s `context_fingerprint` is the one implementation
    (scheme-tagged), shared with tools/render_delta.py's context-hash key:
    contexts are a function of copier.yml, questions/ and the witnesses'
    answers, so a template body edit must not retrigger the pass.
    """
    return context_fingerprint(root)


def load_contexts(root: Path = TOP) -> dict[str, dict[str, Any]]:
    """Leaf id -> the full render context, copier's pass run once and cached.

    The pass costs ~25s over the 272 leaves (a real `Worker._ask` per leaf),
    so the contexts live under `.cache/answers-for/contexts/` keyed by
    ``context_key``; a hit is served from disk, a miss (questionnaire or
    witnesses moved) runs the oracle pass once and rewrites the cache.
    """
    cache_dir = CACHE / "contexts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{context_key(root)}.json"
    requests = load_witnesses(root)
    if cache_path.is_file():
        loaded = json.loads(cache_path.read_text(encoding="utf-8"))
        if set(loaded) == {request.id for request in requests}:
            return loaded
    contexts = {leaf.id: context for leaf, context, _env in predicates.leaf_contexts(requests)}
    cache_path.write_text(json.dumps(contexts, indent=1, sort_keys=True, default=repr), encoding="utf-8")
    return contexts


def known_names(contexts: dict[str, dict[str, Any]]) -> frozenset[str]:
    """Every name a constraint may address: questions and internals, not copier plumbing."""
    names: set[str] = set()
    for context in contexts.values():
        names.update(name for name in context if not name.startswith("_") and name not in UNCONSTRAINABLE)
    return frozenset(names)


def match(
    constraints: list[Constraint], contexts: dict[str, dict[str, Any]]
) -> tuple[list[str], dict[str, Any] | None]:
    """(matching leaf ids in id order, the no-match diagnostic or None)."""
    matching = [
        leaf_id
        for leaf_id in sorted(contexts)
        if all(satisfied(constraint, contexts[leaf_id]) for constraint in constraints)
    ]
    return matching, None if matching else _diagnose(constraints, contexts)


def _diagnose(constraints: list[Constraint], contexts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Why nothing matched: the biggest eliminator, and the nearest leaf.

    "Nearest" is the leaf satisfying the most constraints (ties broken by id
    order), reported with the constraints it misses and the values it has --
    the difference between the asker's intent and the nearest real branch of
    the questionnaire.
    """
    rows: list[dict[str, Any]] = [
        {
            "constraint": constraint.raw,
            "failed": sum(1 for ctx in contexts.values() if not satisfied(constraint, ctx)),
        }
        for constraint in constraints
    ]
    rows.sort(key=lambda row: -row["failed"])
    eliminated = rows

    def score(leaf_id: str) -> int:
        return sum(1 for constraint in constraints if satisfied(constraint, contexts[leaf_id]))

    nearest = max(sorted(contexts), key=score)
    misses = [
        {"constraint": constraint.raw, "observed": _observed(contexts[nearest], constraint.name)}
        for constraint in constraints
        if not satisfied(constraint, contexts[nearest])
    ]
    return {
        "eliminated": eliminated,
        "nearest": {"leaf": nearest, "satisfied": score(nearest), "of": len(constraints), "misses": misses},
    }


def answers_yaml(answers: dict[str, Any]) -> str:
    """A leaf's answers as the YAML a `copier copy --data-file` takes."""
    return yaml.safe_dump(dict(sorted(answers.items())), sort_keys=False)


def _format_matching_leaf_records(
    matching: list[str], root: Path, matrix: invariants.Invariants, limit: int | None
) -> list[dict[str, Any]]:
    """Format the matching leaf records with answers, yaml snippet, and expected files."""
    leaves = []
    for leaf_id in matching[: limit if limit is not None else None]:
        request = _request_for(leaf_id, root)
        expect = matrix.expect_for(request.answers)
        leaves.append(
            {
                "id": leaf_id,
                "answers": request.answers,
                "answers_yaml": answers_yaml(request.answers),
                "ships": list(expect["files"]),
                "absent": list(expect["absent"]),
            }
        )
    return leaves


def recommend(
    tokens: list[str],
    *,
    render: bool = False,
    keep: bool = False,
    limit: int | None = None,
    root: Path = TOP,
) -> dict[str, Any]:
    """The whole feature: constraint tokens in, matching leaves out.

    Shared by the CLI and the MCP tool. Parses the tokens against the cached
    contexts' namespace, filters the leaf space exactly, and (with `render`)
    proves the top match by rendering it. `limit` caps the reported leaves
    (`matched` stays the full count). Raises `ConstraintError` on a malformed
    or unknown-name token; everything else is reported in the payload.
    """
    contexts = load_contexts(root)
    constraints = parse_constraints(tokens, known_names(contexts))
    matching, diagnostic = match(constraints, contexts)
    matrix = invariants_load(root)
    leaves = _format_matching_leaf_records(matching, root, matrix, limit)
    payload: dict[str, Any] = {
        "constraints": [constraint.raw for constraint in constraints],
        "matched": len(matching),
        "shown": len(leaves),
        "leaves": leaves,
        "diagnostic": diagnostic,
        "render": None,
    }
    if render and matching:
        payload["render"] = prove_render(_request_for(matching[0], root), constraints, root, keep=keep)
    return payload


def _request_for(leaf_id: str, root: Path) -> batch.Request:
    """The committed witness request for one leaf id (the render proof reuses it verbatim)."""
    return next(request for request in load_witnesses(root) if request.id == leaf_id)


def invariants_load(root: Path = TOP) -> invariants.Invariants:
    """The leaf-class matrix, read from the one file that owns it."""
    return invariants.load(root / "tests" / "matrix" / "invariants.yml")


def _verify_rendered_constraints(
    dest: Path, leaf_id: str, constraints: list[Constraint]
) -> tuple[list[dict[str, Any]], bool, str | None]:
    """Verify constraint list against context derivation and artifact existence."""
    answers_file = dest / ".copier-answers.yml"
    if not answers_file.is_file():
        return [], False, f"the render recorded no {answers_file.name}; nothing to prove against"
    recorded = read_yaml_mapping(answers_file)
    clean = {name: value for name, value in recorded.items() if not name.startswith("_")}
    context = next(iter(predicates.leaf_contexts([_Recorded(leaf_id, clean)])))[1]
    checks = []
    for constraint in constraints:
        kind, artifact_ok, detail = artifact_proof(constraint, dest)
        checks.append(
            {
                "constraint": constraint.raw,
                "context_ok": satisfied(constraint, context),
                "artifact": kind,
                "artifact_ok": artifact_ok,
                "detail": detail,
            }
        )
    ok = all(check["context_ok"] for check in checks) and all(check["artifact_ok"] for check in checks)
    return checks, ok, None


def prove_render(
    request: batch.Request, constraints: list[Constraint], root: Path = TOP, *, keep: bool = False
) -> dict[str, Any]:
    """Render one leaf through batch and prove every constraint against the tree.

    Two independent proofs per constraint: *context* -- the render's own
    `.copier-answers.yml` drives a fresh copier pass, and the constraint must
    hold on the context those answers produce (the general proof, every
    constraint gets it); *artifact* -- where the internal ships a name-gated
    file (`ARTIFACT_PROOFS`) or the license lands in pyproject.toml, the
    rendered file itself must agree. The batch run is the ordinary witness
    render (post-generation tasks and the leaf's `expect` checks included),
    so `ok` folds all three layers together.
    """
    work = Path(tempfile.mkdtemp(prefix="answers-for-"))
    started = time.monotonic()
    entry: dict[str, Any] = {
        "leaf": request.id,
        "dest": None,
        "seconds": 0.0,
        "ok": False,
        "batch": None,
        "constraints": [],
        "error": None,
    }
    try:
        with batch.report_stream_only():
            (result,) = batch.run_requests([request], work, root)
        dest = Path(result.dest)
        entry.update(
            {
                "dest": str(dest) if keep else None,
                "ok": result.ok,
                "batch": result.as_dict(),
                "error": result.error,
            }
        )
        checks, ok, error = _verify_rendered_constraints(dest, request.id, constraints)
        entry["constraints"] = checks
        if error:
            entry["error"] = error
            entry["ok"] = False
        else:
            entry["ok"] = bool(entry["ok"] and ok)
        return entry
    finally:
        entry["seconds"] = round(time.monotonic() - started, 3)
        if not keep:
            shutil.rmtree(work, ignore_errors=True)


def artifact_proof(constraint: Constraint, dest: Path) -> tuple[str | None, bool, str]:
    """The artifact half of the proof: (kind, ok, detail); kind None = none registered."""
    if constraint.name in ARTIFACT_PROOFS and constraint.value in (None, "true", "false", "True", "False"):
        relative = ARTIFACT_PROOFS[constraint.name]
        exists = (dest / relative).exists()
        want = not constraint.negated if constraint.value is None else constraint.value.lower() == "true"
        verdict = "holds" if exists is want else "contradicts"
        return (
            "artifact",
            exists is want,
            f"{relative} {'exists' if exists else 'absent'} -- want {'present' if want else 'absent'}: {verdict}",
        )
    if constraint.name in ("license", "license_effective") and constraint.value is not None:
        pyproject = dest / "pyproject.toml"
        if not pyproject.is_file():
            return "artifact", False, "pyproject.toml absent -- no license line to check"
        found = LICENSE_LINE.search(pyproject.read_text(encoding="utf-8"))
        observed = found.group(1) if found else None
        agree = observed == constraint.value
        return (
            "artifact",
            agree is not constraint.negated,
            f"pyproject license = {observed!r}, want {constraint.value!r}: "
            + ("holds" if agree is not constraint.negated else "contradicts"),
        )
    return None, True, ""


def prose(payload: dict[str, Any]) -> str:
    """The human report (stderr): every match with its YAML, or the diagnostic."""
    total = len(load_witnesses())
    lines = [
        f"answers-for: {payload['matched']} of {total} leaves match "
        + ", ".join(repr(constraint) for constraint in payload["constraints"])
    ]
    if payload["matched"] == 0:
        return "\n".join([*lines, *_prose_diagnostic(payload["diagnostic"], total)])
    for leaf in payload["leaves"]:
        lines.extend(_prose_leaf(leaf))
    if payload["shown"] < payload["matched"]:
        lines.append(f"  ... {payload['matched'] - payload['shown']} more matching leaves (--top to show fewer)")
    proof = payload["render"]
    if proof is not None:
        lines.extend(_prose_proof(proof))
    return "\n".join(lines)


def _prose_diagnostic(diagnostic: dict[str, Any], total: int) -> list[str]:
    """The no-match half of the prose: the eliminators and the nearest leaf."""
    top = diagnostic["eliminated"][0]
    lines = [f"  nothing matches -- {top['constraint']!r} alone eliminates {top['failed']} of {total} leaves"]
    lines.extend(f"    {entry['constraint']!r} eliminates {entry['failed']}" for entry in diagnostic["eliminated"][1:])
    nearest = diagnostic["nearest"]
    lines.append(f"  nearest leaf: {nearest['leaf']} (satisfies {nearest['satisfied']}/{nearest['of']})")
    lines.extend(f"    misses {miss['constraint']!r}: the leaf has {miss['observed']}" for miss in nearest["misses"])
    return lines


def _prose_leaf(leaf: dict[str, Any]) -> list[str]:
    """One matching leaf: its id, its ships, its answers as a --data-file YAML block."""
    lines = [
        f"  {leaf['id']}",
        f"    ships {len(leaf['ships'])}: {', '.join(leaf['ships'])}",
    ]
    if leaf["absent"]:
        lines.append(f"    absent: {', '.join(leaf['absent'])}")
    lines.append("    answers (copier copy --data-file <file> --defaults):")
    lines.extend(f"      {line}" for line in leaf["answers_yaml"].splitlines())
    return lines


def _prose_proof(proof: dict[str, Any]) -> list[str]:
    """The render-proof half of the prose: the verdict per constraint, plus batch failures."""
    lines = [f"  render proof ({proof['seconds']}s): {'PASS' if proof['ok'] else 'FAIL'} -- leaf {proof['leaf']}"]
    for check in proof["constraints"]:
        artifact = f"; {check['artifact']}: {check['detail']}" if check["artifact"] else ""
        lines.append(
            f"    {check['constraint']}: context {'holds' if check['context_ok'] else 'CONTRADICTS'}{artifact}"
        )
    failed = [c for c in (proof["batch"] or {}).get("checks", []) if not c["ok"]]
    lines.extend(f"    batch check failed: {c['name']}: {c['detail']}" for c in failed)
    if proof["error"]:
        lines.append(f"    error: {proof['error']}")
    if proof["dest"]:
        lines.append(f"    kept at {proof['dest']}")
    return lines


def main(argv: list[str] | None = None) -> int:
    """Entry point: parse constraints, match the leaf space, report (prose on stderr)."""
    parser = argparse.ArgumentParser(
        description="The inverse template: find the witness answers that produce the features you name.",
        epilog="constraint forms: name | name=value | -name | name!=value (name: any question or internal)",
    )
    parser.add_argument(
        "--require",
        action="append",
        required=True,
        metavar="CONSTRAINT",
        help="a constraint a leaf's render context must satisfy; repeat for more",
    )
    parser.add_argument("--render", action="store_true", help="render the top match and prove the constraints on it")
    parser.add_argument(
        "--keep", action="store_true", help="with --render: keep the rendered project and report its dir"
    )
    parser.add_argument(
        "--top", type=int, default=None, metavar="N", help="report at most N matching leaves (all by default)"
    )
    parser.add_argument("--json", action="store_true", help="print the machine report to stdout (pure)")
    args = parser.parse_args(argv)
    if args.top is not None and args.top < 0:
        parser.error("--top must be >= 0")
    try:
        payload = recommend(args.require, render=args.render, keep=args.keep, limit=args.top)
    except ConstraintError as exc:
        print(f"answers-for: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(prose(payload), file=sys.stderr)
    if payload["matched"] == 0:
        return 1
    if payload["render"] is not None and not payload["render"]["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
