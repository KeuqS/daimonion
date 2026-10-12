# Use the template's own MCP server

`tools/mcp_server.py` exposes **this repository's** tooling over MCP, so an
agent editing the template calls `template_status`, `render_project`,
`render_diff`, `run_witness` and friends instead of shelling out and parsing
text. It is the maintenance-loop counterpart of
[the MCP server a generated project gets](mcp.md): that one is scaffolding for
your project, this one is how you drive the template itself.

Nothing to configure: the repository ships a project-scope `.mcp.json`, and an
MCP host that reads one (Claude Code, VS Code, Cursor, ...) picks the server
up as soon as you open the checkout.

## Run it

```shell
task mcp                                     # stdio -- what an MCP host launches
uv run --locked python tools/mcp_server.py   # the same command, unpacked
task mcp CLI_ARGS="--transport streamable-http"   # serve it on 127.0.0.1:8000
uv run mcp dev tools/mcp_server.py           # MCP Inspector (needs npx)
```

`.mcp.json` registers exactly that stdio command, which is also what `task mcp`
runs:

```json
{
  "mcpServers": {
    "daimonion": {
      "command": "uv",
      "args": ["run", "--locked", "python", "tools/mcp_server.py"],
      "env": {}
    }
  }
}
```

## Tools

Every tool states its cost and its return shape -- the docstring *is* the
description the model reads, and `tests/test_mcp_server.py` fails if a tool
stops saying what it costs and what comes back. Ask the cheap questions
first: `template_status` is ~50 ms, a render ~1.5 s, and the `slow` / `full`
witness tiers run into minutes.

