"""Registry guard for the ethics/regional/operational sections.

_shared/ethics/REGISTRY.yml is the single source for accumulated rule
sections (region/sector/domain). Until a section graduates to a genre
(questions/ + witness leaf) it stays draft and no template/ file may
include it (leaf +0). These tests pin the *contract surface*: row shape,
header agreement, draft isolation, gate safety/boundness, generated-appendix
freshness, and the regions/copyright tables' bindings. Prose-shape QA (the
body naming its scale/audience tokens, denylist prose checks) moves to the
codex repo's content suite when the split lands -- see
kasi-x/daimonion-internal notes/upstream-drafts/11-codex-content-qa-suite.md.
"""

import ast
import re
import sys
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path

import yaml

TOP = Path(__file__).resolve().parent.parent
ETHICS = TOP / "_shared" / "ethics"
REGISTRY = ETHICS / "REGISTRY.yml"

VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.\d+$")
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HEADER_RE = re.compile(r"\{#\s*ethics:\s*id=(\S+)\s+version=(\S+)\s+status=(\S+)")
TRIGGER_SPAN_RE = re.compile(r"`((?:\(\?i\))[^`]+)`")


def _load_registry():
    """The registry rows (version 1, non-empty section list)."""
    payload = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    assert payload.get("version") == 1, "registry version must be 1"
    sections = payload.get("sections")
    assert isinstance(sections, list) and sections, "sections must be a non-empty list"
    return sections


def _datestr(value: object) -> str | None:
    """A registry date (YAML parses unquoted dates) as an ISO string."""
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _read(path: Path) -> str:
    """File text, tolerating nothing: non-files read as empty."""
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def test_registry_rows_are_well_formed():
    """Every row names its rule, version, sources, scope and lifecycle state."""
    required = {
        "id",
        "file",
        "version",
        "effective",
        "review_by",
        "sources",
        "scale",
        "audience",
        "enforcement",
        "status",
        "rendered_from",
        "superseded_by",
    }
    ids = []
    for row in _load_registry():
        assert required <= set(row), f"{row.get('id')}: missing keys {sorted(required - set(row))}"
        assert ID_RE.fullmatch(str(row["id"])), f"bad id {row['id']!r}"
        ids.append(str(row["id"]))
        assert VERSION_RE.fullmatch(str(row["version"])), f"{row['id']}: bad version {row['version']!r}"
        assert str(row["file"]).startswith("_shared/ethics/"), f"{row['id']}: must live under _shared/ethics/"
        assert (TOP / str(row["file"])).is_file(), f"{row['id']}: missing file {row['file']}"
        effective, review_by = _datestr(row["effective"]), _datestr(row["review_by"])
        assert review_by is not None and re.fullmatch(r"\d{4}-\d{2}-\d{2}", review_by), f"{row['id']}: bad review_by"
        if effective is not None:
            assert review_by > effective, f"{row['id']}: review_by must be after effective"
        sources = row["sources"]
        assert isinstance(sources, list) and sources, f"{row['id']}: sources must be non-empty"
        assert set(row["scope"]) == {"jurisdiction", "sector", "category"}, f"{row['id']}: bad scope keys"
        assert row["scale"] in {"domestic", "regional", "global"}, f"{row['id']}: bad scale"
        audience = row["audience"]
        assert isinstance(audience, list) and audience, f"{row['id']}: audience must be non-empty"
        assert all(ID_RE.fullmatch(str(entry)) for entry in audience), f"{row['id']}: bad audience entry"
        assert row["enforcement"] in {"L0", "L1", "L2"}, f"{row['id']}: bad enforcement"
        assert row["status"] in {"draft", "active", "kind"}, f"{row['id']}: bad status"
        if row["status"] == "draft":
            assert row["rendered_from"] == [], f"{row['id']}: draft must render from nowhere"
        else:
            assert row["rendered_from"], f"{row['id']}: distributed rows must name their parents"
            assert row.get("gate"), f"{row['id']}: a distributed row needs its gate expression"
    assert len(set(ids)) == len(ids), f"duplicate section ids: {ids}"


def test_section_headers_agree_with_registry():
    """The file header repeats its row (id/version/status/review date)."""
    for row in _load_registry():
        text = (TOP / str(row["file"])).read_text(encoding="utf-8")
        match = HEADER_RE.search("\n".join(text.splitlines()[:4]))
        assert match, f"{row['id']}: must open with a {{# ethics: id=.. version=.. status=.. #}} header"
        section_id, version, status = match.groups()
        assert section_id == row["id"], f"header id {section_id!r} != row {row['id']!r}"
        assert version == str(row["version"]), f"{row['id']}: header version drifted from the row"
        assert status == row["status"], f"{row['id']}: header status drifted from the row"
        review = _datestr(row["review_by"])
        assert review is not None and review in text, f"{row['id']}: body must repeat the row's review_by"


