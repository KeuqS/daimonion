# Processing Flows

Four end-to-end flows in one place: how answers become a project, how adoption
stays reversible, how legal content reaches `AGENTS.md`, and which CI workflow
watches what. Each diagram names real files, jobs, and tools — the prose under
it points at the implementation.

## Questionnaire to generated project

`questions/` declares the gates, `tools/z3_witnesses.py` enumerates the leaf
space, `tools/batch.py` renders each leaf through copier, and the invariant
layer checks the output. Details live in [Verification Architecture](verification.md).

```mermaid
flowchart TD
    Q["questions/*.yml<br/>(gates + layers)"] --> Z3["tools/z3_witnesses.py build()"]
    Z3 --> WL["tests/matrix/witnesses.jsonl<br/>(272 leaves)"]
    WL --> TW["tests/test_witness_matrix.py<br/>(render each leaf via copier)"]
    TW --> BR["tools/batch.py render()<br/>(skip_tasks=True, no venv)"]
    BR --> GP["generated project tree"]
    GP --> IV["tools/invariants.py<br/>+ tests/matrix/invariants.yml"]
    IV --> TRI["tests/test_render_invariants.py<br/>(content predicates)"]
    TRI --> OK(["artifacts: src/, tests/,<br/>docs, CI, AGENTS.md"])
```

The render is a pure function of the template's git tree: the same commit
produces the same output. Anything that would break that (network fetches,
per-render stamps) is excluded or masked — see `mask_render_stamps` in
`tools/batch.py`.

## Adopt and update: the crash-safe transaction

```mermaid
stateDiagram-v2
    [*] --> Planned: adopt() plans answers (detect.detect + derive_answers)
    Planned --> DryRun: --dry-run
    DryRun --> [*]
    Planned --> Journaled: _write_journal (.copier-adopt-journal.json, fsynced)
    Journaled --> Rendered: batch.render (skip_if_exists, overwrite=False)
    Rendered --> Verified: _verify (changed/removed/created)
    Verified --> RolledBack: existing file touched, _undo_run via _roll_back
    Verified --> Merged: clean add-only, _finish_with_merges
    Merged --> Committed: _remove_journal
    Committed --> [*]
    RolledBack --> [*]
    Journaled --> Killed: process killed (journal stays on disk)
    Rendered --> Killed
    Killed --> Recovered: adopt.py --recover (adopt_journal.recover)
    Recovered --> [*]
```

Two layers cover two failure classes: the in-process rollback
(`_signals_roll_back` in `tools/adopt_crash.py`, plus `_roll_back` in
`tools/adopt_tree.py`) handles failures the process survives; the journal
(`JOURNAL_NAME` in `tools/adopt_types.py`) covers kills — while it exists,
the run has not committed, so `--recover` can finish the undo. A stale
journal blocks the next run (exit 4) until it is recovered.

## Ethics and law distribution pipeline

Legal content flows downstream through three external repositories before it
reaches a generated `AGENTS.md`. The full contract is
[Ethics as External Source](ethics-external.md); this is the same chain as a
pipeline.

```mermaid
flowchart LR
    OL["open-law<br/>(world legislation corpus)"] --> LM["law-map<br/>(obligation graph,<br/>related_sections ids)"]
    LM --> CX["good-future-codex<br/>(reviewed prose,<br/>sections tier/slug,<br/>review_by dates)"]
    CX --> VE["_shared/ethics/<br/>(vendored snapshot:<br/>MANIFEST.yml, FLAGS.yml,<br/>REGISTRY.yml, .ethics-vendored)"]
    VE --> CC["tools/check_ethics_contract.py<br/>(MANIFEST vs FLAGS vs REGISTRY)"]
    CC --> GA["tools/gen_ethics_appendix.py<br/>--check in CI"]
    GA --> AJ["_shared/ethics-appendix.jinja<br/>(generated)"]
    AJ --> AM["template AGENTS.md.jinja<br/>(ethics appendix,<br/>agents_md_effective gate)"]
    AM --> ET["tools/ethics.py match()<br/>(MCP check_ethics,<br/>presence triggers)"]
```

Watchers on the chain, each naming exactly one failure: `ethics-sync.yml`
(prose drift vs. codex `main`, `tools/check_ethics_drift.py`),
`scheduled-check.yml` job `law-map-review-by` (expired `review_by`
groundings, `law-map check --codex`), and the `e2e` job in
`e2e-ecosystem.yml` (`law-map export` + codex validate + a render whose
`AGENTS.md` must still carry the codex-derived sections). The generated
project's own `legal-check` task (`_tasks.jinja`, `law-lint diff --strict`)
is the downstream consumer, not a watcher.

## CI at a glance: four lanes

Each scheduled lane is staggered so a red run names exactly one cause.
`ci.yml` handles push/PR plus the nightly heavy tier; the weekly lanes only
watch drift that push/PR CI cannot see.

```mermaid
flowchart TD
    subgraph push["ci.yml (push main/tags, pull_request, nightly 0 3)"]
        CH["changes<br/>(docs-only gate)"] --> T["test (test-fast)<br/>test-meta"]
        L["lint (lint,type-check)"]
        H["hygiene"]
        T --> D["docs"]
        T --> EX["example (main only)"]
        T --> REL["release (tags only)"]
        HN["test-heavy + test-randomly<br/>(schedule only)"]
        T --> REQ["required-checks-passed"]
        L --> REQ
        H --> REQ
        D --> REQ
    end
    subgraph sched["scheduled-check.yml (weekly TUE 07:00)"]
        SL["lint / test / docs<br/>(toolchain drift)"]
        PX["pixi-render-test<br/>poetry-render-test"]
        LAW["law-map-review-by"]
        ODI["open-drift-issue"]
        SL --> ODI
        PX --> ODI
    end
    subgraph per["periodic.yml (weekly WED 08:00)"]
        LC["linkcheck (lychee)"]
        PR["patch-rot<br/>(copier contribution branches)"]
    end
    subgraph sc["scorecard.yml (push main, weekly SAT 01:30)"]
        AN["analysis<br/>(ossf/scorecard-action + upload-sarif)"]
    end
```

Adjacent but separate: `pr.yml` (job `validate-pr-title`, conventional-commit
titles), `ethics-sync.yml` (weekly codex drift), `e2e-ecosystem.yml` (weekly
FRI cross-repo chain), `dependency-audit.yml` (weekly pip-audit),
`security.yml` (zizmor workflow audit), and `update-rehearsal.yml` (the
`copier update` path the adopt flow depends on).
