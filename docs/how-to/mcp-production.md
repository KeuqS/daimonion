# Running an MCP server in production

How to serve the [MCP scaffold](mcp.md)'s streamable-http transport past
local debugging: a compose service, the host allowlist, and the three
things the scaffold deliberately leaves to you (replicas, auth, process
management). For packaging the server itself (PyPI, `uvx`, registry),
see [Distributing an MCP Server](mcp-distribute.md).

There is no `mcp_transport` generation-time question: the transport is a
runtime flag on the console script (`--transport stdio`, the default an
MCP host launches, or `--transport streamable-http`; SSE was removed in
SDK v2). Everything below assumes you have answered **Yes** to
`include_mcp` and serve over streamable-http.

## The compose service

No compose file is generated for `cli` + MCP projects
(`compose.local.yml` ships only for `web_api` + `docker`, wiring the API
to Postgres). For streamable-http, add one — building the same
`runtime` target of the generated `Dockerfile`, with the entrypoint
overridden to the MCP console script. The vocabulary mirrors
`compose.local.yml` on purpose: read-only root filesystem, `/tmp` and
cache tmpfs, `.env` via `env_file`, and the same `/health` probe (the
generated `mcp_server.py` registers `GET /health` as an unauthenticated
custom route, and binds port 8000 by default — so the web_api image's
baked `HEALTHCHECK` keeps working unchanged under the new entrypoint).

Save this as `compose.mcp.yml` (`web_api` + MCP projects can instead
merge the `mcp` service into `compose.local.yml`, next to `api`);
replace `<repo>` / `<org>` with your names:

```yaml
name: <repo>_mcp

services:
  mcp:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    image: ghcr.io/<org>/<repo>:local
    entrypoint: ["mcp-server-<repo>"]
    command: ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
    # Least privilege: same shape as compose.local.yml's api service.
    read_only: true
    tmpfs:
      - /tmp
      - /home/appuser/.cache
    environment:
      PYTHONDONTWRITEBYTECODE: "1"
      XDG_CACHE_HOME: /home/appuser/.cache
      # Public hostname(s), comma-separated — never "*". The proxy in
      # front must forward the Host header (reverse proxies do).
      MCP_ALLOWED_HOSTS: "mcp.example.com"
    env_file:
      - path: .env
        required: false
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      start_period: 10s
      retries: 3
    restart: unless-stopped
```

```sh
docker compose -f compose.mcp.yml up --build
curl http://localhost:8000/health   # {"status": "ok"}
```

For a one-off container without compose, the equivalent is the
`mcp-serve` task (generated when `docker` is on) or the `docker run`
recipe in the Dockerfile comments (the generated project's own
run-container how-to shows the same command).

## The host allowlist

Binding to a non-local address (`0.0.0.0` inside any container) requires
`MCP_ALLOWED_HOSTS`: the SDK arms its DNS-rebinding protection only for
localhost binds, so the generated `main()` refuses to start without an
explicit allowlist rather than accept every `Host` header. In production:

- Set it to the **public hostname(s)** the server is reached at
  (`mcp.example.com`), not `*` and not the container default from local
  debugging. Port matching is exact unless the entry is `host:*`, which
  matches any port on that host — and there is no bare-hostname
  wildcard, so a lone `*` matches nothing at all.
- `MCP_ALLOWED_ORIGINS` stays optional, for browser-based clients only.
- `GET /health` intentionally bypasses the allowlist (like every SDK
  custom route): it is a liveness probe for the orchestrator and exposes
  no tools or data.

## What the scaffold does not do for you

Three production concerns are operator-owned by SDK design. The scaffold
gives you the seam; wiring it is deployment work, not generation work.

### Replicas need a shared request-state key