def _consumer_files():
    """Every file that could include a section: template/ + tasks + _shared/."""
    files = [path for path in (TOP / "template").rglob("*") if path.is_file()]
    tasks = TOP / "_tasks.jinja"
    if tasks.is_file():
        files.append(tasks)
    files += [path for path in (TOP / "_shared").rglob("*.jinja") if path.name != "_template.md.jinja"]
    return files


def test_draft_sections_are_not_distributed():
    """A draft section is documentation only: nothing includes it (leaf +0).

    `include`-shaped distribution is the failure this guards; a *reference*
    to the section file is how the shipped `ethics/regions.yml` table points
    back at the rule it abbreviates, so a consumer that names the draft only
    through the table's `serves:` field is exempt -- the distinction is
    lexical: distribution embeds or pulls the section's body, a reference
    just names the path for the reader.
    """
    for row in _load_registry():
        if row["status"] != "draft":
            continue
        text = _read(TOP / str(row["file"]))
        assert "{{" not in text, f"{row['id']}: draft sections take no copier context"
        offenders = []
        for path in _consumer_files():
            if path == TOP / str(row["file"]):
                continue
            body = _read(path)
            if str(row["file"]) not in body:
                continue
            if path.name == "regions.yml" and f"serves: {row['file']}" in body:
                continue  # the table references the draft; it does not distribute it
            offenders.append(str(path.relative_to(TOP)))
        assert not offenders, f"{row['id']} is draft but included from: {offenders}"


def test_distributed_sections_are_included_by_their_parents():
    """The mirror of the draft check: an active/kind row's parents include it.

    `rendered_from` is the row's claim about who renders the section; this
    holds each named parent to it, so a promotion PR cannot name a parent it
    did not wire (and a refactor cannot silently drop the include).
    """
    for row in _load_registry():
        if row["status"] == "draft":
            continue
        assert row["rendered_from"], f"{row['id']}: a distributed row must name its parents"
        for parent in row["rendered_from"]:
            path = TOP / str(parent)
            assert path.is_file(), f"{row['id']}: rendered_from names a missing parent {parent!r}"
            assert str(row["file"]) in _read(path), (
                f"{row['id']}: parent {parent!r} does not reference the section file"
            )


def test_every_row_documents_a_parseable_presence_trigger():
    """The 設定側トリガー span is the row's machine-readable half.

    tools/ethics.py's `match()` (the MCP `check_ethics` tool) scans text with
    exactly this span; a row that stops documenting it in the parseable shape
    would silently vanish from every match result, so the loader's parse is
    pinned here for all rows, drafts included. The trigger detects English
    code vocabulary (a Japanese title cannot carry it), so the only honest
    pins are: it compiles, it is case-insensitive, and no two rows share one.
    """
    sys.path.insert(0, str(TOP))
    from tools import ethics  # noqa: PLC0415

    triggers = [ethics.presence_trigger(row) for row in _load_registry()]
    for row, trigger in zip(_load_registry(), triggers, strict=True):
        re.compile(trigger)
        assert trigger.startswith("(?i)"), f"{row['id']}: the presence trigger must be case-insensitive"
    assert len(set(triggers)) == len(triggers), (
        "two rows sharing one presence trigger would be indistinguishable to check_ethics"
    )


def test_the_generated_appendix_matches_the_registry():
    """_shared/ethics-appendix.jinja is generated, so the committed file must
    equal what the registry currently produces.

    The AGENTS.md appendix used to hand-write the include chain; now the
    registry row's `gate` is the single spelling, and the generated file is
    what actually renders. An edit to a row's status or gate without a
    regeneration leaves the shipped appendix silently wrong -- the drift is
    the same class gen_docs' committed-output check catches, so the test
    runs the generator's check path rather than re-deriving the chain.
    """
    sys.path.insert(0, str(TOP))
    from tools import gen_ethics_appendix  # noqa: PLC0415

    assert gen_ethics_appendix.main(["--check"]) == 0, (
        "the committed _shared/ethics-appendix.jinja is stale -- run `python tools/gen_ethics_appendix.py`"
    )


