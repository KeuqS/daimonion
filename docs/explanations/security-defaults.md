# Security-sensitive defaults inventory

The scaffold ships development-friendly defaults. They are safe on a
laptop and wrong in production. This page lists every security-sensitive
default by project type, the file that carries it, and what to change
before shipping. Generated projects carry the short version of the same
checklist in `AGENTS.md` ("Production security defaults").

Scope: security-sensitive *rendered defaults* (credentials, network
binds, open endpoints, permissive middleware). CI hardening (workflow
permissions, SHA pins, zizmor) lives in
[Security & compliance posture](security.md).

## How to use this page

- Before first deploy, walk the rows for your project type and confirm
  each "Change for production" cell.
- The scaffold fails closed where forgetting is likely (bot tokens, the
  MCP host allowlist): those rows say "refuses to start".
- Nothing here is a `SECRET_KEY`: the template ships no session-secret /
  JWT-secret default (there is no auth/session middleware to configure),
  so there is no signing key to rotate — the secrets below are the whole
  list.

## All project types

| Default | File | Change for production |
|---|---|---|
| `.env.example` carries only placeholders / commented values | `template/{% if needs_env_example %}.env.example{% endif %}.jinja` | Copy to `.env`, fill real values there; never commit `.env` |
| `.env`, `.envs/`, `*.pem` git-ignored | `template/{% if not existing_project or 'gitignore' not in adopt_protect %}.gitignore{% endif %}.jinja`, `template/{% if docker %}.dockerignore{% endif %}.jinja` | Keep ignoring them; inject prod secrets from the environment or a secret manager |
| `SENTRY_DSN` unset; `sentry_sdk.init(..., traces_sample_rate=1.0)` when `include_sentry` is on | `template/{% if needs_env_example %}.env.example{% endif %}.jinja`, `template/{% if pkg_scaffold %}{{ pkg_dir }}{% endif %}/__main__.py.jinja` | Set the DSN from the environment, lower the sample rate, scrub PII before enabling |
| LLM demo keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) commented out; the offline demo needs no key | `template/{% if needs_env_example %}.env.example{% endif %}.jinja` | Fill them only where the agent scaffold runs, via the environment |

## web_api

| Default | File | Change for production |
|---|---|---|
| `DATABASE_URL` points at local Postgres with `postgres:postgres` | `template/{% if web_api %}app{% endif %}/settings.py.jinja`, `template/{% if needs_env_example %}.env.example{% endif %}.jinja` | Rotate the credential; inject the real URL from the environment / secret manager |
| `POSTGRES_PASSWORD: postgres` in the local stack and CI service | `template/{% if web_api and docker %}compose.local.yml{% endif %}.jinja`, `template/{% if is_github %}.github{% endif %}/{% if ci_provider == 'github_actions' %}workflows{% endif %}/ci.yml.jinja` | Local/CI only — never reuse for production data |
| `alembic.ini` carries no URL; `env.py` reads app settings | `template/{% if web_api %}alembic{% endif %}/alembic.ini.jinja`, `template/{% if web_api %}alembic{% endif %}/env.py.jinja` | Rotating `DATABASE_URL` covers migrations too |
| Binds `0.0.0.0:8000` (settings default, Dockerfile `ENV`, compose `command`) | `template/{% if web_api %}app{% endif %}/settings.py.jinja`, `template/{% if docker or cicd_extras %}Dockerfile{% endif %}.jinja`, `template/{% if web_api and docker %}compose.local.yml{% endif %}.jinja` | Keep behind TLS termination + firewall; do not publish beyond the reverse proxy |
| CORS deny-by-default (`cors_origins: []`, no middleware) when `cors` is on | `template/{% if web_api %}app{% endif %}/settings.py.jinja`, `template/{% if web_api %}app{% endif %}/main.py.jinja` | Set `CORS_ORIGINS` to exact origins, never `*` (`allow_credentials` is on) |
| `GET /docs`, `GET /openapi.json` served by default | `template/{% if web_api %}app{% endif %}/main.py.jinja` (`FastAPI(...)`) | Restrict or disable in production |
| `GET /health` unauthenticated, DB-independent | `template/{% if web_api %}app{% endif %}/routers/health.py.jinja` | Keep it (orchestrator probe); keep sensitive data out of it |
| `GET /metrics` unauthenticated when `prometheus` is on | `template/{% if web_api %}app{% endif %}/{% if prometheus_effective %}metrics.py{% endif %}.jinja` | Scrape on a private interface or protect it |
| Demo list endpoint `5/minute` per IP (`slowapi`, `get_remote_address`); nothing when `rate_limit` is off | `template/{% if web_api %}app{% endif %}/routers/items.py.jinja`, `template/{% if web_api %}app{% endif %}/{% if rate_limit_effective %}rate_limit.py{% endif %}.jinja` | Set per-endpoint limits; behind a proxy, forward the client IP so the key is the caller |
| `uvicorn ... --reload` in the guide/README is the dev loop | `template/{% if agents_md_effective %}AGENTS.md{% endif %}.jinja`, `template/{% if not existing_project or 'readme' not in adopt_protect %}README.md{% endif %}.jinja` | Run production uvicorn without `--reload` (the Dockerfile/ compose `ENTRYPOINT` already does) |
| Runtime image runs as non-root `appuser`, read-only root FS in compose | `template/{% if docker or cicd_extras %}Dockerfile{% endif %}.jinja`, `template/{% if web_api and docker %}compose.local.yml{% endif %}.jinja` | Keep; add dropped capabilities / seccomp where your platform supports it |

