# Initial dependencies

What `pyproject.toml` a generated project starts with, per `project_type`
(and per opt-in layer). The questionnaire offers one recommended set per area
— "recommended + No for custom" — never a catalogue, so this page lists the
fixed sets rather than choices.

!!! tip "These sets are editable after generation"
    The runtime list is recorded in `.copier-answers.yml` as the
    `dependencies` answer. Edit that list and re-render rather than
    hand-editing `pyproject.toml` (which the next `copier update` would
    reconcile against anyway): see
    [the answers file](answers-file.md#structured-answers).

All types share the same dev toolchain at `strictness` recommended/full:
basedpyright + pyrefly (or ty) + ruff (`ALL`) + vulture + deptry + typos +
pytest-cov, driven by `task type-check`, plus an on-demand `task audit`
(`pip-audit`, needs network). `none`/`basic` shrink
this to pytest + ruff (minimal/basic rules) with no type checking.

## Runtime dependencies (`[project] dependencies`)

| Type | Runtime deps |
|---|---|
| `library` / `cli` / `script` | one logging library (`structlog` default; `loguru` / `picologging` / stdlib swap) |
| `web_api` | logging library + `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `alembic`, `asyncpg`, `pydantic-settings`, `asgi-correlation-id` (+ `prometheus-client` / `slowapi` unless opted out) |
| `data_science` | logging library + `duckdb`, `pyarrow`, `polars>=0.20.15` |
| `kaggle` (`online_judge` + `oj_kind=kaggle`) | `structlog` + `hydra-core`, `lightgbm`, `omegaconf`, `optuna`, `pandas`, `pydantic`, `pydantic-settings`, `pyyaml`, `rich`, `torch`, `torchvision`, `typer`, `xgboost` + `duckdb`, `pyarrow`, `polars>=0.20.15` |
| code-submission judges (`atcoder` / `leetcode` / `yukicoder` / `aoj`) | none (stdlib only) |
| `micropython` | none (firmware is deployed with mpremote, not pip) |
| `ros2` | logging library (ROS deps live in `package.xml`, not pip) |

Opt-in additions (same idea as the MCP layer — added to the base, never a
new type):

| Option | Adds |
|---|---|
| `include_ctf` (`library` / `cli` base) | `ctf` extra: `pwntools`, `z3-solver` |
| `include_bot` (`cli` / `web_api` base) | `discord.py>=2,<3` (the recommended platform, `bot_platform=discord`), `slack-bolt>=1.21,<2` (`bot_platform=slack`) or `line-bot-sdk>=3,<4` + `fastapi` + `uvicorn[standard]` (`bot_platform=line`, which serves LINE's webhook itself instead of dialling out) + `anyio` and, for line, `httpx` (dev, the in-process tests); entry point `bot-discord-<name>` / `bot-slack-<name>` / `bot-line-<name>` |
| `include_scraping` (`cli` base) | `httpx` (recommended engine), `scrapy` / `memorious4` (AGPL-3.0!) / `playwright` per `scraping_engine`, or all four with `all` |
| `license_check` (on by default) | dev: `pip-licenses` (runs `task license-check` in `type-check`) |
| `include_sentry` | `sentry-sdk` (initialised from `SENTRY_DSN`) |
| `cloud_provider=aws` / `gcp` / `azure` | `boto3`+`botocore` / `google-cloud-storage` / `azure-identity` |
| `docs_type=sphinx` | `requests` (runtime; used by `docs/conf.py` for the version switcher) |
| agent scaffold (`use_recommended_agent=No`, `library`/`cli`) | `pydantic-ai`, `pydantic-settings` |
| `sphinx` docs | dev: `pydata-sphinx-theme`, `myst-parser`, `sphinx-autobuild`, `sphinx-copybutton`, `sphinx-design` |

## Generated size (`tools/gen_docs.py --write`)

How big each rendered project is (files, text lines, runtime deps), measured
from real renders. A template change that grows or shrinks a family must
re-measure `tests/matrix/sizes.json` and rewrite this table; `--check` fails
in between.

<!-- BEGIN GENERATED: generated-size (tools/gen_docs.py --write) -->
| Row | Files | Lines | Runtime deps |
|---|---|---|---|
| `preset:bare` | 35 | 2454 | 1 |
| `preset:bot` | 55 | 3337 | 2 |
| `preset:cli` | 52 | 3076 | 1 |
| `preset:data-science` | 87 | 5120 | 4 |
| `preset:library` | 52 | 2907 | 1 |
| `preset:mcp-server` | 56 | 3479 | 2 |
| `preset:micropython` | 56 | 3228 | 0 |
| `preset:online-judge-atcoder` | 47 | 2840 | 0 |
| `preset:online-judge-codeforces` | 47 | 2834 | 0 |
| `preset:online-judge-kattis` | 47 | 2835 | 0 |
| `preset:ros2` | 51 | 2217 | 1 |
| `preset:web-api` | 66 | 3649 | 10 |
| `project_type=script` | 52 | 2822 | 1 |
| `row:oj_ctf` | 52 | 2749 | 1 |
| `row:oj_kaggle` | 68 | 3275 | 17 |
<!-- END GENERATED: generated-size -->

## Dev / experiment groups

- `web_api` / `include_mcp` dev add `anyio` (in-process client test); the
  discord bot layer adds it the same way (the fake-interaction test — the
  slack listener is driven synchronously, so it needs none), and so does the
  line bot, which additionally adds `httpx` for the transport its generated
  test drives `POST /callback` over (`httpx.ASGITransport`, the same reason
  the web_api tests use it: starlette's TestClient is not warning-free under
  the generated `filterwarnings = error`).
- `include_bot` (`cli` / `web_api` base) adds one platform runtime floor —
  `discord.py>=2,<3` by default, `slack-bolt>=1.21,<2` with
  `use_recommended_bot=No` + `bot_platform=slack`, `line-bot-sdk>=3,<4` (plus
  the `fastapi` / `uvicorn[standard]` its webhook server runs on, which a
  `web_api` base already declares) with `bot_platform=line` — and the matching
  `bot-discord-<name>` / `bot-slack-<name>` / `bot-line-<name>` entry point.
  Every floor is checked against PyPI by `tools/check_upstream.py` ("PyPI
  floor [bot] discord.py", "PyPI floor [bot] slack-bolt", "PyPI floor [bot]
  line-bot-sdk"); `fastapi` / `uvicorn` are pinned by its "PyPI floor
  [web_api]" rows, which read the same declarations.
- `data_science` / `kaggle` dev add `ipykernel`, `nbclient`, `nbstripout`,
  `pandas`, `tomli`, `quartodoc`.
- `include_ctf` adds a `ctf` extra (`pwntools`, `z3-solver`) — installed with
  `uv sync --extra ctf`.
- `data_science` / `kaggle` get an `experiment` extra (marimo, matplotlib,
  plotly, seaborn, wandb, openai, pendulum, httpx) — installed with
## Generated renovate rules

Generated `renovate.json` pins the template-owned surface so updates flow
through `copier update`, not renovate PRs. `packageRules` are split per
category (one rule per concern, each with its own description):

- `pyenv`: disabled (Python version is template-managed).
- Core CI (`github-actions`): checkout, toolchain setup (setup-uv,
  setup-pixi, install-poetry), `upload/download-artifact`, `setup-task`,
  `setup-just`, `zizmor-action`.
- Release (`github-actions`): `action-gh-release`, `git-cliff-action`,
  `codecov-action`.
- Container (`github-actions`, `docker=true` only): the 4 `docker/*` actions.
- PyPI (`github-actions`, `pypi=true` only): `gh-action-pypi-publish`.
- Docs (`github-actions`, docs generated): `actions-gh-pages`.
- Scorecard (`github-actions`, `scorecard=true` only): `scorecard-action` +
  `codeql-action`.
- FAIR (`github-actions`, `fair=true` only): `howfairis-github-action`.
- `dockerfile`: `ubuntu` and `ghcr.io/kasi-x/ubuntu-devcontainer` base
  images disabled (template-managed).

A test (`test_renovate_actions_match_what_is_shipped`) asserts the disabled
github-actions across all category rules exactly equal the actions used in
the workflows.

## Config parity with this repo

The generated `[tool.ruff]` / `[tool.basedpyright]` / `[tool.pytest]`
sections intentionally differ from this repo's own `pyproject.toml`:
different lint targets (generated `pkg_dir` + `tests` vs this repo's
`tests` + `tools`) and different jobs (generated
projects ship a library; this repo ships a template). Shared choices stay
in sync: ruff `ALL` + preview rules, line-length 120, single-line isort,
`pyproject-fmt` keep-full-version, typos 3-letter ignore. If you change a
shared choice, change it in both places.
