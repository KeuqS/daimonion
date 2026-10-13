# Verification Architecture

Which layer of this repository's verification proves what, what each layer
costs, and the rules a new check has to satisfy before it lands.

This page is the written contract behind three things that already exist:
the tier selectors in `Taskfile.yml` / `pyproject.toml`, the witness tiers in
`tests/test_witness_matrix.py`, and the support levels in
[`support.yml`](../reference/support.md). Every number here is measured; the
source command for each one is listed in
[Where the numbers come from](#where-the-numbers-come-from).

The short version: the questionnaire's **input space** is proven by Z3, the
**rendered output** of every leaf is proven by declarative invariants, and a
bounded sample of the leaves is **executed** for real. Three layers, three
different jobs — no layer replaces another. (How these mechanisms map onto
*where wrongness comes from* and *when it gets noticed* — the drift matrix —
is a different axis again: [Drift Detection](drift-detection.md).)

## The three layers

| Layer | Proves | Cannot prove | Input | Measured unit cost |
|---|---|---|---|---|
| **L1 — input space** | every `when` is satisfiable, no contradictory or unreachable combination exists, and the leaves can be enumerated | anything about what the answers *render* | `copier.yml` + `questions/*.yml` | milliseconds, no render |
| **L2 — output invariants** | every leaf's render satisfies its declared file-set and content predicates | install, run, network, docs build — anything needing a venv or an external tool | all **272** leaves | **≈0.6 s/leaf** serial; the 234-leaf space of 2026-09-18 measured **≈20 s** with 16 xdist workers and the session render cache (scale linearly for today's 272) |
| **L3 — execution** | the generated project actually syncs, tests, type-checks and builds its docs | enumeration — it runs a sample, so it is evidence for those leaves only | a bounded sample of **8** leaves | **13–24 s/case**; the whole 8-leaf sample 132–195 s |

### L1 — the input space (Z3)

`tools/when_model.py` encodes each area gate's `when` expression for Z3 (the
tokenizer, `when_expr_satisfiable` and the string domains), and
`tests/test_copier_structure.py` asks the model two questions of the
questionnaire: is every `when` satisfiable, and does the sweep detect typo'd
gates, self-contradictions and impossible genre combinations (the detectors
have meta-tests that break them on purpose to prove they still detect).
`tools/z3_witnesses.py` turns the same model into the leaf list
(`tests/matrix/witnesses.jsonl`, 272 leaves), and
`tests/test_witness_matrix.py::test_witness_leaves_match_the_generator` keeps
the committed list equal to what the generator enumerates.

L1 **cannot** say anything about rendered content, cross-file consistency, the
equivalence of two task definitions, or whether a generated project runs: those
need Jinja + copier + filesystem execution semantics, which are outside Z3.

The Z3 side of `when` is a *projection* (re-implementation) of Jinja's
evaluation, so L1's green is only as strong as that projection. What keeps it
honest is `tests/test_when_model.py`: for every declared leaf it asks copier's
own questionnaire machinery (`Worker._ask` + `Question.get_when`) every
templated `when` — 48 expressions, 9,840 verdicts — and compares that verdict
with the model's. Six probe answer sets then vary the values the leaf space
holds at their copier defaults, for 10,128 comparisons in total, and the test
asserts **per expression** that both polarities were seen: a `when` whose inputs
nothing varies fails instead of quietly proving half of it. It also checks that
the string domains the production callers pass contain every answer copier
actually gives. The test states its own narrowing — concrete assignments rather
than abstract satisfiability, the questionnaire's current expressions, and the
leaf space plus those probes — while the abstract reachability side stays with
the sweeps in `tests/test_copier_structure.py`. Treat "Z3 is green" as "the
input space is honestly enumerated", never as "the template is correct".

### L2 — output invariants over every leaf

The witness `fast` tier renders every leaf with copier (`skip_tasks=True`, no
venv), asserts the leaf's declared artifact set (present *and* absent files),
and runs `ruff format --check` / `ruff check` over the rendered Python. Renders
go through `tests/render_cache.py`, so every tier sharing the same answers pays
for one copier run; the cache is fingerprint-addressed and lives in the
session's temporary directory.

