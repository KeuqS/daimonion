# Patches

PR-ready diffs authored against `copier-org/copier`. The two frozen,
ready-to-file patches live in `notes/upstream-drafts/patches/` (see
"準備済みのもの" in `notes/COPIER_UPSTREAM.md`); new work lands here.

## Status

| Patch                                                        | Upstream target                              | Status        |
| ------------------------------------------------------------ | -------------------------------------------- | ------------- |
| `notes/.../unsafe-refusal-message-and-exit-codes.patch`      | `errors.py`, `docs/faq.md`, `tests/test_unsafe.py` | Ready (frozen) |
| `notes/.../answers-file-error-hint.patch`                    | `errors.py`, `tests/test_cli.py`             | Ready (frozen) |
| `cli-missing-answers-batch.patch` (this directory, F3) | `copier/_main.py`, `tests/test_copy.py` | Implemented 2026-10-04 on `kasi-x/copier` branch `f3-missing-batch` (pushed, PR unfiled per AI_POLICY — file manually). Upstream tests green: `test_copy` + `test_cli` + `test_config` + `test_answersfile` (323 passed). |
| `vcs-stale-tag-warning.patch` (this directory, F5) | `copier/_vcs.py`, `_template.py`, `errors.py`, `tests/test_vcs.py` | Implemented 2026-10-05 on `kasi-x/copier` branch `f5-stale-tag-warning` (pushed, PR unfiled per AI_POLICY). Emits `StaleTagWarning` on the implicit latest-tag resolution when the tag is behind the default branch; silent on explicit `--vcs-ref`. Tests: `test_vcs` + `test_copy` green (229+205). |
| `cli-trust-discoverability.patch` (this directory, F6 docs+message half) | `copier/errors.py`, `docs/generating.md` | Implemented 2026-10-05 on `kasi-x/copier` branch `f6-trust-discoverability` (pushed, PR unfiled per AI_POLICY). The `settings trust add` CLI sketch from FEATURES F6 remains unfounded — deliberately split: this patch is the docs+refusal-message half, the CLI subcommand is a separate upstream conversation. |
| `cli-pretend-dry-run.patch` (this directory, F7 reduced scope) | `copier/_main.py`, `_cli.py`, `docs/configuring.md`, `tests/test_copy.py` | Implemented 2026-10-05 on `kasi-x/copier` branch `f7-pretend-summary` (pushed, PR unfiled per AI_POLICY). `--pretend` already covered F7's preview ask; this adds the missing summary line and documents it as the dry-run path. |

## Compatibility Verification (2026-10-11)

Verified against installed `copier 9.18.1`:
- `cli-missing-answers-batch.patch`: applies cleanly (`copier/_main.py`)
- `cli-pretend-dry-run.patch`: applies cleanly (`copier/_cli.py`, `copier/_main.py`)
- `cli-trust-discoverability.patch`: applies cleanly (`copier/errors.py`)
- `vcs-stale-tag-warning.patch`: applies cleanly (`copier/_template.py`, `copier/_vcs.py`, `copier/errors.py`)
All 4 patches apply with zero hunks failed, ready for upstream PR filing.

## Naming

`patches/<area>-<slug>.patch`, e.g. `cli-missing-answers-batch.patch`.
`<area>` is the upstream path area (`cli`, `config`, `docs`, `vcs`, ...),
`<slug>` the change in a few words.

## Creating

From the fork checkout, on a topic branch branched off `master`:

```sh
git format-patch -1 --stdout HEAD > patches/<area>-<slug>.patch
```

## Verifying

```sh
./scripts/verify-patch.sh patches/<area>-<slug>.patch /path/to/copier-checkout
```

It runs `git apply --check`, lists touched files, and suggests the upstream
tests covering them. Run those tests per upstream `CONTRIBUTING.md` before
filing — and file it yourself, in your own words (`AI_POLICY.md`).
