#!/usr/bin/env python3
"""M0 read-only prototype for PLAN S5 (notes/plan-S5-derived-invariants.md, §3 M0).

Recompute the file-sets of the D1-D5 rows of tests/matrix/invariants.yml
from live machinery and print the diff table against the hand-written values
to stderr. Read-only: no file is written, no test is added, exit status is
always 0 (this is a report, not a gate; --check comes in M2).

Inputs are all existing machinery (no new parser):

- tools/questionnaire.py: the question shape (bot_platform choices/default,
  oj_kind per-category choices, has_* definitions backing the D3 implication).
- tools/predicates.py: collect_sites + evaluate (copier's own questionnaire
  pass over the witness leaves) -- the vectors every coverage check reads --
  plus leaf_contexts (copier's own pass, the source of per-leaf gate values).
- tools/ethics.py: the REGISTRY gates (cross-check that no D file-set needs
  ethics input; D rows carry no ethics-appendix predicate).
- tools/z3_witnesses.py: build() leaves (the domain rows select over).
- tools/invariants.py: the hand values (the diff's other side) and matching.

Method per row:

- origin: the row's `origin:` internal (what M1 policy rows would declare)
  must cover the row's leaf set, read from copier's own rendered contexts
  (never re-parsed: `{{ pkg_dir }}` is resolved from the context, adopt-mode
  gates like `pkg_scaffold`/`prompts_scaffold` come out evaluated).
- ships: each hand-claimed artifact is matched to its template path and the
  `{% if %}` gates on that path; the combined gate must cover the row's leaf
  set. Files whose gate fires on EXACTLY the row's leaf set are listed as
  generated extras (the sentinel-vs-exhaustive gap M2 must rule on).
- absent: the artifact must be unrenderable on every row leaf.
- content: each (path, needle) pair declares a textual anchor (file + gate);
  the anchor is checked textually and the gate's live vector must cover the
  row's leaf set. Where the needle lands in `dependencies`, the rendered
  copier context is checked as a second leg.

Usage: uv run --locked python tools/gen_invariants.py
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:  # tools/ is no root package (pyproject.toml)
    sys.path.insert(0, str(TOP))

from tools import ethics  # noqa: E402
from tools import invariants  # noqa: E402
from tools import predicates  # noqa: E402
from tools import questionnaire  # noqa: E402
from tools import z3_witnesses  # noqa: E402

TEMPLATE = TOP / "template"

#: The M0 rows, in plan §1.1 order (D1-D5).
TARGET_ROWS: tuple[str, ...] = (
    "layout=data_science",
    "layout=web_api",
    "oj_kind=kaggle",
    "oj_kind=ctf",
    "oj_kind=code",
    "include=include_data_science",
    "include=include_web_api",
    "include=include_bot/bot_platform=slack",
    "include=include_bot/bot_platform=line",
    "include=include_bot/bot_platform=gmail",
    "include=include_bot_web_api/bot_platform=slack",
    "include=include_bot_web_api/bot_platform=line",
    "include=include_bot_web_api/bot_platform=gmail",
    "gate_off=use_recommended_agent",
)

#: The origin internal each D row's file-set derives from (plan §2.1: the
#: `origin:` a policy row would carry after M1). The vectors are evaluated
#: live; only the declaration itself is hard-coded -- that declaration IS the
#: M0 output being prototyped.
ORIGINS: dict[str, str] = {
    "layout=data_science": "data_science_layout",
    "layout=web_api": "web_api",
    "oj_kind=kaggle": "kaggle",
    "oj_kind=ctf": "oj_ctf",
    "oj_kind=code": "oj_code",
    "include=include_data_science": "alias-of layout=data_science",
    "include=include_web_api": "alias-of layout=web_api",
    "include=include_bot/bot_platform=slack": "bot_slack_effective",
    "include=include_bot/bot_platform=line": "bot_line_effective",
    "include=include_bot/bot_platform=gmail": "bot_gmail_effective",
    "include=include_bot_web_api/bot_platform=slack": "bot_slack_effective",
    "include=include_bot_web_api/bot_platform=line": "bot_line_effective",
    "include=include_bot_web_api/bot_platform=gmail": "bot_gmail_effective",
    "gate_off=use_recommended_agent": "prompts_scaffold (via agent_scaffold)",
}

#: Content needles: (path, needle, anchor file, gate, also-in-dependencies).
#: The gate is a named internal except where noted; the anchor is verified
#: textually and the gate vector is evaluated live. `None` gate = the
#: empty-dependencies check (the bare workspace renders `dependencies = []`).
CONTENT_ORIGINS: dict[str, list[tuple[str, str, str, str | None, bool]]] = {
    "layout=data_science": [("pyproject.toml", "polars", "questions/_structured.yml", "ds_stack", True)],
    "layout=web_api": [
        # Anchor wording uses the template tag; the live check splits the conjunction into the
        # web_api origin cover (done above) plus a docker-defaults leg from contexts below.
        (".github/workflows/ci.yml", "postgres", "workflows/ci.yml.jinja", "web_api+docker-default", False),
        ("pyproject.toml", "fastapi", "questions/_structured.yml", "web_api", True),
        ("AGENTS.md", "regions.yml", "AGENTS.md.jinja", "web_api", False),
    ],
    "oj_kind=kaggle": [("pyproject.toml", "torch", "questions/_structured.yml", "kaggle", True)],
    "oj_kind=ctf": [("pyproject.toml", "pwntools", "_shared/pyproject-ctf-extra.toml.jinja", "ctf_effective", False)],
    "oj_kind=code": [("pyproject.toml", "dependencies = []", "_shared/pyproject-deps.toml.jinja", None, False)],
    "include=include_bot/bot_platform=slack": [
        ("pyproject.toml", "slack-bolt", "questions/_structured.yml", "bot_slack_effective", True)
    ],
    "include=include_bot/bot_platform=line": [
        ("pyproject.toml", "line-bot-sdk", "questions/_structured.yml", "bot_line_effective", True)
    ],
    "include=include_bot/bot_platform=gmail": [
        (
            "pyproject.toml",
            "google-api-python-client",
            "questions/_structured.yml",
            "bot_gmail_effective",
            True,
        )
    ],
    "include=include_bot_web_api/bot_platform=slack": [
        ("pyproject.toml", "slack-bolt", "questions/_structured.yml", "bot_slack_effective", True)
    ],
    "include=include_bot_web_api/bot_platform=line": [
        ("pyproject.toml", "line-bot-sdk", "questions/_structured.yml", "bot_line_effective", True)
    ],
    "include=include_bot_web_api/bot_platform=gmail": [
        (
            "pyproject.toml",
            "google-api-python-client",
            "questions/_structured.yml",
            "bot_gmail_effective",
            True,
        )
    ],
}

#: One-line causes for the rows whose diff is not empty (H/P-side typo vs
#: generator misread, one line each; filled from the observed diffs).
CAUSES: dict[str, str] = {
    "layout=data_science": (
        "H側 convention (not a typo): the row claims representative sentinels only; "
        "exhaustive generation would add the notebooks/paper/slides outputs and break "
        "byte-identical witness expects, so M2 needs an explicit sentinel rule."
    ),
    "layout=web_api": (
        "H側 convention (not a typo): same sentinel-only claim as data_science; "
        "the app/ auxiliaries (db/models/router/schemas/settings/routers/alembic) are "
        "unclaimed by design and exhaustive generation would drift the expects."
    ),
    "oj_kind=kaggle": (
        "H側 convention (not a typo): src/utils/__init__.py is the package sentinel; "
        "the pipeline modules (dataset/features/plots/...) fire on the same set and "
        "would be generated extras under exhaustive enumeration."
    ),
    "oj_kind=ctf": (
        "H側 convention (not a typo): AGENTS.md is a shared always-rendered file owned "
        "by no single row (superset gate), and challenges/__init__ sentinels are "
        "unclaimed; generation needs a shared-file ownership rule (M1 input)."
    ),
    "oj_kind=code": (
        "H側 convention (not a typo): the bare workspace has no exact-gated file, so "
        "there is nothing to discover -- AGENTS.md is claimed as the branch tell and "
        "`dependencies = []` is verified through the empty-contributors check."
    ),
    "include=include_data_science": (
        "alias row: empty file-set by design (why says the artifacts are layout=data_science's); "
        "any diff here is a generator misread of the has_data_science implication."
    ),
    "include=include_web_api": (
        "alias row: empty file-set by design (why says the artifacts are layout=web_api's); "
        "any diff here is a generator misread of the has_web_api implication."
    ),
    "include=include_bot/bot_platform=slack": (
        "placement-split row: module rides pkg_dir (src/<pkg>/) on cli base; "
        "any diff is a generator misread of the pkg_dir resolution, not an H-side typo."
    ),
    "include=include_bot/bot_platform=line": (
        "placement-split row: module rides pkg_dir (src/<pkg>/) on cli base; "
        "any diff is a generator misread of the pkg_dir resolution, not an H-side typo."
    ),
    "include=include_bot/bot_platform=gmail": (
        "placement-split row: module rides pkg_dir (src/<pkg>/) on cli base; "
        "any diff is a generator misread of the pkg_dir resolution, not an H-side typo."
    ),
    "include=include_bot_web_api/bot_platform=slack": (
        "placement-split row: module lives in top-level app/ on web_api base; "
        "any diff is a generator misread of the web_api branch, not an H-side typo."
    ),
    "include=include_bot_web_api/bot_platform=line": (
        "placement-split row: module lives in top-level app/ on web_api base; "
        "any diff is a generator misread of the web_api branch, not an H-side typo."
    ),
    "include=include_bot_web_api/bot_platform=gmail": (
        "placement-split row: module lives in top-level app/ on web_api base; "
        "any diff is a generator misread of the web_api branch, not an H-side typo."
    ),
    "gate_off=use_recommended_agent": (
        "H側 convention (not a typo): prompts/ is claimed as the directory while the template "
        "renders prompts/agent.md, and tests/test_agent.py fires on the same set unclaimed; "
        "generation needs a directory-vs-file naming rule (M1 input)."
    ),
}


@dataclass
class Finding:
    """One checked field: what the hand value says and what live machinery says."""

    row: str
    field: str
    hand: str
    generated: str
    verdict: str  # MATCH | EXTRA | MISSING | MISMATCH | UNKNOWN


def _eprint(text: str = "") -> None:
    sys.stderr.write(text + "\n")


def _short(text: str, width: int = 42) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def _coverage(fires: list[bool] | None, members: list[bool]) -> str | None:
    """Whether the gate covers the row's leaf set; None when unevaluable."""
    if fires is None:
        return None
    return "cover" if all(not leaf or fire for leaf, fire in zip(members, fires, strict=True)) else "gap"


