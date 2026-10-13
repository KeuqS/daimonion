# MCP server scaffolding

The template can scaffold an [MCP](https://modelcontextprotocol.io) (Model
Context Protocol) server onto a `cli` or `web_api` project. Answering **No**
to `use_recommended_integrations` and **Yes** to `include_mcp` adds the `mcp`
SDK (with its CLI), generates an `mcp_server.py` with typed example tools,
and ships an in-process client test.
An MCP server is a **long-running process** — it does not fit the
"print and exit" CLI model. See
[the layer model](../explanations/long-running.md) for why it is a module on
top of a normal `cli` / `web_api` project rather than its own project type.

This page has two audiences: **developers** building an MCP server (from the
scaffold or their own) and **users / operators** adding MCP servers to a
host. The security sections are split accordingly. Serving the HTTP
transport past local debugging — compose, replicas, auth — is
[Running an MCP Server in Production](mcp-production.md).

## What gets generated

- The `mcp[cli]>=2.0,<3` dependency (the SDK plus its `mcp` command).
- An `mcp_server.py` in your package exposing a module-level `server`
  object (`MCPServer`) with:
  - two **typed tools** — `add(a: int, b: int)` and `divide(...)`. The input
    schema comes from the type hints, no hand-written JSON Schema;
  - a **`ToolError` example** — `divide` by zero raises one, which the SDK
    turns into an `is_error=True` result whose message the calling model can
    read (any other exception is sanitised);
  - two **resources** — `project://about` (static) and `greeting://{name}`
    (template: URI parameters map to function arguments);
  - one **prompt** — `review_code` (a reusable message template the host
    surfaces as a slash command; the user picks it and fills in `code`).
  (The module lives in `app/mcp_server.py` when the web_api layer is present,
  otherwise in `<pkg>/mcp_server.py` — one body shared via `_shared/`, so the
  two locations never drift.)
- A **console script** `mcp-server-<name>` so an MCP host can launch the
  server, and users can run it with `uvx` once published.
- An in-process client test `tests/test_mcp_server.py` that calls the tools,
  resources and prompt through the SDK's `Client` — no subprocess, no port.
  Treat it as the worked example for calling this server from your own
  client code.

The MCP SDK v2 ships full type stubs, so `mcp_server.py` **is** covered by
the generated type checkers (no exclusions).

## Running it

`mcp_server.py` exposes a module-level `server` object and a `main()` that
starts it. Replace `<name>` with your generated `repo_name` and `<package>`
with your generated `package_name`:

```sh
# stdio transport (the default): how an MCP host launches the server
uv run mcp-server-<name>

# Streamable HTTP (serve it on a port)
uv run python -m <package>.mcp_server --transport streamable-http

# Debug with the MCP Inspector (requires npx on PATH)
uv run mcp dev src/<package>/mcp_server.py
```

SSE is superseded by Streamable HTTP in the protocol; the scaffold only
offers stdio and streamable-http.

## Registering it with an MCP host

The generated project ships a `.mcp.json` pointing at the stdio command
(`uv run mcp-server-<name>`), so VS Code / Cursor and other hosts pick the
server up with no manual registration. Beyond that:

- **Claude Code / Claude Desktop**: `claude mcp add <name> -- uv run
  mcp-server-<name>` (stdio), or the streamable-http URL after starting the
  server.
- **Published server**: after releasing to PyPI (the `pypi` option), users
  run `uvx mcp-server-<name>` — no install needed. Point `.mcp.json` (or the
  host config) at that command instead. The full recipe — replacing the
  example surface, the SDK pin policy, registry listing — is
  [Distributing an MCP Server](mcp-distribute.md).

## Consuming MCP servers (as a client)

Using an **existing** MCP server is out of scope for code generation: it is
either a host-configuration step (above) or a `uvx mcp-server-...` launch.
Writing Python code that *calls* an MCP server uses the same `mcp` dependency
and the same `Client` API that the generated test exercises — start from
`tests/test_mcp_server.py`.

## Security for server developers

An MCP server is a remote-control surface for an LLM: the model picks
arguments and your tools act on them. The scaffold keeps that surface small
on purpose, and the SDK adds a few guarantees — the rest is yours to hold.

- **Least privilege by default.** The generated tools (`add`, `divide`) touch
  nothing but their arguments. When you add real tools, give each one the
  narrowest possible scope: prefer read-only operations, validate and
  allowlist any path / URL / identifier the model hands you, and never let a
  tool accept a free-form shell command. A tool that can reach the network is
  an SSRF primitive — apply the same egress rules you would to any service.
