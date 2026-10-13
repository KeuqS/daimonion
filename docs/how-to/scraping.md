# Polite web-fetching layer

The template can layer **polite web fetching** onto a `cli` project under
the [Good-future charter](../explanations/good-future.md): robots.txt first,
per-host rate limiting, on-disk caching, and a contactable User-Agent. The
charter's rules are enforced by the toolchain (ruff `banned-api`, pytest,
CI) — not left to discipline.

Answering **Yes** to `include_scraping` (asked for the `cli` base only)
generates a `CHARTER.md`, a fetcher module, and the **scrape mode** built
on it: a URL-list pipeline, a JSONL result store and a `scrape` subcommand.
Answering **No** to `use_recommended_scraping` reveals the engine question
(`scraping_engine`): `httpx` (recommended), `scrapy`, `memorious`,
`playwright`, or `all` (every engine at once).

## What gets generated

- `CHARTER.md` — the Good-future rules for this project (respect the
  source, respect the law, respect the commons). Read it before touching
  fetch code.
- `httpx` engine (recommended; also included for `memorious`,
  `playwright`, and `all` as the politeness core they reuse):
  `<pkg>/fetcher.py` — the preflight judge (`preflight()` /
  `PoliteFetcher`) plus offline `tests/test_scraping.py`. Adds the `httpx`
  runtime dependency. The judgement order is fixed in code:
  1. probe feed endpoints (`/feed`, `/rss.xml`, `/atom.xml`, ...) — when
     one answers, fetch the feed instead of the page;
  2. probe API hints (`/api`, `api.` subdomain, `openapi.json`) — when
     found, prefer the API over scraping;
  3. check robots.txt (deny → `RobotDeniedError` immediately, before any
     discovery — a denied page never detours through its feed), probe
     access (401/403 → `AccessDeniedError`: do not work around it), check
     the per-host session budget (`max_requests_per_host`, default 100 →
     over it is `BudgetExceededError`: stop, do not scale up). Probes count
     too, but discovery findings are cached per origin for
     `cache_ttl_seconds`, so the second page on a host costs one HEAD probe
     instead of re-probing 8 feed paths + API hints;
  4. rate-limit (1 req/s per host), serve from the on-disk cache when
     fresh, otherwise GET once and cache. `fetch()` is the same call with
     the HTTP status attached (`FetchedPage(url, status, text)`); `fetch_text()`
     returns just the body.
  The httpx politeness core also renders the scrape mode described below —
  `<pkg>/pipeline.py`, `<pkg>/storage.py`, `tests/test_pipeline.py` and the
  `scrape` CLI subcommand — so `memorious` and `playwright` (which reuse the
  core) carry it too; `scrapy` (the one httpx-free engine) does not.
- `scrapy` engine: `<pkg>/spider.py` — spider starter with `ROBOTSTXT_OBEY`
  + `AUTOTHROTTLE` enforced in `custom_settings`, plus
  `tests/test_scrapy_spider.py` (settings + offline parse). Adds `scrapy`.
- `memorious` engine: `<pkg>/crawler.py` — memorious crawler config
  (rate-limited cached HTTP sessions), plus
  `tests/test_memorious_crawler.py`. Adds `memorious4` — which is
  **AGPL-3.0**, so choosing this engine rewrites the whole project license
  to AGPL-3.0 automatically (see below).
- `playwright` engine: `<pkg>/browser_fetch.py` — headless-Chromium fetch
  for JS-rendered pages (robots precheck reused from the fetcher), plus
  `tests/test_browser_fetch.py` (config defaults only — no browser launch
  in CI). Adds `playwright` (`playwright install chromium` once to run it).
- ruff `banned-api`: direct HTTP calls (`requests.get`, `httpx.get`,
  `urllib.request.urlopen`, ...) are banned outside the fetcher, so every
  fetch stays polite. `.cache/fetcher/` is git-ignored.

## The scrape mode: URLs in, stored records out

The `httpx` engine renders more than the fetcher — it renders a usable
scraping *mode*, so a crawl is a command rather than a blank page:

- `<pkg>/pipeline.py` — `ScrapePipeline` takes an iterable of URLs, runs
  each through `PoliteFetcher` (the same robots / rate-limit / cache path
  `fetch_text()` uses — nothing re-implemented), and yields a
  `ScrapeResult(url, status, text, fetched_at)` per URL, appending each to
  the store as it goes. It is synchronous and needs nothing beyond `httpx`.
- `<pkg>/storage.py` — `ResultStore` appends those records as JSONL under
  `.cache/scraped/results.jsonl` (git-ignored with the rest of `.cache/`)
  and reads them back with `iter()`. No database: one JSON object per line
  is durable, greppable and re-runnable, and a torn trailing line is
  skipped rather than failing the read.
- the CLI: `python -m <pkg> scrape <url>...` (also `<repo_name> scrape ...`
  once installed) fetches every URL, appends one record per page, and
  prints a per-URL summary plus the store path. It exits non-zero when any
  page failed.

Failure policy, pinned by `tests/test_pipeline.py` (mocked fetcher, no
network):

- a page that robots.txt denies, a site that answers 401/403, or a
  transport error is **recorded** — status `0` / the real HTTP code plus
  the error text — and the next URL proceeds. A many-page crawl is not
  all-or-nothing, and the store shows what happened instead of hiding it.
- the one global stop is `BudgetExceededError`: an exhausted host budget
  stops the crawl and propagates, exactly as the charter demands — never
  quietly continue past a budget you set.

## Scaling up

The pipeline is deliberately single-process and single-host polite. Mass
crawls, distributed queues, proxy rotation and multi-day schedules are out
of scope on purpose: the charter's **ask-first** rule is the scaling path —
open an issue describing the crawl size and get review before raising
`max_requests_per_host` or parallelizing across hosts. `ResultStore` stays a
boring JSONL sink so the harvested data is yours to move (into a database,
a data-science pipeline, or a de-identification review) without the
template locking you into a storage engine.

## License consequences

- `memorious4` is AGPL-3.0: linking it forces the whole project to
  AGPL-3.0. The template hard-forces `license_effective` to AGPL-3.0 when
  the memorious engine is selected — do not change it back to MIT.
- `task license-check` (`pip-licenses --fail-on`) audits installed
  dependency licenses and fails on copyleft the project license
  cannot absorb. It runs standalone and from `type-check`; like
  `task audit` it needs network (PyPI metadata).

## What is never generated

CAPTCHA-solving helpers (2captcha-style solvers, token injectors) are
deliberately out of scope for every engine. If a site blocks bots, use its
API or ask permission — bypassing bot protection violates the site's terms
and likely the law.