class Model:
    """The live inputs, loaded once: leaves, sites, vectors, contexts."""

    def __init__(self) -> None:
        self.inv = invariants.load()
        _raw, _order = questionnaire.load_raw_questions()
        self.raw_questions = _raw
        self.vocab = self.inv.vocabulary
        _space, leaves = z3_witnesses.build()
        self.leaves = sorted(leaves, key=lambda leaf: leaf.id)
        self.sites = predicates.collect_sites()
        predicates.evaluate(self.sites, self.leaves)
        self.vectors: dict[str, list[bool]] = {}
        for site in self.sites:
            if site.kind == "internal" and site.vector is not None:
                self.vectors[site.location.rsplit(":", 1)[-1]] = site.vector
        self.by_eval: dict[str, list[bool]] = {}
        for site in self.sites:
            if site.vector is not None and site.eval_expr not in self.by_eval:
                self.by_eval[site.eval_expr] = site.vector
        self.facts = {leaf.id: self.inv.facts(leaf.answers) for leaf in self.leaves}
        self.rows = {row.id: row for row in self.inv.rows}
        self.contexts: dict[str, dict] = {}
        self._ctx_vectors: dict[str, list[bool] | None] = {}
        self.registry = ethics.load_registry()

    def members(self, row_id: str) -> list[bool]:
        row = self.rows[row_id]
        return [row.matches(self.facts[leaf.id]) for leaf in self.leaves]

    def member_ids(self, row_id: str) -> list[str]:
        return [leaf.id for leaf, hit in zip(self.leaves, self.members(row_id), strict=True) if hit]

    def ensure_contexts(self, ids: list[str]) -> None:
        missing = [leaf for leaf in self.leaves if leaf.id in ids and leaf.id not in self.contexts]
        if not missing:
            return
        for leaf, context, _env in predicates.leaf_contexts(missing):
            self.contexts[leaf.id] = dict(context)

    def context_vector(self, name: str) -> list[bool] | None:
        """The named internal's per-leaf value from copier's own pass.

        Copier already evaluated every internal (including adopt-mode gates
        like `pkg_scaffold` whose spelling reads a list and is therefore
        unevaluable as a re-rendered site); reading the value back is never
        unevaluable. None only when no leaf context carries the name.
        """
        if name not in self._ctx_vectors:
            self.ensure_contexts([leaf.id for leaf in self.leaves])
            if all(name in self.contexts[leaf.id] for leaf in self.leaves):
                self._ctx_vectors[name] = [bool(self.contexts[leaf.id].get(name)) for leaf in self.leaves]
            else:
                self._ctx_vectors[name] = None
        return self._ctx_vectors[name]

    def gate_vector(self, gate: str) -> list[bool] | None:
        """The live vector of a gate.

        Copier's own value for a named internal, else the evaluated site
        expression (None when unevaluable).
        """
        if gate.isidentifier():
            vector = self.context_vector(gate)
            if vector is not None:
                return vector
            return self.vectors.get(gate)
        return self.by_eval.get(gate)