`MCPServer` defaults to `RequestStateSecurity.ephemeral()` — a key
generated at startup and held only by that process. Multi-round-trip
state minted by one worker is rejected by every other worker (and after
any restart). A single `server.run()` is one
[uvicorn](https://www.uvicorn.org/) process — the SDK does no process
management, there is no `--workers` flag — so the moment you run two
replicas, give them the same key:

```python
import os

from mcp.server import MCPServer
from mcp.server.request_state import RequestStateSecurity

server = MCPServer(
    "<repo>",
    request_state_security=RequestStateSecurity(keys=[os.environ["MCP_STATE_KEY"]]),
)
```

(`import` paths: `mcp.server.request_state.RequestStateSecurity`.)

- The secret must decode to **at least 32 bytes**; generate one with
  `python -c "import secrets; print(secrets.token_hex(32))"`, keep it in
  `.env` / your secrets manager, never in git.
- `keys` is a rotation ring: `keys[0]` seals, every key unseals. Rotate
  with zero downtime by deploying `keys=[new, old]`, then `keys=[new]`
  after one TTL.

### Replicas need a shared subscription bus (if you use them)

Subscriptions (`resources/subscribe`, `tools` list-change notifications)
fan out through a `SubscriptionBus` (`mcp.server.subscriptions`), and
the default is `InMemorySubscriptionBus` — listeners in this process
only. Events published on replica A never reach a listen stream open on
replica B. If your tools emit subscription events, implement the
`SubscriptionBus` protocol (`async publish`, sync `subscribe`) over an
external pub/sub backend (Redis, NATS, …) and pass it as
`MCPServer(..., subscriptions=...)`. If nothing you serve subscribes,
there is nothing to share — one replica's memory is enough.

### Auth and process supervision are yours

The SDK supports OAuth (`AuthSettings` plus a provider or token
verifier on the server object), but the scaffold wires **none** of it:
no login flow, no tokens, no users. Either implement the SDK's OAuth
surface or — the common case — terminate TLS and authenticate at a
reverse proxy in front of the compose service. Minimal Caddy pattern
(automatic TLS; prefer your real auth — `forward_auth` against your
identity provider — over the placeholder `basicauth` below, which most
MCP clients cannot complete):

```caddy
mcp.example.com {
        basicauth {
                <user> <hash>
        }
        reverse_proxy mcp:8000
}
```

When the proxy is on the same compose network, drop the `ports:` mapping
on the `mcp` service — only the proxy listens publicly. Supervision is
the platform's job too: `restart: unless-stopped` in compose (as above),
or replicas under Swarm / Kubernetes / your PaaS. Stateful replicas need
session affinity at the proxy; alternatively the SDK's streamable HTTP
app exposes a `stateless_http` option (no sessions, no SSE streams) —
the scaffold leaves it off, evaluate it against what your clients need.

## How this relates to the web_api Docker layer

The compose shape above reuses `compose.local.yml`'s vocabulary
(`runtime` target, read-only filesystem, tmpfs, `env_file`, `/health`
probe, `LOG_FORMAT=json` logging through the same `logging_setup.py`),
so one mental model covers both. Where they diverge:

| | web_api (`compose.local.yml`) | MCP streamable-http (here) |
| --- | --- | --- |
| Entrypoint | Fixed: `uvicorn app.main:app` | Overridden: `mcp-server-<repo>` with `--transport streamable-http` |
| Companion services | Postgres 17 (+ Alembic migrations) | None for the example surface — add a database only if your tools need one |
| stdio projects | n/a | No packaging at all: the host launches `uv run` / `uvx mcp-server-<repo>` as a child process (see [mcp.md](mcp.md)) |

## Checklist

- [ ] Serving streamable-http from the `runtime` image with the
  `mcp-server-<repo>` entrypoint (`compose.mcp.yml` or the `mcp-serve` task)
- [ ] `MCP_ALLOWED_HOSTS` set to the public hostname(s) — never `*`
- [ ] More than one replica → shared `RequestStateSecurity` key (≥32
  bytes, in `.env` / secrets manager) and, if you emit subscription
  events, an external `SubscriptionBus`
- [ ] TLS + real authentication at the proxy (or SDK OAuth wired
  deliberately); `ports:` closed except through the proxy
- [ ] `/health` scraped by the orchestrator; `LOG_FORMAT=json` where logs
  are aggregated

## Related

- [MCP Server Scaffolding](mcp.md) — the generated server, transports,
  and the developer/operator security notes this recipe builds on.
- [Distributing an MCP Server](mcp-distribute.md) — packaging and
  `uvx` distribution (the stdio path needs no containers at all).
- [Web API Service Scaffolding](web-api.md) — the compose vocabulary
  this page reuses.
- [MCP Deploy & scale](https://py.sdk.modelcontextprotocol.io/run/deploy/) —
  official SDK docs; why process management and auth stay outside the
  scaffold.
