# How to run a batch of generation requests

`tools/batch.py` runs a list of copier requests and decides, itself, whether
each one succeeded. You write the requests as JSONL (one JSON object per
line); the runner renders each one with the real template, judges the
`expect` block, and exits nonzero if anything failed. Nothing needs to be
inspected by eye.

```shell
task batch                                   # runs batches/smoke.jsonl
task batch FILE=batches/my-batch.jsonl CLI_ARGS="--only '^library' --keep"
```

Exit codes: `0` every line passed, `1` a check failed, `2` the request list
itself is invalid (unknown key, duplicate id, malformed JSON).

## Why not just more pytest cases

The same request list is useful to three different callers: a human
debugging one combination, CI running the whole matrix, and a generator
that emits requests from the questionnaire (see
`notes/PLAN-improvements.md` W3, which turns Z3 witnesses into exactly this
format). Two properties pytest does not give you fall out of that: the
runner executes the *real* copier against the *working tree* (uncommitted
template edits are included, with copier's `DirtyLocalWarning`), and its
verdict is a machine-readable report (`--json`) rather than a test outcome.

## Request keys

| Key | Meaning |
| --- | --- |
| `id` | Required, unique. Also the default destination directory. |
| `note` | Free text, ignored by the runner. |
| `src` | Template path or git URL. Default: this repository. |
| `ref` | Git ref for the template. Default: `HEAD`. |
| `answers` | Copier data, inline. |
| `answers_file` | YAML answers file (relative to `--repo`), merged *under* `answers`. |
| `dest` | Destination under the work dir. Default: `id`. |
| `update` | Optional second phase: `ref`, `answers`, `answers_file`, `conflict` (`inline`/`rej`). |
| `commands` | Shell commands run in the destination: `run`, `cwd`, `timeout`, `exit`, `stdout_regex`, `stderr_regex`. |
| `expect` | Static checks, below. |

Unknown keys are rejected everywhere: a typo like `expec` fails the run with
exit 2 instead of silently checking nothing.

### `expect`

| Key | Meaning |
| --- | --- |
| `files` | Globs that must match at least one path. |
| `absent` | Globs that must match nothing. |
| `matches` | `[{path, regex}]` — the file text must match. |
| `unmatches` | `[{path, regex}]` — the file text must not match. |
| `toml` | `[{path, key, equals}]` — dotted-key lookup (integer segments index lists). |
| `agents_md` | `[{present: [registry-id], absent: [registry-id]}]` — the generated AGENTS.md must carry/not carry the ethics appendix section; ids resolve to section titles through `_shared/ethics/REGISTRY.yml`. |

`expect` and `commands` are judged against the state *after* `update`, if
that phase is present.

## Example

```json
{"id":"script-recommended","answers_file":"batches/base.yml","answers":{"project_type":"script"},"expect":{"files":["smoke_example/__init__.py"],"absent":["src"],"toml":[{"path":"pyproject.toml","key":"project.name","equals":"smoke-example"}]}}
```

`batches/smoke.jsonl` is the shipped sample: ten lines covering the fast
paths (library / web_api / script / data-science combo / ros2 /
micropython / kaggle / bare / gitlab), including one `update` line
(`library-update-in-place`). Running it needs no network and takes a few
seconds.

## The update phase needs a clean template tree

`copier update` re-renders the old version to diff against, so it clones the
template and checks out the `_commit` recorded in `.copier-answers.yml`.
When the template working tree is dirty, copier commits that dirty state
into its clone and records *that* synthetic commit — which a later update
cannot check out of a fresh clone. The runner therefore fails an `update`
line before generating anything:

```
- update-precondition: clean template tree: uncommitted: TODO.md, tools/batch.py
  (an update cannot check out copier's synthetic dirty commit)
```

Commit (or stash) the template first. A copy-only request from a dirty tree
is fine, but note that its `.copier-answers.yml` records the same
unreachable synthetic commit, so that particular generated project cannot be
updated later.

- `--only REGEX` — run the lines whose `id` matches.
- `--keep` — keep the work dir (default: a temp dir, deleted on success).
- `--work DIR` — choose the work dir.
- `--repo DIR` — resolve `answers_file` relative to DIR instead of this repo.
- `--prepare` — install each rendered project's environment (implies `--keep`).
- `--shell` — after the run, open a shell in the last rendered project (implies `--keep`).
- `--jobs N` — run up to N requests concurrently (default 1: serial, in file order).
- `--fail-fast` — stop at the first failing line.
- `--json` — print the verdict as JSON on stdout (copier's own output goes
  to stderr, so the stream stays parseable).

`task batch` is deliberately not part of `task check`: a batch renders real
projects and the update phase needs a clean tree, both of which belong in a
dedicated CI job rather than the lint/type-check/test loop.