## MCP (`include_mcp` on cli / web_api)

| Default | File | Change for production |
|---|---|---|
| stdio transport, localhost-only HTTP bind | `_shared/mcp_server.py.jinja` | Keep stdio unless you need HTTP |
| Non-local `--host` (e.g. `0.0.0.0` in Docker) requires `MCP_ALLOWED_HOSTS` — refuses to start without it | `_shared/mcp_server.py.jinja`, `template/{% if docker or cicd_extras %}Dockerfile{% endif %}.jinja` | Set the exact host allowlist + `MCP_ALLOWED_ORIGINS` |
| `GET /health` unauthenticated | `_shared/mcp_server.py.jinja` | Keep it (orchestrator probe); keep sensitive data out of it |

## Bots (`include_bot` on cli / web_api)

| Default | File | Change for production |
|---|---|---|
| `DISCORD_BOT_TOKEN` required — refuses to start without it | `_shared/bot-discord.py.jinja` | Inject from the environment; never bake into the image |
| `SLACK_BOT_TOKEN` (xoxb-) + `SLACK_APP_TOKEN` (xapp-) required — refuses to start without either | `_shared/bot-slack.py.jinja` | Same; Socket Mode is an outbound WebSocket (no listening port) |
| `LINE_CHANNEL_SECRET` + `LINE_CHANNEL_ACCESS_TOKEN` required — refuses to start without either; missing secret fails webhooks closed (HTTP 500, no reply) | `_shared/bot-line.py.jinja` | Same; webhook listens on all interfaces (`BOT_PORT`, default 8000) — expose over HTTPS only |
| `GMAIL_CREDENTIALS_JSON` / `GMAIL_TOKEN_JSON` required file paths — refuses to start without either | `_shared/bot-gmail.py.jinja` | Mount read-only (e.g. `/run/secrets/`); the token file IS the inbox; both git-ignored (`_shared/gitignore-gmail.jinja`) |

## Scraping (`include_scraping` on cli)

| Default | File | Change for production |
|---|---|---|
| `FETCHER_CONTACT` placeholder (`contact@example.com`) in the User-Agent | `_shared/fetcher-httpx.py.jinja`, `template/{% if needs_env_example %}.env.example{% endif %}.jinja` | Set a reachable address before any real crawl |
| 1 req/s per host floor, robots.txt, disk cache | `_shared/fetcher-httpx.py.jinja`, `template/{% if scraping_effective %}CHARTER.md{% endif %}.jinja` | Keep; confirm per-source (see `LEGAL.md`) |
| Cache / browser profiles git-ignored (`.cache/fetcher/`, `.cache/ms-playwright/`) | `_shared/gitignore-scraping.jinja` | Keep harvests out of git |

## MicroPython

| Default | File | Change for production |
|---|---|---|
| `boot.py` shows a `wlan.connect("SSID", "password")` placeholder | `template/{% if micropython_pkg %}firmware{% endif %}/boot.py.jinja` | Never commit real Wi-Fi credentials; provision per device |

## Online judge / CTF

| Default | File | Change for production |
|---|---|---|
| `.kattisrc` + downloaded `test/` cases git-ignored | `_shared/gitignore-oj.jinja` | Never commit submission tokens or harvested cases |
| `challenges/**/vuln`, `challenges/**/flag*` git-ignored | `_shared/gitignore-ctf.jinja` | Never commit targets or flags |