This is the layer that grows best: cost is linear in leaves, and one leaf is
sub-second. It **cannot** express anything that requires the rendered project
to be installed or executed — a leaf whose file set and content predicates are
all correct can still fail to `uv sync`, fail its own pytest, or fail
`mkdocstrings`. That residual is exactly what L3 exists for.

### L3 — bounded execution of a sample

The witness `full` tier takes 8 leaves from `FULL_SAMPLE`: one per project
family whose checks run on a bare runner, plus the one gate-off leaf that
switches the agent prompts on. Each gets `uv sync`, the generated project's own
pytest, `basedpyright`, and its docs build. Every leaf getting this treatment
would be ~10 hours, so the sample is a deliberate bound; ros2 is out of the
sample entirely (its generated recipes need `/opt/ros/$ROS_DISTRO`, not a bare
runner). The leaves the sample does not cover stay in L2.

L3 **cannot** generalize. It is evidence for eight leaves, not for the other
197, and it is not a cheaper way to run L2 — it is the only way to observe the
external toolchain. See [Why L3 stays](#why-l3-stays-the-evidence) for what
keeping it has already caught.

## Tiers: the commands and their budgets

A tier is a contract, not a habit. `fast` means "the edit loop stays inside its
budget"; `heavy` means "this builds a venv or talks to the network". When a
check moves between tiers, the budget moves with it.

| Tier | Command | Selector | What runs |
|---|---|---|---|
| Edit loop | `task test-fast` | `-m "not heavy and not slow and not meta and not network"` | L1 + L2 + everything that neither builds a venv nor touches the network |
| Cost ledger guard | `task test-meta` | `-m meta` | the guards in `tests/test_marker_drift.py`: the venv/network marker scan, the tier-membership check, the cost-staleness check and the leaf-space budget |
| Slow | `task test-slow` | `-m slow` | the serial 272-leaf batch runner (`tools/batch.py` over `tests/matrix/witnesses.jsonl`) |
| Pre-push / nightly | `task test-heavy` | `-m heavy` | L3: `uv sync` + the generated project's pytest / type check / docs build (`network` follows where the case downloads) |
| Witness render | `uv run --no-sync pytest -q tests/test_witness_matrix.py -m fast` | `fast` | L2 over all 272 leaves |
| Witness execution | `uv run --no-sync pytest -q tests/test_witness_matrix.py -m full` | `full` | L3 over the 8-leaf sample (those tests are also `heavy` / `network`) |
| Full suite | `task test` | — | everything, with coverage |

The ledger guard is `meta` rather than part of the edit loop because it
re-collects every tier in a pytest session of its own (six startups): it is a
check on the cost contract, not a cost the edit loop can carry. `ci.yml` runs
`task test-meta` as its own job on every push and PR, and `task test` includes
it.

One measured hole remains in that nightly type-check coverage:
`tests/test_generated_typecheck.py` (the heavy tier's `uv sync` + basedpyright
+ pyrefly module) does not render the kaggle answers — the only render whose
dependencies pull the torch cu126 wheels. The weight reason (minutes of
download into a multi-GB venv) is why the module is heavy+network and
nightly-only to begin with; the blocking reason (measured 2026-09-18) is
that a render must reach zero findings to pass — basedpyright enables
`failOnWarnings` by default — and the kaggle scaffold carries 31
reportAny-family warnings (structlog logger typing, DictConfig attribute
access, the hydra decorator). The one error-level defect that measurement
surfaced (a `FixedTrial` passed into an `optuna.Trial`-annotated objective
in the generated `src/utils/modeling/train.py`) is fixed; the decision
record, with the unblocking steps, lives at that module's `TYPECHECK_PATHS`.
The torch-free `data_science` leaf is already executed nightly by the
witness `full` tier.

The numbers themselves are not hand-copied into this page: the table below is
a generated block (tools/gen_docs.py, the same generator that owns the
questionnaire and support tables), rendered from `tests/matrix/tiers.json`.
When a number in it disagrees with the suite, the ledger wins:
`tests/test_marker_drift.py` re-collects every tier and fails on drift, fails
when a row's `measured` date is more than 30 days old, and fails when a row
with a declared `budget_seconds` measures over it.
`UPDATE_TIERS=1 uv run --no-sync pytest -q tests/test_marker_drift.py`
re-records the collected sets — and the Tests column of the tier table in
[test-loop.md](../how-to/test-loop.md), the hand-edited counts this used to
leave behind — after a deliberate tier change.

<!-- BEGIN GENERATED: tier-ledger (tools/gen_docs.py --write) -->
| Ledger row | Selector | Tests | Budget | Measured |
|---|---|---|---|---|
| `test-fast` | `-m "not heavy and not slow and not meta and not network"` | 1176 | 30s (measured 18.6s) | 2026-09-20 |
| `test-slow` | `-m "slow"` | 7 | measured 89.6s | 2026-09-17 |
| `test-heavy` | `-m "heavy"` | 50 | measured 25.7s | 2026-09-17 |
| `test-meta` | `-m "meta"` | 10 | measured 6.6s | 2026-09-17 |
| `test` | `—` | 1243 | measured 178.6s | 2026-09-17 |
| `test-randomly` | `-m "not heavy and not slow and not meta and not network"` | 1176 | measured 22.3s | 2026-09-17 |
| `witness-fast` | `-m "fast"` | 278 | measured 16.9s | 2026-09-18 |
<!-- END GENERATED: tier-ledger -->

The edit-loop budget is **30 s**; anything that pushes `task test-fast` past it
is either marked `slow` / `heavy` / `meta` or is a regression — for venv and
network work the marker-drift guard enforces that structurally, and the
ledger's `test-fast` row carries the budget as `budget_seconds`, which the
same guard compares against the measured wall: the budget is a checked
statement, not prose. The ledger's own guards are out of the loop by the
`meta` marker. The run taken for this page
on 2026-09-14 was **731 tests in 47 s**
(`uv run --no-sync pytest -q -m "not heavy and not slow and not meta"`), on a
machine whose 32 logical CPUs were also carrying unrelated work at load average
64–117. That number measures the contention: the same tree with the guard still
in the selection (738 tests) took 46 s at load 85 in the same session, and the
ledger's earlier 22 s was taken idle on a 717-test tree that other changes have
since grown past. What the guard's removal is worth *on its own* is the ledger's
`test-meta` row (10.5 s, nearly all of it the six pytest startups the membership
check runs); what it is worth inside the loop was below this box's noise. The
count grows as tests land, so read every time here as a dated observation of a
moving suite and take the current numbers from the ledger above.

## Growth rules

Adding a capability is not free, and the cost is predictable:

| Change | Leaf increment | Cost |
|---|---|---|
| One more include layer (composed with all base leaves) | **+76 leaves** | ≈ +45 s serial, ≈ +3 s at 16 workers, ≈ 0 once the render cache holds the answers |
| One more gate-off dimension | +8 base leaves → **+22 leaves** | ≈ +13 s serial, ≈ +1 s at 16 workers |
| One more `project_type` | its base leaves (e.g. +3 base ≈ +8 leaves) | **plus one invariant row** in the single invariant source, **plus one L3 sample leaf** (≈ +20 s) |

!!! warning "Include layers are exclusive today"
    A leaf carries **at most one** include *layer* (measured on today's
    272-leaf space: 146 leaves with none, 124 with exactly one, 2 with two, and of those with one
    9 carry a derived detail the variant leaves answer — 3 the integrations
    detail `include_mcp` and 6 a bot platform — details, not layers, so they do
    not join the product). The layer multiplier is ~2.7×
    rather than the product of four layers because of that exclusivity. Lifting
    it — allowing two layers on one leaf — turns the multiplier into a
    combinatorial product and the leaf count becomes exponential. Any change
    that touches layer composition must declare, up front, whether it keeps
    exclusivity (choose-one) or accepts the product, and the growth table above
    stops applying if it accepts the product.

The growth table is not the whole contract: the leaf space also has a declared
ceiling. `LEAF_BUDGET` in `tests/test_marker_drift.py` — currently **450**
(it landed at twice the then-225-leaf space; the space is 272 today) — fails
the meta guard when
`tools/z3_witnesses.py` enumerates more leaves than that. The additive
increments in the table fit several times over; what the budget turns away is
the multiplicative case above (a lifted exclusivity, or a new axis that
composes with everything already declared), which would otherwise surface only
as the witness fast job creeping toward its 30-minute CI timeout. Raising it
is a decision, not an accident: edit the constant and re-measure the witness
job's wall time into `tests/matrix/tiers.json`.

The conclusion that drives the rules below: growth pushed into L2 stays bounded
(+22 leaves ≈ +1 s parallel, 0 s cached), while growth pushed into L3 is linear
in samples and each sample is 13–24 s. So a new check goes into L2 **unless
there is a reason it cannot be expressed there**.

## Before adding a check: five questions

Answer all five before writing the check; a "no answer" is a design decision
that has not been made yet.

1. **Which existing layer does it sit on?** L1 (input space), L2 (render
   invariant), or L3 (execution). If it is "a bit of both", split it.
2. **What is its leaf increment?** Use the growth table. If it multiplies
   rather than adds, the exclusivity question above must be answered first.
3. **Which invariant row does it need?** Every file the leaf must (or must not)
   have, and every content predicate over it, belongs to the single invariant
   source (TODO §23.4 / §24.4 T6) — never to a second hand-synced dict.
4. **Which tier runs it?** Pick from the tier table and check the budget it
   lands in. A check that builds a venv or touches the network carries `heavy`
   (and `network` when it talks to the network), no exceptions.
5. **Which support level does it get?** `supported` if CI executes it end to
   end, `best_effort` if it is declared and rendered but never executed — and it
   goes into `support.yml` with a measured `why`.

## Non-goals

Stated plainly, because the vaguer version — "Z3 proves the template is
correct" — is false:

- **Z3 proves the input space only.** Satisfiability of each `when`, the absence
  of contradictory or unreachable combinations, and a complete enumeration of
  the leaves. It does not prove anything about what those leaves render.
- **The `when` model is a re-implementation**, so a Z3 green is a statement
  about the model, not directly about Jinja. `tests/test_when_model.py`
  differentially compares the two at every declared leaf and states the limits
  of that assurance (concrete assignments, the current expressions, the leaf
  space plus the probes); nothing beyond those limits is covered by L1.
- **venv builds, real pytest runs, network access, Docker and external CI are
  covered by the heavy tier on purpose.** They cannot be expressed as L2
  predicates over rendered bytes, so they stay in L3 rather than being
  re-declared into a weaker form. The `heavy` tier is a deliberate design
  decision, not debt to be paid off.
- **The goal is the three-part set** — Z3 enumerates the input space,
  invariants cover every leaf's output, sampled execution covers the external
  toolchain — **not** "Z3 alone proves everything". A proposal that argues
  "Z3 already covers it" for a run-time property is arguing the wrong thing.

### Why L3 stays: the evidence

The 8-leaf sample is not ceremony. On 2026-09-13 it failed **three leaves**, all
of them invisible to L2 (whose leaves stayed green at the same time):

1. `project_type=micropython/gate=recommended` — basedpyright exited 3 with
   `File or directory ".../smoke_example" does not exist`: the shared
   `include = ["{{ pkg_dir }}", "tests"]` assumed a package directory that the
   MicroPython layout does not have. The MicroPython branch now excludes the
   package and checks `tests` + `firmware/core` instead (the firmware tree has
   its own `pyrightconfig.json` pass).
2. `project_type=online_judge/.../atcoder` — `just docs` failed with
   `mkdocstrings: accessing 'smoke_example' raises ModuleNotFoundError`: a
   code-submission workspace ships no importable package, so the generated API
   reference had nothing to collect. The competitive-programming layout now
   omits the module nav and the `mkdocstrings` plugin.
3. `project_type=cli/gate=off:use_recommended_agent` — basedpyright exit 1:
   `run(parsed.prompt, model=parsed.model)` passed `argparse.Namespace`
   attributes, which type as `Any`. The generated CLI now parses into a typed
   `_CliArgs` namespace.

All three are fixed, and all three shipped inside a render-only pipeline that
was entirely green. That is the measured justification for holding L3 at a
sample rather than dropping it: the render layers prove the file sets, and only
execution proves the toolchain.

## Support levels

`support.yml` (repository root) is the machine-readable declaration of what
this template keeps working. It uses two levels:

- **`supported`** — executed end to end by the witness `full` tier: `uv sync`,
  the generated project's own pytest, basedpyright and its docs build.
  `tests/test_support_matrix.py` asserts the declared `supported` rows are
  exactly the ledger's `tier: full` leaves, so a claim here is a measured one.
- **`best_effort`** — declared so the questionnaire's existing answers keep
  rendering, but never CI-gated for execution. The witness `fast` tier still
  renders and ruff-checks these leaves; a regression that only breaks install or
  run is not caught for them.

Two related pieces of the same vocabulary live in `support.yml` as well: the
per-entry `why` (the measured evidence for the assigned tier) and
`tier_policy`, which maps a *class* of leaf to a tier. `none` is reserved for a
future exclusion and is declared per leaf as `tier: none` plus a `reason` in
`tests/matrix/witnesses.json`; no leaf uses it today, because every declared
leaf has a recorded run.

`support.yml` is the source, not the documentation: `tools/gen_docs.py --write`
renders [the support matrix](../reference/support.md) and the README summary
from it, and `--check` fails CI when those drift.

## Where the numbers come from

| Measurement | Source command | Recorded |
|---|---|---|
| 272 leaves, 146 with no include layer, 124 with exactly one, 2 with two (9 carry a derived detail: 3 the MCP integrations detail, 6 a bot platform) | `tests/matrix/witnesses.jsonl` (count of `include=` per leaf) | 2026-09-22, current tree (integrations-details and bot-platform variants) |
| L1 model vs real Jinja: 10,128 comparisons (9,840 leaf verdicts + 6 probes × 48 expressions), both polarities asserted per expression | `uv run --no-sync pytest -q tests/test_when_model.py`; with the structure sweeps, `uv run --no-sync pytest -q tests/test_when_model.py tests/test_copier_structure.py` → 16 passed, 1 xfailed | 2026-09-14, this tree |
| L2 ≈ 0.58 s/leaf at the 205-leaf tree of the 2026-09-13 audit (119 s ÷ 205; that tree's full render ≈ 11 s at 16 workers + cache) | the serial batch runner's `--durations` entry (119 s) in the 2026-09-13 audit | TODO §23.0 / §24.0 P4 / §24.1 |
| L3 13–24 s/case; the 8-leaf sample 132–195 s | `uv run --no-sync pytest -q tests/test_witness_matrix.py -m full` | TODO §24.0 P6 (PLAN §W9 top-5) |
| L3 found 3 defects L2 missed, with L2 green on every leaf | same 8-leaf sample; `-m fast` for the render layer | TODO §24.0 P6 |
| Edit loop 731 (of today's 732) tests in 47 s, load average 64; the same tree with the guard still in the selection, then 738 tests, took 46 s at load 85 | `uv run --no-sync pytest -q -m "not heavy and not slow and not meta"` | 2026-09-14, this tree — a dated observation; the current per-tier counts are the ledger row below |
| Ledger guard: 7 tests, 10.5 s (six pytest startups: the membership check re-collects every tier) | `uv run --no-sync pytest -q -m meta` | 2026-09-14, this tree — the ledger row, measured with unrelated work on the machine |
| Witness fast job: 278 tests (272 renders + six leaf-list checks), 4.5 s warm on the dev machine (5.1 s at the 234-leaf tree of 2026-09-18), against the job's 30-minute timeout | `uv run --no-sync pytest -q tests/test_witness_matrix.py -m fast` | 2026-09-22, this tree — the ledger's `witness` row; a PR runner is always cold |
| Per-tier counts, marker expressions, re-measure commands and wall times (the tier ledger and the witness fast job) | `tests/matrix/tiers.json`; re-collect with `UPDATE_TIERS=1 uv run --no-sync pytest -q tests/test_marker_drift.py`, fill `wall_seconds`/`measured` by hand from a `time` run of the row's own `command` | 2026-09-14, this tree |
| Growth table's +76 / +22 leaf increments and their second costs | derived in the 2026-09-13 audit from the ledger's leaf counts and the 0.58 s/leaf unit | TODO §24.1 |
| Leaf-space ceiling: `LEAF_BUDGET` = 450 (landed at twice the then-225-leaf space) | `LEAF_BUDGET` in `tests/test_marker_drift.py`, checked against `tools/z3_witnesses.py`'s enumeration on every meta run | declared, citing §24.1 — the enforcement is the record |
| Edit-loop budget of 30 s (a contract, not a measurement) | declared for the tiers in the 2026-09-13 audit | TODO §24.2 |
| "all 272 leaves executed would be ~10 hours" | the `FULL_SAMPLE` rationale comment: 272 × (venv build + docs) at ~3 min | `tests/test_witness_matrix.py` |