- **Treat tool inputs as untrusted.** Arguments come from a model that may be
  following instructions found in files, emails or web pages it has read
  (indirect prompt injection). Validate arguments against your domain rules
  before acting, and make destructive operations explicit — raise `ToolError`
  for anything that looks out of bounds rather than guessing.
- **Error messages are part of the API.** `ToolError` messages reach the
  model verbatim; every *other* exception is sanitised to
  `Error executing tool <name>` and only logged with its traceback. Never put
  secrets or internal paths in a `ToolError` message.
- **Exposing it over HTTP is a deployment decision.** The scaffold's
  streamable-http mode binds to `127.0.0.1` for local debugging. Serving it
  to real clients is where MCP's own security settings kick in — see below.

### Serving over HTTP / in production

The scaffold makes safe-by-default choices for the HTTP transport:

- The generated `main()` binds to `127.0.0.1` unless you pass `--host` /
  `--port` (list them with `mcp-server-<name> --help`).
- Binding to a **non-local** address requires the `MCP_ALLOWED_HOSTS`
  environment variable (comma-separated host allowlist). The SDK only arms
  its DNS-rebinding protection while the server binds to localhost —
  binding anywhere else (e.g. `0.0.0.0` inside Docker) would otherwise
  accept *every* Host header. `mcp_server.py` refuses to start in that
  state instead of silently serving without protection. `MCP_ALLOWED_ORIGINS`
  is optional and passed through for browser clients.
- A `GET /health` route is registered for orchestrators. Like every custom
  route in the SDK it is unauthenticated and bypasses the host allowlist —
  it exists so a load balancer can probe the process before any MCP
  handshake; it exposes no tools or data. `.env.example` documents the
  variables.

Multi-worker deployments additionally need a shared `RequestStateSecurity`
key for multi-round-trip requests to survive reaching a different worker.
Both are documented in the SDK's
[Deploy & scale](https://py.sdk.modelcontextprotocol.io/run/deploy/) page —
there is no MCP-specific Docker recipe, because the SDK deliberately leaves
process management to you (run the ASGI app under your usual uvicorn /
platform tooling). Authentication in front of the server is likewise yours:
the SDK supports OAuth, and a reverse proxy can add any other scheme. For a
Dockerized `cli` project with the `docker` option enabled, the generated
Dockerfile `EXPOSE`s port 8000 and the README / run-container how-to show the
`docker run` command (also available as the `mcp-serve` task).

The generated project already follows the template's security baseline
(pinned CI actions, dependency auditing, `pip-audit`, no secrets in the
repo).

## Security for users and operators

Adding an MCP server to a host is **not** a no-op configuration step. A
stdio server runs as a child process on your machine with your user's
permissions — it is arbitrary code execution by another name — and a remote
(streamable-http) server receives your prompts' tool calls. Whoever you
connect to decides what your agent can see and do.

- **Only connect servers you trust.** Prefer servers from a source you can
  audit: the project's own repository, a publisher you recognise, a PyPI
  package you have checked. Treat a copy-pasted `uvx mcp-server-...` command
  from an unfamiliar blog post or registry entry the same way you would a
  `curl | sh` install script. Malicious and typosquatted MCP servers /
  agent skills are a documented, active threat (registry poisoning,
  credential-exfiltrating "skills", prompt-injected tool descriptions).
- **Read what the server can do before adding it.** The server's
  `tools/list` result *is* its permission manifest: connect once in the MCP
  Inspector or a scratch client and look at the tool names, descriptions and
  argument schemas. A "filesystem" or "shell" tool is a wide-open grant;
  a server whose tools are narrow and specific is a small one.
- **Know where its instructions come from.** Some servers fetch resources or
  load external content that can steer the model (indirect prompt
  injection). A server that reads web pages or emails is asking the model to
  act on untrusted text — keep it away from high-privilege tools.
- **Grant it the least it needs.** Configure per-server permissions in the
  host (folder access, allowed tools) when the host supports it. Never run an
  untrusted server inside a project that holds credentials, and prefer an
  isolated environment for servers you are evaluating.
- **For remote servers, check the transport.** A production streamable-http
  server should sit behind TLS with real authentication — not an open
  `http://` endpoint. If you self-host one, apply the deployment notes in the
  developer section above.

## Where the token / config comes from

Like every long-running executable in this template, `mcp_server.py` reads
configuration from the **environment** (`.env`, loaded by direnv / the
compose stack) rather than from committed files. The generated `.env.example`
documents the variables the project understands — add yours there, never
commit the real `.env`.

Logging inside the server goes through the generated `logging_setup.py`, so
the `LOG_FORMAT=json` / `structlog` / `loguru` / ... behaviour is the same as
in the CLI.