_TAG = re.compile(r"\{%.*?%\}")


def _strip_tags(segment: str) -> str:
    return _TAG.sub("", segment)


def _rendered_rel(path: Path, pkg_dir: str | None) -> str | None:
    """The template path with its gates stripped, or None when symbolic.

    Each segment is `{% if gate %}literal{% endif %}` (or a chain of them):
    stripping the tags leaves the literal the segment renders to when the
    gate holds. `{{ pkg_dir }}` is resolved from the leaf's copier context
    (never by string surgery on the formula). A segment keeping a `{{ }}`
    after that (e.g. `{{ _copier_conf.answers_file }}`) or rendering empty
    (a pure gate with no literal) cannot be named: None.
    """
    parts: list[str] = []
    for segment in path.relative_to(TEMPLATE).parts:
        text = _strip_tags(segment)
        if "{{ pkg_dir }}" in text:
            if pkg_dir is None:
                return None
            text = text.replace("{{ pkg_dir }}", pkg_dir)
        if "{{" in text or "{%" in text:
            return None
        text = text.strip()
        if not text:
            return None
        parts.append(text)
    text = "/".join(parts)
    return text.removesuffix(".jinja")


@dataclass
class GatedFile:
    """One template file: its location and every segment gate with its vector."""

    location: str
    gates: list[tuple[str, list[bool] | None]]
    combined: list[bool] | None