| Tool | What it answers | Cost |
| --- | --- | --- |
| `template_status` | this checkout: question count, latest tag, commits behind it, dirty or not | git + questionnaire (~50 ms) |
| `list_questions` | the questionnaire in ask order, with defaults, help and choices | filesystem |
| `list_presets` | the ready-made answer files under `presets/` -- each name (what `--preset` accepts) with the answer mapping it supplies | filesystem |
| `explain_choice` | why a preset pins what it pins / what changes when an answer deviates, from the questionnaire's own words | filesystem |
| `suggest_config` | preset candidates for requirement words, each with reasons and pinned answers (the assistant's first step) | filesystem |
| `validate_answers` | whether a proposed answer set is askable and copier-valid, with {question, reason} rejections | questionnaire + copier's own pass, no render |
| `template_fingerprint` | sha256 of the render inputs: what a render is a function of | hashes ~0.8 MB (~5 ms) |
| `inspect_project` | what a target already has, which mode fits it, which files would be overwritten | filesystem |
| `render_project` | render a set of answers, and report the files it produced (`{path, sha256}` per file; `diff_against` a previous render for a manifest diff) | one render; `prepare=True` adds an install (network on a cold cache) |
| `render_diff` | two answer sets rendered and compared file by file | two renders, no install |
| `lint_render` | render, then `ruff format --check` + `ruff check` under the generated config | one render + two ruff runs, no venv |
| `run_batch` | a batch file's verdict (`tools/batch.py` semantics, structured) | one render per line; `prepare=True` adds installs |
| `run_witness` | a witness tier's verdict, one entry per executed test | `fast` a few seconds (272 renders, no venv), `slow` ~2 min, `full` adds venvs and network (tens of minutes) |
| `run_tests` | the same verdict shape for the suite's own tiers: `fast` / `heavy` / `slow` / `meta` / `all` | the tier you name; the marker expression comes from the cost ledger |
| `check_ethics` | which ethics/regional rules (`_shared/ethics/REGISTRY.yml`) the given text trips: each match carries the section's full markdown, its lifecycle (draft rules warn but ship nowhere) and its enforcement — the `license-drift` rule's L2 is the generated `license-check` gate | filesystem |

Two calls cover most of the loop:

- `render_diff(answers_a, answers_b)` replaces "render both, diff two trees by
  hand" -- `identical`, `file_count`, `identical_count`, `only_in_a` /
  `only_in_b`, and one entry per changed file with its sizes, its two sha256
  digests and a unified diff.
- `run_witness("fast", only="ros2 and use_recommended_license")` returns
  `run_batch`-shaped verdicts (`id`, `ok`, `checks`), so a failing leaf is read
  without interpreting pytest output. `only` is pytest's `-k` expression, which
  cannot contain `=`; select leaves by the words in their id (`ros2`,
  `use_recommended_license`).

`render_diff` compares `.copier-answers.yml` with copier's `_commit` stamp
normalized and reports the two stamps in `answers_commit`: for a *dirty*
template copier stamps a synthetic commit it creates per render, so the raw
file differs between two renders of identical answers, and that difference says
nothing about the answers. Every other byte is compared as it is.

## Resources

| Resource | Payload |
| --- | --- |
| `template://questionnaire` | the full questionnaire as JSON, internal variables included |
| `template://witnesses` | each witness leaf with its recorded tier and result, plus the ledger's coverage counters -- sorted and declaration-ordered, so it diffs between runs |
| `template://support` | the declared support contract (`support.yml`): what CI promises to execute per combination and per leaf class, each entry with the measured `why` |
| `template://ethics` | the ethics/regional rule registry: one row per section with its lifecycle, enforcement, audience and documented presence trigger — the active rows are what the generated AGENTS.md ethics appendix ships |

## The HTTP transport and its allowlist

Binding to localhost is safe by default: the SDK arms its DNS-rebinding
protection for a local bind, and `main()` adds `MCP_ALLOWED_HOSTS` on top when
you set it. Binding anywhere else (`--host 0.0.0.0`, e.g. inside a container)
**requires** `MCP_ALLOWED_HOSTS`, because the SDK's protection is only
automatic for localhost; the server refuses to start rather than accept every
`Host` header.

- `MCP_ALLOWED_HOSTS` -- comma-separated; a `host:*` entry matches any port.
- `MCP_ALLOWED_ORIGINS` -- optional, comma-separated, checked after the Host.
- `GET /health` -- an unauthenticated liveness probe for an orchestrator. Like
  every SDK custom route it is a plain Starlette route, so it **bypasses** the
  allowlist and returns `{"status": "ok"}` to anyone; it exposes no data.

That scope is not a claim, it is tested: `tests/test_mcp_server.py` starts the
real server on `127.0.0.1` (no venv, no network) and pins a foreign `Host` at
421 on `/mcp` with `/health` still 200, a foreign `Origin` at 403, and an
allowed `Host` completing an `initialize` handshake at 200.

## Relationship to the generated scaffold's server

Two MCP servers exist in this repository, and they stay separate on purpose:

| | `tools/mcp_server.py` (this one) | `_shared/mcp_server.py.jinja` |
| --- | --- | --- |
| Serves | the template's maintenance loop | the generated project, after `include_mcp` |
| Audience | an agent editing the template | the project's own users and their hosts |
| Tools | render, inspect, adopt, batch, witnesses | a worked example: typed tools, a `ToolError`, resources, a prompt |
| Shipped as | a repo script (`task mcp`) | `<pkg>/mcp_server.py` + a console script, `uvx`-runnable once published |

They share no code and import nothing from each other: a generated project is
copied out, released and installed on its own, so it must never depend on this
repository -- and this repository must not grow a dependency on one project
type's shape. The only idea that appears in both is the `MCP_ALLOWED_HOSTS`
rule plus `/health`, about thirty lines of SDK glue re-derived from the SDK API
in each; keeping the second copy is what lets either side change its transport
settings without a release coupling. Their dependency handling differs too,
deliberately: the generated scaffold's deptry config ignores the starlette
import its `custom_route` needs (`DEP001=starlette`, plus `DEP003`), while this
repository declares `starlette` in its dev group and imports it directly.

Fix a generated project's server in `_shared/mcp_server.py.jinja` (and
[the MCP how-to](mcp.md) describes what it ships); add a maintenance tool to
`tools/mcp_server.py` and the table above.

## Related

- [Serve an MCP Server from a Generated Project](mcp.md) -- the scaffold, its
  security notes for developers and for users/operators.
- [Check a Change Without the Full Test Suite](test-loop.md) -- the same
  capabilities from the shell (`task batch`, `pytest -m`), and the tier model
  `run_witness` follows.
- [Verification Architecture](../explanations/verification.md) -- what the
  `fast`, `full` and `slow` tiers observe, and what the 272 leaves are.
