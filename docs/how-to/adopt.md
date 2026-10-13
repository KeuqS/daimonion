# How to adopt the template into an existing project

`tools/adopt.py` is the reversible driver: it plans the adoption, applies it,
verifies what happened, and undoes what it did — whether it failed, was
interrupted, or was killed outright.

What that means precisely, because the word "transactional" alone overstates
it:

| How the run ends | What the project looks like afterwards |
| --- | --- |
| Verified and fitted | The adoption, plus a note of what to wire by hand |
| A failure at any point (a collision it did not skip, a merge that rewrote a line, an unexpected exception) | Exactly as it was before the run, byte for byte, directories included; exit 1 |
| Ctrl-C / `SIGINT` / `SIGTERM` mid-run | The same rollback, from a signal handler; exit 1 |
| `SIGKILL`, a crash, or a power cut | Whatever the process had written stays on disk **with its journal**; `--recover` puts the project back exactly as it was (see [If the run is killed](#if-the-run-is-killed)) |

```shell
task adopt DIR=/path/to/project CLI_ARGS="--dry-run"   # plan only
task adopt DIR=/path/to/project                        # plan, then apply
task adopt DIR=/path/to/project CLI_ARGS="--recover"   # undo a killed run
```

## If the run is killed

Nothing the driver writes is unrecoverable. Before it changes the first byte
of your project it writes a journal — `.copier-adopt-journal.json`, inside the
target — holding the old bytes of every file the run may modify and the path
of every file it may create, and `fsync`s it and its directory. The journal is
removed only when the run has committed or been rolled back, so finding one
means the run it describes did not finish: the project is in a state nobody
chose, and a new adoption refuses to start over it (exit 4) rather than
building on an accident. A `--dry-run` refuses too — a plan built from that
state would be a plan about an accident.

```shell
task adopt DIR=/path/to/project CLI_ARGS="--recover"
# or, directly:
python tools/adopt.py /path/to/project --recover
```

Recovery puts the recorded old bytes back, deletes every file that was not
there before the run, removes the directories it created, and removes the
journal last. It is idempotent: running it when the tree already matches
rewrites nothing, and running it with no journal at all does nothing — both
exit 0, so a retry is always safe. `--json` prints the result (`found`,
`applied`, `restored`, `removed`) instead of the report.

```console
$ python tools/adopt.py /path/to/project --recover
target:  /path/to/project
journal: /path/to/project/.copier-adopt-journal.json
recovered: 1 file(s) restored, 45 removed
  nothing of the interrupted run is left; adopt again when you are ready

$ python tools/adopt.py /path/to/project --recover      # nothing left to do
target:  /path/to/project
journal: /path/to/project/.copier-adopt-journal.json
nothing to recover: this project has no journal
  no journal: nothing to recover
```

`--recover` exits 0 when it recovered something or found nothing to recover,
and 2 when the journal is there but cannot be used (unreadable, or written by
a run in another project — the refusal names which). It never deletes a journal
it cannot read, because one that is unreadable was written before the project
was touched: if nothing has changed since, deleting it by hand is safe.

The one thing the journal cannot cover is the instant of the commit itself:
the run deletes the journal without flushing the rendered files to disk, so a
power cut in that same instant can lose *new* content. Every crash before that
point is recovered exactly; the commit is the last thing that happens.

## Why a driver and not just `copier copy`

Three failure modes, all measured against copier 9.18.1:

| Failure | What copier does on its own |
| --- | --- |
| A file the template also ships already exists (`.github/workflows/ci.yml`, `renovate.json`, ...) | Stops with `Interactive session required: Consider using --overwrite`, exit 1, **after** writing every file it had already rendered — the project is neither before nor after |
| `--overwrite` to get past that | Replaces those files, including collisions nobody listed |
| `copier copy <url>` without `--vcs-ref` | Expands the latest **tag** — while this fork's newest tag was still an inherited upstream one, that silently rendered the old template. Since the 6.0.0 fork detach the newest tag is the fork's own release, so the plain command is correct |

The driver closes all three:

1. **No collisions**: the collisions come from `tools/detect.py` and are passed
   to copier as `skip_if_exists`, so your files are left alone and everything
   else is still added. Nothing is passed as `--overwrite`.
2. **Rollback**: the run renders with `overwrite=False` and then verifies that
   no existing file changed (by content) and none disappeared — comparing
   file *and* directory sets. If anything did, the originals are restored,
   everything the run created is deleted (empty directories included), and the
   command exits 1 reporting what happened. A failed adoption leaves the
   project exactly as it was; a run that ends any other way leaves the journal
   for [recovery](#if-the-run-is-killed).
3. **The right revision**: `ref` is the latest tag *only if that tag declares
   the same questions as this checkout*; otherwise the default branch is used
   and the report says why ("latest tag 5.4.0 does not carry this
   questionnaire (missing 93 question(s), e.g. ...); using main"). Since the
   fork tags its own releases that guard is normally satisfied, and it is the
   pre-detach tags — the ones the driver exists to defend against — that
   still trip it. Pass `--ref HEAD` to expand the working tree instead,
   uncommitted changes included — that is the local-iteration case.

## What it merges into the files you already have

After a successful render, whatever the template *would* have generated is
merged into the files you have instead of being skipped (the template is
rendered into a temporary directory for exactly this, since your files are
the protected ones). Every merge is **additive**: your lines and values are
never rewritten, and one that cannot be done safely is reported instead.

| Your file | What gets merged |
| --- | --- |
| `pyproject.toml` | dependencies and `[tool.*]` keys (below) |
| `.gitignore` | the template's patterns you do not have, appended under a comment |
| `Makefile` / `justfile` | the recipes/targets you do not have, body included, appended |
| `.github/workflows/ci.yml` | the read-only jobs (`lint`, `test`, `hygiene`) appended when you approve it, otherwise a second workflow, `copier-ci.yml`, added next to it |
| `Taskfile.yml`, `tasks.py`, `duties.py` | reported, and appended when you approve it (see below) |

`Taskfile.yml` and the Python task files are offered as a question rather than
merged silently, and after writing they are verified: every task that was
there must still be there, unchanged, or the write is undone. For
`Taskfile.yml` the append is only valid when `tasks:` is the file's last
top-level key — when it is not, the list stays a report. `tasks.py` /
`duties.py` are merged with `ast`: only the functions you are missing are
appended, the existing source is compared byte for byte afterwards, and when
the `@task` / `@duty` decorator is not imported in your file nothing is
written at all (the report names the import you would need).

The CI caller keeps the **read-only checks** (`lint` from `_tasks.yml`,
`test`, `hygiene`) and deliberately drops `dist`, `release` and `docs`: those
build artifacts, publish releases, or push GitHub Pages, and a second
publisher is worse than none. It is generated by cutting job blocks out of
the rendered workflow rather than by a YAML round-trip — PyYAML reads the
`on:` key as the boolean `true`, so re-dumping it would emit an invalid
workflow. You are asked where those jobs go: the default is the
non-destructive placement (`copier-ci.yml` beside your workflow); answering
yes appends them to your `ci.yml`, keeping your existing jobs untouched (the
file is re-parsed and the old content must still be there, or the write is
undone), and a job name you already use is reported instead of overwritten.
Delete whichever of the two workflows you do not want.

The rules for `pyproject.toml` are deliberately narrow:

| Rule | Why |
| --- | --- |
| Only add names you do not already declare | An existing requirement is yours; a merge that rewrites pins is a merge that starts fights |
| A name you declare differently is **kept and reported** (`deps.differing`) | "You have `structlog>=9`, the template pins `structlog`" is information, not a conflict to resolve |
| Never reorder or reformat anything else | The edit goes through tomlkit, which round-trips your comments and layout |
| Idempotent | Running the adoption (or the merge) twice adds nothing the second time |
| Extras are reported, not invented | `[project.optional-dependencies] experiment` is opt-in per project — the note lists it |
| No `[project]` and no `[tool.poetry]` table | Nothing to merge into: the list is printed to wire by hand |
| Poetry layouts get the requirements translated (`httpx>=0.27` → `httpx = ">=0.27"`) | Extras and markers need table syntax, so those are reported instead of guessed |
| `[tool.*]` keys merge one by one, under the same "add only" rule | `ruff.lint.select`, the `typos` word lists, `pycodestyle` limits and the rest of the lint config land in your file |
| A `[tool.*]` value that names **this** project is reported, not copied | `basedpyright.include = ["src/probe"]`, `pytest.testpaths`, `vulture.paths`, `coverage.paths.source` and a `per-file-ignores` entry for `src/probe/...` are the template's layout, not your setting |
| Tables that describe how a project is built or resolved are skipped | `[tool.setuptools*]`, `tool.uv`, `tool.pixi`, `tool.poetry`: those encode the template's layout and index choices |

Every merge runs inside the same transaction as the render: it is verified
afterwards (the old content must still be a prefix, no requirement or
`[tool.*]` key may be dropped or changed) and a violation rolls the whole
adoption back.

`--no-merge` skips all of it (your files are then left byte-identical).

What it still does not do: reconcile a *conflicting* constraint or rewrite
`[tool.*]` sections. `notes/SPEC-adoption.md` section 12 keeps section-level
TOML reconciliation a non-goal — the merge above is the additive half that is
safe to automate.

## Example

```
$ task adopt DIR=/path/to/project CLI_ARGS="--dry-run --ref HEAD"
target: /path/to/project
mode:   adopt
ref:    HEAD  (requested explicitly)
skip:   .github/workflows/ci.yml renovate.json

dry run -- nothing written

  dry run: would render 156 new file(s)
  created [dependency-groups] to hold the dev dependencies

$ task adopt DIR=/path/to/project CLI_ARGS="--ref HEAD"
adopted: 46 file(s) added, 5 existing file(s) untouched

  created [dependency-groups] to hold the dev dependencies
  not merged (build/environment config; wire by hand if you want it): tool.setuptools_scm
  the dist/release/pypi and docs jobs are not copied: they publish artifacts, releases or
  GitHub Pages, and a second publisher is the one thing worse than none
  runs alongside your own ci.yml; delete whichever you do not want (copier-ci.yml)

next
  git diff     # review; the adoption only added files
  git status   # untracked additions: CI, hygiene, AGENTS.md, ...
```

A refused or failed run:

```
$ task adopt DIR=/path/to/project            # another template owns it
another copier template owns this project (https://github.com/other/template.git);
pass takeover=True to replace its record                       # exit 3

$ ... --skip nothing-actually-collides        # an uncovered collision
FAILED: InteractiveSessionError: Interactive session required: Consider using `--overwrite`
  removed what the run created: 40 file(s)
                                                               # exit 1, project unchanged
```

## Options

| Option | Meaning |
| --- | --- |
| `--dry-run` | Plan only; write nothing. |
| `--yes` | Apply without the confirmation prompt. |
| `--ask` | Confirm even when stdin is not a terminal. |
| `--ref REF` | Revision to expand (default: judged from the tags). `HEAD` = this working tree. |
| `--answers FILE` | Copier answers file — `tools/detect.py --answers` writes one for the target. |
| `--data k=v` | Extra answer, repeatable; effective YAML value (`k=true`, `k=[a, b]`). |
| `--skip PATH` | Path never to write over, repeatable. Default: the detected collisions. |
| `--takeover` | Adopt over a foreign template's answers file (otherwise refused). |
| `--no-merge` | Do not merge anything into the files you already have. |
| `--recover` | Undo an interrupted run from its journal; exits 0 when there is nothing to undo. Refused with `--dry-run`. |
| `--json` | Machine-readable result, including `created`, `unchanged`, `restored`, `removed`. |

Exit codes: `0` adopted (or a clean dry run, or a recovery that had nothing to
do), `1` failed and rolled back (a signal included), `2` invalid request
(already generated by this template, not a directory, an unusable journal),
`3` refused (foreign template without `--takeover`), `4` a previous run left
its journal behind — recover it first.

The same operation is available over MCP as `adopt_project`
([Use the template's own MCP server](mcp-tools.md)), where `dry_run`
defaults to `true` and a failed adoption raises rather than returning a
half-valid result.

## Related

- [Inspect a Target Before Applying the Template](detect.md) — the report the
  plan is built from.
- [Adopt the template into an existing repo](../tutorials/adopt-existing.md) —
  the user-facing walkthrough, including what copier does with each of your
  files.
