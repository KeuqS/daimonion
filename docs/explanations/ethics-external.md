# Ethics Sections as an External Source

The ethics appendix (`_shared/ethics/`, surfaced into generated `AGENTS.md`)
is the one part of this template whose content has its own review cadence —
OWASP revisions, FIPS finalization, Let's Encrypt chain ceremonies, regional
law — independent of the template's release cycle. It now lives upstream as
its own repository — **`good-future-codex`**, the canonical section texts of
the Good-future charter — so other templates and projects can consume the
same reviewed text. This page records the design for that split: what moves,
what stays, and why the sync happens at vendor time and never at render time.

The codex is itself one layer of a larger legal pipeline:

```text
open-law            law-map                 good-future-codex      this repo
world legislation   obligation graph         reviewed prose         vendored
-> unified corpus -> jurisdiction groundings -> AGENTS.md sections -> snapshot
```

`open-law` fetches statutes, `law-map` organizes them as machine-readable
technical obligations (statute, precedent, and guidance share one
functional-equivalence node), and `good-future-codex` renders the human-
and-agent-facing prose this repo vendors.

## Why not fetch at render time

The tempting version — `copier copy` pulls the latest ethics text from the
external repo — breaks the property the whole verification stack rests on:

- **A render must be a pure function of the template's git tree.** The Z3
  witness leaves, the render invariants, and the update rehearsal all assume
  that the same commit produces the same output. A network fetch makes the
  output depend on the day it ran.
- **Offline contract.** `task check` / `task type-check` deliberately exclude
  network so a fresh clone works offline; a render-time fetch would be the
  first violation.
- **`copier update` determinism.** The update path diffs the recorded
  revision against the target revision. If the text between them can drift
  outside git, the merge produces diffs no commit explains — the exact class
  of bug the rehearsal exists to catch.

So the external repo is the *source of truth for content*, and this repo
*vendors* a snapshot. The render never sees the network.

## What moves, what stays

The split is content vs. wiring — the line is drawn at "does this text
reference a template flag":

| Moves to the external repo | Stays here |
| --- | --- |
| Section bodies (`*.md.jinja` prose) | `REGISTRY.yml` — the gate column names template flags (`scraping_effective`, `oj_code`, `mcp_effective`); moving it would leak the flag namespace into a repo that should not know it exists |
| `review_by` dates and watch metadata | The `when:`/audience mapping (which leaf classes get which section) |
| Source citations in each section's `why` | The enforcement level (L0/L1/L2) and the invariants.yml predicates that check it |
| The `_template.md.jinja` section shape | `tools/ethics.py` presence triggers and the appendix assembly in `AGENTS.md.jinja` |

The external repo holds **flag-agnostic content**: each section is a file
with frontmatter (`id`, `audience`, `review_by`, `sources`) and a prose body.
It must not contain `{{ scraping_effective }}`-style conditionals — gating is
this repo's job, applied at vendor time by the registry row.

## The sync contract

Same pattern as `check-upstream-fork`: a scheduled workflow diffs the
external repo's sections against the vendored copy and opens a PR when they
diverge. A human reviews the diff (a section edit is a content decision, not
a merge), then the vendor commit lands. The marker file records which
external SHA is vendored, so the check only fires on genuinely new upstream
work — the permanent-red trap the fork check escaped.

```text
ethics-sections (source of truth)      daimonion
┌──────────────────────────┐         ┌────────────────────────────┐
│ sections/*.md.jinja       │  sync   │ _shared/ethics/ (vendored) │
│  flag-agnostic prose      │ ──────► │ REGISTRY.yml (flag gating) │
│  frontmatter: id,         │   PR    │ invariants.yml predicates  │
│   audience, review_by     │         │ tools/ethics.py triggers   │
└──────────────────────────┘         └────────────────────────────┘
        ▲ own review cadence                 ▲ scheduled sync opens PR
        (OWASP / FIPS / LE watch)            on content drift only
```

## Versioning

The vendored snapshot is pinned to an external SHA (the marker file), not a
floating `main`. A template release therefore ships a *known* ethics text —
the release notes can name it — and a `copier update` between two template
tags shows the ethics diff as part of the template diff, reviewable like any
other change. Bumping the vendored SHA is a deliberate act (the sync PR),
which is what keeps a surprise upstream edit out of a user's `copier update`.

## Status

The split is done: `good-future-codex` is live under the
[ConstitutiveTemplates](https://github.com/ConstitutiveTemplates)
organization alongside `open-law` (legislation scraping) and `law-map`
(the obligation graph). For a single consumer the vendor machinery would be
cost without benefit; the codex now has two consumers (this template and
`law-map`'s section references), so it pays for itself.

Two contracts hold the pipeline together:

- **Vendored snapshot**: `_shared/ethics/` is pinned to a codex SHA in
  `.ethics-vendored`; the weekly `ethics-sync.yml` workflow runs
  `tools/check_ethics_drift.py` and opens an issue when codex `main` moves
  ahead of the marker.
- **Section ids**: `law-map` obligations link prose via `related_sections`
  ids of the form `<tier>-<slug>`, which resolve to
  `sections/<tier>/<slug>.md.jinja` in the codex (e.g.
  `baseline-personal-data` → `sections/baseline/personal-data.md.jinja`).
  `law-map check --codex <checkout>` fails on an unresolvable id, and
  `law-map export` emits skeletons in that same shape.

The weekly `scheduled-check.yml` job `law-map-review-by` runs
`law-map check --codex` against fresh checkouts of both repos and fails when
a grounding's `review_by` has expired — a different corpus than the vendored
drift check (prose SHA vs. obligation freshness), so a red run names exactly
one thing to fix.

The weekly `e2e-ecosystem.yml` workflow closes the remaining gap: it runs
the whole chain in one job — `law-map export` plus
`law-map validate --codex` against a fresh codex checkout, then
`tools/validate.py` in the codex, then a `daimonion new --preset web-api`
render of this checkout whose `AGENTS.md` must still carry the
codex-derived ethics sections (the unconditional active registry rows).
Each pairwise check can stay green while the handoff between two repos
breaks — an export schema change that drops the section header, a gating
change that silently drops a section from the render — so a red run here
means a downstream silent break, and it opens an issue like the other
scheduled drift checks.