def test_gates_are_safe_and_distributed_ones_are_bound():
    """Every gate parses under the restricted evaluator; a distributed row's
    gate also names only the flags the leaf context provides.

    Drafts keep their intended `gate` at registration time (a promotion is a
    status flip plus the answer wiring), so every row's expression is linted;
    boundness is checked only where it is decidable -- the leaf context's
    vocabulary is the contract a distributed row renders against, while a
    draft may reserve a flag that the context does not bind yet (that is the
    promotion's job to add). A typo'd flag on a distributed row would raise
    NameError at render time (the generated `{% if %}`), so it fails here,
    not in a user's copier run.
    """
    sys.path.insert(0, str(TOP))
    from tools import ethics as ethics_mod  # noqa: PLC0415

    context_keys = set(ethics_mod.leaf_context({"project_type": "library"}))
    for row in _load_registry():
        gate = str(row.get("gate") or "")
        if not gate:
            continue
        problem = ethics_mod.gate_safe(gate)
        assert problem is None, f"{row['id']}: gate {gate!r} is not evaluable: {problem}"
        if row["status"] == "draft":
            continue  # drafts may reserve flags the context does not bind yet
        names = {node.id for node in ast.walk(ast.parse(gate, mode="eval")) if isinstance(node, ast.Name)}
        unknown = names - context_keys
        assert not unknown, f"{row['id']}: gate {gate!r} names flags the leaf context does not bind: {sorted(unknown)}"


def test_copyright_terms_table_matches_its_section():
    """The lang/ table is the structured half of baseline-copyright-ai.

    `lang/` is reserved for the translation-style dictionaries the section
    prose keeps out of AGENTS.md: the protection-term differences a
    public-domain checker must consult. The pin holds the table to the
    section it serves -- same review_by as the registry row, every
    jurisdiction carrying rules plus its own primary sources, and the
    wartime extension the section's prose names present as data, so the
    section can claim "法域差" without the checker's inputs living only in
    a paragraph.
    """
    rows = [row for row in _load_registry() if row["id"] == "baseline-copyright-ai"]
    assert rows, "the copyright-ai section must stay registered"
    review_by = _datestr(rows[0]["review_by"])
    table_path = ETHICS / "lang" / "copyright-terms.yml"
    assert table_path.is_file(), "the copyright-terms table must live under _shared/ethics/lang/"
    payload = yaml.safe_load(table_path.read_text(encoding="utf-8"))
    assert payload.get("version") == 1, "table version must be 1"
    assert payload.get("serves") == "baseline-copyright-ai", "table must name the section it serves"
    assert _datestr(payload.get("review_by")) == review_by, (
        "the table's review_by must match the baseline-copyright-ai row"
    )
    terms = payload.get("terms")
    assert isinstance(terms, dict) and terms, "terms must be a non-empty mapping"
    for jurisdiction, entry in terms.items():
        assert ID_RE.fullmatch(jurisdiction), f"bad jurisdiction id {jurisdiction!r}"
        for key in ("individual", "corporate", "notes", "sources"):
            assert key in entry, f"{jurisdiction}: missing key {key!r}"
        assert entry["individual"] and entry["corporate"], f"{jurisdiction}: term rules must be non-empty"
        assert isinstance(entry["notes"], list) and entry["notes"], f"{jurisdiction}: notes must be non-empty"
        sources = entry["sources"]
        assert isinstance(sources, list) and sources, f"{jurisdiction}: sources must be non-empty"
        assert all(str(url).startswith("https://") for url in sources), f"{jurisdiction}: sources must be https URLs"
    jp = terms.get("jp")
    assert jp is not None and "戦時加算" in "".join(jp["notes"]), (
        "jp must carry the wartime extension as data, not only in the section prose"
    )
    section_text = (TOP / str(rows[0]["file"])).read_text(encoding="utf-8")
    assert "lang/copyright-terms.yml" in section_text, (
        "the section must point at the table so the two cannot drift apart silently"
    )


def test_regions_table_serves_registered_drafts():
    """ethics/regions.yml is the distribution channel for the regional rules
    whose trigger is a target market, not a project kind.

    The questionnaire cannot ask 'which regions do you target' without a new
    leaf dimension, so the generated `ethics/regions.yml` (web_api renders
    only) carries each rule's summary and primary sources and points back at
    the registry draft it abbreviates. The pin holds both ends: the table
    names only registered region sections, and its review horizon is the
    earliest review_by among the rows it serves -- stale statutes surface in
    the section suite, not after a user's project was already generated.
    """
    table_path = TOP / "template" / "{% if web_api %}ethics{% endif %}" / "regions.yml"
    assert table_path.is_file(), "the regions table must live under template/{% if web_api %}ethics{% endif %}/"
    payload = yaml.safe_load(table_path.read_text(encoding="utf-8"))
    assert payload.get("version") == 1, "table version must be 1"
    rules = payload.get("rules")
    assert isinstance(rules, list) and rules, "rules must be a non-empty list"

    rows = {row["id"]: row for row in _load_registry()}
    served: list[str] = []
    review_by: list[str] = []
    for rule in rules:
        rule_id = rule.get("id")
        assert ID_RE.fullmatch(str(rule_id)), f"bad rule id {rule_id!r}"
        serves = str(rule.get("serves", ""))
        assert serves.endswith(".md.jinja"), f"{rule_id}: serves must name the section file"
        served_row = rows.get(str(rule_id))
        assert served_row is not None, f"{rule_id}: serves a section the registry does not know"
        assert str(served_row["file"]) == serves, (
            f"{rule_id}: serves {serves!r} but the registry names {served_row['file']!r}"
        )
        for key in ("jurisdiction", "statute", "applies_to", "duties", "triggers", "sources"):
            assert rule.get(key), f"{rule_id}: missing or empty key {key!r}"
        assert isinstance(rule["duties"], list), f"{rule_id}: duties must be a list"
        assert isinstance(rule["sources"], list) and all(str(url).startswith("https://") for url in rule["sources"]), (
            f"{rule_id}: sources must be https URLs"
        )
        served.append(str(rule_id))
        review_by.append(str(served_row["review_by"]))

    assert _datestr(payload.get("review_by")) == min(review_by), (
        "the table's review_by is the earliest among the rows it serves -- "
        "the first rule to need re-checking sets the table's horizon"
    )
    agents = TOP / "template" / "{% if agents_md_effective %}AGENTS.md{% endif %}.jinja"
    assert "regions.yml" in _read(agents), "AGENTS.md must point at the table so the channel cannot drop silently"