class TemplateWalk:
    """Every template file with its combined gate vector (AND over segments)."""

    def __init__(self, model: Model) -> None:
        self.model = model
        index: dict[str, list[predicates.Site]] = {}
        for site in model.sites:
            if site.kind == "filename":
                index.setdefault(site.location.split("::")[0], []).append(site)
        n = len(model.leaves)
        self.files: list[GatedFile] = []
        for path in sorted(TEMPLATE.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(TEMPLATE)
            gates, combined = self._walk_segments(rel, index, model, n)
            self.files.append(GatedFile(rel.as_posix(), gates, combined))

    @staticmethod
    def _walk_segments(
        rel: Path,
        index: dict[str, list[predicates.Site]],
        model: Model,
        n: int,
    ) -> tuple[list[tuple[str, list[bool] | None]], list[bool] | None]:
        """Combine one template path's per-segment gate vectors (AND over segments)."""
        gates: list[tuple[str, list[bool] | None]] = []
        combined: list[bool] | None = [True] * n
        for depth, segment in enumerate(rel.parts):
            base = Path("template", *rel.parts[:depth]).as_posix()
            seg_sites = index.get(f"{base}/{segment}", [])
            if not seg_sites:
                continue
            seg_or = TemplateWalk._or_segment(seg_sites, model, n)
            gates.extend((site.eval_expr, model.gate_vector(site.eval_expr)) for site in seg_sites)
            if seg_or is None:
                combined = None
            elif combined is not None:
                combined = [hit and fire for hit, fire in zip(combined, seg_or, strict=True)]
        return gates, combined

    @staticmethod
    def _or_segment(seg_sites: list[predicates.Site], model: Model, n: int) -> list[bool] | None:
        """OR one path segment's site vectors (None when any site is unevaluable)."""
        seg_or: list[bool] | None = [False] * n
        for site in seg_sites:
            vector = model.gate_vector(site.eval_expr)
            if vector is None:
                return None
            if seg_or is not None:
                seg_or = [hit or fire for hit, fire in zip(seg_or, vector, strict=True)]
        return seg_or

    def candidates(self, artifact: str, pkg_options: list[str]) -> list[tuple[str, GatedFile]]:
        """Template files that can render to the artifact, with their gates."""
        out: list[tuple[str, GatedFile]] = []
        for entry in self.files:
            for pkg in pkg_options:
                rendered = _rendered_rel(TEMPLATE / entry.location, pkg)
                if rendered is not None and (rendered == artifact or rendered.startswith(artifact + "/")):
                    out.append((rendered, entry))
                    break
        return out

    def possible_on(self, members: list[bool], pkg: str) -> set[str]:
        """Rendered paths that can appear on at least one member leaf."""
        out: set[str] = set()
        for entry in self.files:
            if entry.combined is None:
                continue
            if not any(fire and leaf for fire, leaf in zip(entry.combined, members, strict=True)):
                continue
            rendered = _rendered_rel(TEMPLATE / entry.location, pkg)
            if rendered is not None:
                out.add(rendered)
        return out

    def exact(self, members: list[bool], pkg_options: list[str]) -> set[str]:
        """Rendered paths whose gate fires on exactly the member leaves."""
        want = [i for i, leaf in enumerate(members) if leaf]
        out: set[str] = set()
        for entry in self.files:
            if entry.combined is None:
                continue
            if [i for i, fire in enumerate(entry.combined) if fire] != want:
                continue
            for pkg in pkg_options:
                rendered = _rendered_rel(TEMPLATE / entry.location, pkg)
                if rendered is not None:
                    out.add(rendered)
                    break
        return out


def _cover_status(cands: list[tuple[str, GatedFile]], members: list[bool], count: int) -> tuple[str, str]:
    """Whether the candidate files cover every member leaf."""
    if not cands:
        return ("MISSING", "UNREACHABLE on row leaves")
    covered = [False] * count
    for _rendered, entry in cands:
        if entry.combined is None:
            continue
        covered = [hit or fire for hit, fire in zip(covered, entry.combined, strict=True)]
    if all(not leaf or hit for leaf, hit in zip(members, covered, strict=True)):
        return ("MATCH", f"present, gate covers {sum(members)} row leaves")
    unevaluable = sorted({expr for _rendered, entry in cands for expr, vector in entry.gates if vector is None})
    if unevaluable:
        return ("UNKNOWN", f"possible but gate unevaluable: {unevaluable}")
    return ("MISMATCH", "renderable but not on all row leaves")


def _check_ships(
    model: Model, walk: TemplateWalk, row_id: str, members: list[bool], pkg_options: list[str]
) -> list[Finding]:
    row = model.rows[row_id]
    findings: list[Finding] = []
    for artifact in row.ships:
        cands = walk.candidates(artifact, pkg_options)
        verdict, generated = _cover_status(cands, members, len(model.leaves))
        if cands and cands[0][0] != artifact:
            generated += f" (as {min(rendered for rendered, _ in cands)})"
        findings.append(Finding(row_id, "ships", artifact, generated, verdict))
    extras = sorted(path for path in walk.exact(members, pkg_options) if path not in row.ships)
    findings.extend(Finding(row_id, "ships", "(unclaimed)", extra, "EXTRA") for extra in extras)
    return findings


def _check_absent(
    model: Model, walk: TemplateWalk, row_id: str, members: list[bool], pkg_options: list[str]
) -> list[Finding]:
    row = model.rows[row_id]
    possible: set[str] = set()
    unevaluable: set[str] = set()
    for pkg in pkg_options:
        possible |= walk.possible_on(members, pkg)
    for artifact in row.ships:
        for _rendered, entry in walk.candidates(artifact, pkg_options):
            if entry.combined is None:
                unevaluable.add(artifact)
    _ = unevaluable  # ships-side tracking lives in _cover_status; kept for symmetry
    findings: list[Finding] = []
    for artifact in row.absent:
        if artifact == "src" and row_id == "oj_kind=code":
            # `src` is never a template path: the `{% if src_dirs %}src{% endif %}` tree plus
            # copier.yml's src_dirs task create it, and bare leaves render src_dirs=[]. Check
            # the derived list from contexts instead of the path walk (R4: no silent drop).
            model.ensure_contexts(model.member_ids(row_id))
            lists = {str(model.contexts[i].get("src_dirs")) for i in model.member_ids(row_id)}
            if lists == {"[]"}:
                findings.append(Finding(row_id, "absent", artifact, "src_dirs=[] on all member leaves", "MATCH"))
            else:
                findings.append(Finding(row_id, "absent", artifact, f"src_dirs on members={sorted(lists)}", "MISMATCH"))
            continue
        rendered = {path for path in possible if path == artifact or path.startswith(artifact + "/")}
        if rendered:
            findings.append(Finding(row_id, "absent", artifact, f"RENDERED: {min(rendered)}", "MISMATCH"))
        else:
            gate_unknown = [
                expr
                for rendered_path, entry in (
                    (rendered_path, entry)
                    for rendered_path, entry in (
                        (r, e) for pkg in pkg_options for r, e in walk.candidates(artifact, [pkg])
                    )
                )
                for expr, vector in entry.gates
                if vector is None
            ]
            if gate_unknown:
                findings.append(
                    Finding(row_id, "absent", artifact, f"gate unevaluable: {sorted(set(gate_unknown))}", "UNKNOWN")
                )
            else:
                findings.append(Finding(row_id, "absent", artifact, "not rendered on row leaves", "MATCH"))
    return findings


def _read_anchor(anchor: str) -> tuple[str, list[str]] | None:
    """Locate the anchor file and read its lines (None when unreadable)."""
    path: Path | None = TOP / anchor
    if not path.exists():
        matches = list(TEMPLATE.rglob(Path(anchor).name))
        path = matches[0] if matches else None
    if path is None:
        return None
    try:
        return path.relative_to(TOP).as_posix(), path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None


def _same_line_hit(
    short: str, lines: list[str], pair: tuple[str, str], hits: tuple[list[int], list[int]]
) -> str | None:
    """A gate and needle sharing one source line (None when they do not)."""
    gate, needle = pair
    gate_lines, needle_lines = hits
    for number in sorted(set(gate_lines) & set(needle_lines)):
        line = lines[number - 1]
        if line.find(f"{{% if {gate}") < line.find(needle) or line.find(gate) < line.find(needle):
            return f"{short}:{number} ({gate}) -> :{number} ({needle}) [same line]"
    return None


def _anchor_text(anchor: str, gate: str | None, needle: str) -> str:
    """Textual evidence that the needle sits under the gate in the anchor file."""
    located = _read_anchor(anchor)
    if located is None:
        return "anchor unreadable"
    short, lines = located
    if gate is None:
        return f"{short} one-liner (empty-list leg checked in context)"
    gate_lines = [i + 1 for i, line in enumerate(lines) if gate in line and "if" in line]
    needle_lines = [i + 1 for i, line in enumerate(lines) if needle in line]
    missing = (
        f"gate {gate!r} NOT FOUND in {short}"
        if not gate_lines
        else (f"needle {needle!r} NOT FOUND in {short}" if not needle_lines else None)
    )
    if missing is not None:
        return missing
    same = _same_line_hit(short, lines, (gate, needle), (gate_lines, needle_lines))
    if same is not None:
        return same
    if min(needle_lines) > min(gate_lines):
        return f"{short}:{gate_lines[0]} ({gate}) -> :{needle_lines[0]} ({needle})"
    return f"order unexpected: needle {needle_lines} before gate {gate_lines}"


def _check_content(model: Model, row_id: str, members: list[bool]) -> list[Finding]:
    row = model.rows[row_id]
    hand = {tuple(pair) for pair in row.content}
    model.ensure_contexts(model.member_ids(row_id))
    findings: list[Finding] = []
    for path, needle, anchor, gate, in_deps in CONTENT_ORIGINS.get(row_id, []):
        anchor_hit = _anchor_text(anchor, gate, needle)
        if gate is None:
            deps = [model.contexts[i].get("dependencies") for i in model.member_ids(row_id)]
            empty = sum(1 for dep in deps if dep == [])
            generated = f"{anchor_hit}; dependencies empty on {empty}/{len(deps)} member leaves"
            verdict = "MATCH" if empty == len(deps) and "NOT FOUND" not in anchor_hit else "MISMATCH"
        elif gate == "web_api+docker-default":
            # ci.yml.jinja renders its postgres block under `{% if web_api and not docker %}`.
            # `docker` is a detail question behind use_recommended_integrations (default false);
            # the derived details=chosen leaves answer it true, so the needle is conditional:
            # it must fire exactly on the docker=false members (the docker=true members get
            # postgres from compose.local.yml instead). Read both legs live: the site vector
            # for the conjunction plus docker from copier's own rendered contexts.
            anchor_hit = _anchor_text(anchor, "web_api and not docker", needle)
            model.ensure_contexts(model.member_ids(row_id))
            gate_vec = model.by_eval.get("web_api and not docker")
            want = [
                member and model.contexts[leaf.id].get("docker") is False
                for member, leaf in zip(members, model.leaves, strict=True)
            ]
            if gate_vec is not None and [bool(v) for v in gate_vec] == want:
                generated = f"{anchor_hit}; conditional: fires exactly on {sum(want)} docker=false members"
                verdict = "MATCH" if "NOT FOUND" not in anchor_hit else "MISMATCH"
            else:
                generated = f"{anchor_hit}; gate vector != docker=false members"
                verdict = "MISMATCH"
        else:
            vector = model.gate_vector(gate)
            cover = _coverage(vector, members)
            generated = f"{anchor_hit}; gate={gate} {cover}"
            if cover is None:
                verdict = "UNKNOWN"
            else:
                verdict = "MATCH" if cover == "cover" and "NOT FOUND" not in anchor_hit else "MISMATCH"
                if verdict == "MATCH" and in_deps:
                    deps = [str(model.contexts[i].get("dependencies")) for i in model.member_ids(row_id)]
                    if not all(needle in dep for dep in deps):
                        generated += "; dependencies leg MISSING needle"
                        verdict = "MISMATCH"
        key = (path, needle)
        findings.append(
            Finding(row_id, "content", f"[{path}, {needle}]", generated, verdict if key in hand else "EXTRA")
        )
    for path, needle in sorted(hand):
        if (path, needle) not in {(p, n) for p, n, _a, _g, _d in CONTENT_ORIGINS.get(row_id, [])}:
            findings.append(Finding(row_id, "content", f"[{path}, {needle}]", "no origin declared", "UNKNOWN"))
    return findings


def _check_alias(model: Model, row_id: str, members: list[bool]) -> list[Finding]:
    """D3: the include_* leaf set must sit inside the layout row's leaf set."""
    layout_row = "layout=data_science" if "data_science" in row_id else "layout=web_api"
    layout_members = model.members(layout_row)
    inside = all(not leaf or fire for leaf, fire in zip(members, layout_members, strict=True))
    row = model.rows[row_id]
    trait = "has_data_science" if "data_science" in row_id else "has_web_api"
    definition = str(model.raw_questions.get(trait, {}).get("default", ""))
    generated = f"leaves={sum(members)} inside {layout_row}={inside}; {trait}={definition[:60]}"
    verdict = "MATCH" if inside and not row.ships and not row.absent else "MISMATCH"
    return [Finding(row_id, "ships+absent", "[] (alias)", generated, verdict)]


def _check_origin_cover(model: Model, row_id: str, members: list[bool]) -> Finding:
    origin = ORIGINS[row_id]
    if origin.startswith("alias-of"):
        return Finding(row_id, "origin", origin, "see alias check", "MATCH")
    gate = {"gate_off=use_recommended_agent": "agent_scaffold"}.get(row_id, origin.split(" ")[0])
    vector = model.gate_vector(gate)
    cover = _coverage(vector, members)
    if cover is None:
        return Finding(row_id, "origin", origin, f"gate {gate} unevaluable", "UNKNOWN")
    fires = sum(1 for fire in vector if fire)
    return Finding(
        row_id,
        "origin",
        origin,
        f"gate {gate}: fires={fires} leaves={sum(members)} {cover}",
        "MATCH" if cover == "cover" else "MISMATCH",
    )


def _ethics_note(model: Model, row_id: str, _members: list[bool]) -> str:
    ids = model.member_ids(row_id)
    firing: set[str] = set()
    for section in model.registry:
        for leaf_id in ids:
            leaf = next(leaf for leaf in model.leaves if leaf.id == leaf_id)
            if ethics.gate_holds(section, dict(leaf.answers)):
                firing.add(str(section.get("id", section.get("file"))))
                break
    preds = ",".join(model.rows[row_id].predicates) or "(none)"
    return f"registry sections firing on row leaves: {len(firing)}; row predicates: {preds}"


_ALIAS_ROWS = frozenset({"include=include_data_science", "include=include_web_api"})


def _analyze_row(model: Model, walk: TemplateWalk, row_id: str) -> list[Finding]:
    members = model.members(row_id)
    findings = [_check_origin_cover(model, row_id, members)]
    if row_id in _ALIAS_ROWS:
        return findings + _check_alias(model, row_id, members)
    model.ensure_contexts(model.member_ids(row_id))
    pkg_options = sorted({str(model.contexts[i].get("pkg_dir")) for i in model.member_ids(row_id)})
    out = findings + _check_ships(model, walk, row_id, members, pkg_options)
    out += _check_absent(model, walk, row_id, members, pkg_options)
    out += _check_content(model, row_id, members)
    return out


def _questionnaire_notes(model: Model) -> list[str]:
    vocab = model.vocab
    live_platforms = tuple(p for p in vocab.bot_platforms if p != vocab.bot_platform_default)
    code_kinds = sorted(set(vocab.oj_kinds) - {"kaggle", "ctf"})
    hand_code = list(model.rows["oj_kind=code"].select.get("oj_kind", []))
    bot_line = (
        f"bot_platform choices={list(vocab.bot_platforms)} default={vocab.bot_platform_default} "
        f"derived-variants={list(live_platforms)} "
        f"(z3 BOT_PLATFORM_VARIANTS={list(z3_witnesses.BOT_PLATFORM_VARIANTS)})"
    )
    oj_line = (
        f"oj kinds live={sorted(vocab.oj_kinds)} code-kinds={code_kinds} hand={hand_code} "
        f"match={sorted(hand_code) == code_kinds}"
    )
    return [bot_line, oj_line]


def main() -> int:
    model = Model()
    walk = TemplateWalk(model)
    unevaluable = sum(1 for site in model.sites if site.vector is None)

    _eprint("gen_invariants.py M0: D1-D5 file-set recomputation vs tests/matrix/invariants.yml (read-only)")
    _eprint(
        f"inputs: leaves={len(model.leaves)} sites={len(model.sites)} "
        f"unevaluable={unevaluable} registry-sections={len(model.registry)}"
    )
    for note in _questionnaire_notes(model):
        _eprint(f"questionnaire: {note}")
    _eprint("")

    all_findings: list[Finding] = []
    for row_id in TARGET_ROWS:
        all_findings += _analyze_row(model, walk, row_id)
    _eprint(f"{'row':44} {'field':12} {'hand':40} {'generated':60} verdict")
    for finding in all_findings:
        _eprint(
            f"{finding.row:44} {finding.field:12} {_short(finding.hand):40} "
            f"{_short(finding.generated, 60):60} {finding.verdict}"
        )
    _eprint("")
    diff_rows = sorted({finding.row for finding in all_findings if finding.verdict != "MATCH"})
    _eprint(f"rows with non-empty diff: {len(diff_rows)} / {len(TARGET_ROWS)}")
    for row_id in TARGET_ROWS:
        if row_id in diff_rows:
            cause = CAUSES.get(row_id, "UNTRIAGED: generator misread suspected, needs template re-read")
            _eprint(f"CAUSE {row_id}: {cause}")
        else:
            _eprint(f"OK {row_id}: empty diff (match) -- {_ethics_note(model, row_id, model.members(row_id))}")
    _eprint("method: named gates read from copier's own rendered contexts (never re-parsed),")
    _eprint("so adopt-mode gates (pkg_scaffold/prompts_scaffold) evaluate instead of going unevaluable;")
    _eprint("a remaining UNKNOWN names its gate (plan R4: never silently dropped).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