def test_python_examples_are_ruff_format_clean(tmp_path: Path):
    """A section's ```python blocks survive the generated project's `task check`.

    ruff 0.16+ formats Python code blocks inside markdown files, and the
    section bodies render into the generated AGENTS.md — so an example
    whose style is off fails `ruff format --check` for every project kind
    that ships the section. The examples are checked under both generated
    widths (allow_japanese's 88 and 120). A "bad" example is bad
    semantically (verify=False, a missing scrub), never stylistically.
    """
    import subprocess  # noqa: PLC0415

    blocks: list[tuple[str, int, str]] = []
    for row in _load_registry():
        text = (TOP / str(row["file"])).read_text(encoding="utf-8")
        for index, span in enumerate(re.findall(r"```python\n(.*?)```", text, re.DOTALL)):
            blocks.append((str(row["id"]), index, span))
    assert blocks, "no python examples found: the sections lost their concrete examples"

    for line_length in (88, 120):
        for section_id, index, code in blocks:
            example = tmp_path / f"{section_id}-{index}.py"
            example.write_text(code, encoding="utf-8")
            proc = subprocess.run(  # noqa: S603
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "format",
                    "--check",
                    "--no-cache",
                    f"--line-length={line_length}",
                    str(example),
                ],
                capture_output=True,
                text=True,
            )
            assert proc.returncode == 0, (
                f"{section_id} example {index} is not ruff-format-clean at width {line_length}:\n"
                f"{proc.stdout}{proc.stderr}"
            )


def test_no_review_date_has_passed():
    """A section whose review_by is in the past is overdue, loudly.

    Every row's 制度変更ウォッチ names the date its primary sources must be
    re-checked by (the watch items are the section's half-life: OWASP
    editions rotate, CA chains rotate, statutes move). Nothing else in the
    repo surfaces a passed date -- the MCP inventory carries review_by but
    nobody is required to read it -- so this pin is the reminder: the fast
    tier runs on every push and the scheduled test run, so an overdue
    section reddens CI until someone re-checks the sources and bumps
    review_by (or supersedes the row). Reviewers other than the maintainer
    can do the re-check; the bump itself is a versioned registry edit.
    """
    today = datetime.now(tz=UTC).date()
    overdue = []
    for row in _load_registry():
        review_by = _datestr(row["review_by"])
        if review_by is not None and review_by < today.isoformat():
            overdue.append(f"{row['id']}: review_by {review_by}")
    assert not overdue, (
        "the following sections' review_by dates have passed -- re-check each "
        "section's primary sources, update the body, and bump the row's version "
        "and review_by (or supersede the row):\n  " + "\n  ".join(overdue)
    )


def test_kyushu_ntp_denylist_and_detector():
    """The first section names the retired identifiers and ships a detector."""
    rows = [row for row in _load_registry() if row["id"] == "region-kyushu-ntp"]
    assert rows, "the kyushu-ntp sample section must stay registered"
    text = (TOP / str(rows[0]["file"])).read_text(encoding="utf-8")
    for identifier in ("133.100.9.2", "133.100.11.8", "clock.nc.fukuoka-u.ac.jp"):
        assert identifier in text, f"retired identifier {identifier} must be named"
    spans = TRIGGER_SPAN_RE.findall(text)
    assert spans, "the section must document its T1 trigger regex"
    hit_topic = hit_retired = False
    for span in spans:
        pattern = re.compile(span)
        hit_topic |= bool(pattern.search("chrony"))
        hit_retired |= bool(pattern.search("server 133.100.9.2"))
    assert hit_topic and hit_retired, f"no documented trigger matches both a topic and a retired id: {spans}"
