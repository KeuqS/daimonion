"""Security-sensitive defaults: the AGENTS.md prod checklist and its inventory page.

Every row of docs/explanations/security-defaults.md must be backed by the
rendered code it names, and every generated AGENTS.md must carry the
"Production security defaults" checklist for exactly the layers the render
ships (web_api / mcp / bot platforms / sentry / scraping / micropython /
oj / ctf are all conditional; the secrets-hygiene bullet is not).
"""

from __future__ import annotations

import sys
from pathlib import Path

TOP = Path(__file__).absolute().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import answers as answers_mod  # noqa: E402

from render_cache import render_cache as render_cache  # noqa: PLC0414  # session fixture, made visible here
from support import copy_project  # noqa: E402

SECTION = "## Production security defaults"
DOCS_PAGE = TOP / "docs" / "explanations" / "security-defaults.md"

LINE_ANSWERS = {"use_recommended_bot": False, "bot_platform": "line"}
SLACK_ANSWERS = {"use_recommended_bot": False, "bot_platform": "slack"}
GMAIL_ANSWERS = {"use_recommended_bot": False, "bot_platform": "gmail"}


def _agents(project: Path) -> str:
    return (project / "AGENTS.md").read_text(encoding="utf-8")


def test_docs_inventory_page_exists(tmp_path: Path):
    """The inventory page exists (nav wiring is the integrator's job)."""
    assert DOCS_PAGE.is_file(), "docs/explanations/security-defaults.md must exist"


def test_every_render_ships_the_checklist(tmp_path: Path, render_cache):
    """library, web_api, cli and script renders all carry the section."""
    for kwargs in (
        {"project_type": "library"},
        {"project_type": "web_api"},
        {"project_type": "cli"},
        {"project_type": "script"},
    ):
        target = tmp_path / kwargs["project_type"]
        copy_project(target, **kwargs)
        assert SECTION in _agents(target), f"{kwargs}: AGENTS.md lost the checklist"


def test_web_api_checklist_names_prod_changes(tmp_path: Path, render_cache):
    """web_api AGENTS.md warns about the DB credential, CORS, bind and open routes."""
    copy_project(tmp_path, project_type="web_api")
    agents = _agents(tmp_path)
    for needle in (
        "postgres:postgres",
        "CORS_ORIGINS",
        "0.0.0.0:8000",
        "/docs",
        "/health",
        "/metrics",
        "5 requests/minute",
    ):
        assert needle in agents, f"web_api AGENTS.md must warn about {needle!r}"
    settings = (tmp_path / "app" / "settings.py").read_text()
    assert '"0.0.0.0"' in settings, "settings.py must back the 0.0.0.0 claim"
    assert "cors_origins: list[str] = []" in settings, "settings.py must back the deny-by-default claim"
    main = (tmp_path / "app" / "main.py").read_text()
    assert "if origins:" in main, "main.py must back the conditional-CORS claim"
    env = (tmp_path / ".env.example").read_text()
    assert "postgres:postgres" in env, ".env.example must back the DATABASE_URL claim"


def test_web_api_detail_options_off_mentions_missing_rate_limit(tmp_path: Path, render_cache):
    """cors/rate_limit/prometheus off: the checklist says what is absent."""
    copy_project(
        tmp_path,
        project_type="web_api",
        use_recommended_web_api=False,
        cors=False,
        rate_limit=False,
        prometheus=False,
    )
    agents = _agents(tmp_path)
    assert SECTION in agents
    assert "No rate limiting is configured" in agents
    assert "CORS_ORIGINS" not in agents
    assert "/metrics" not in agents


def test_mcp_checklist_requires_allowlist_for_public_binds(tmp_path: Path, render_cache):
    """cli + include_mcp warns about MCP_ALLOWED_HOSTS; a bare cli does not."""
    mcp = tmp_path / "mcp"
    copy_project(mcp, project_type="cli", include_mcp=True)
    agents = _agents(mcp)
    assert "MCP_ALLOWED_HOSTS" in agents
    assert "refuses to start" in agents
    body = (mcp / "src" / "daimonion_example" / "mcp_server.py").read_text()
    assert "MCP_ALLOWED_HOSTS" in body, "mcp_server.py must back the allowlist claim"

    bare = tmp_path / "bare"
    copy_project(bare, project_type="cli")
    assert "MCP_ALLOWED_HOSTS" not in _agents(bare)


def test_bot_checklists_name_each_platform_secret(tmp_path: Path, render_cache):
    """Each bot platform's AGENTS.md names its required secret(s)."""
    cases = [
        ({}, "DISCORD_BOT_TOKEN"),
        (SLACK_ANSWERS, "SLACK_APP_TOKEN"),
        (LINE_ANSWERS, "LINE_CHANNEL_SECRET"),
        (GMAIL_ANSWERS, "GMAIL_TOKEN_JSON"),
    ]
    for extra, needle in cases:
        target = tmp_path / needle.lower()
        copy_project(target, project_type="cli", include_bot=True, **extra)
        assert needle in _agents(target), f"bot AGENTS.md must warn about {needle!r}"


def test_line_checklist_warns_about_public_webhook(tmp_path: Path, render_cache):
    """LINE's webhook listens on all interfaces: the checklist says HTTPS-only."""
    copy_project(tmp_path, project_type="cli", include_bot=True, **LINE_ANSWERS)
    agents = _agents(tmp_path)
    assert "BOT_PORT" in agents
    assert "HTTPS" in agents
    body = (tmp_path / "src" / "daimonion_example" / "bot_line.py").read_text()
    assert 'host="0.0.0.0"' in body, "bot_line.py must back the all-interfaces claim"


def test_sentry_checklist_warns_about_sample_rate(tmp_path: Path, render_cache):
    """include_sentry warns about the DSN + 1.0 sample rate; bare renders do not."""
    sentry = tmp_path / "sentry"
    copy_project(sentry, project_type="cli", include_sentry=True)
    agents = _agents(sentry)
    assert "SENTRY_DSN" in agents
    assert "traces_sample_rate=1.0" in agents

    bare = tmp_path / "bare"
    copy_project(bare, project_type="cli")
    assert "SENTRY_DSN" not in _agents(bare)


def test_scraping_checklist_warns_about_contact_placeholder(tmp_path: Path, render_cache):
    """include_scraping warns about FETCHER_CONTACT; bare renders do not."""
    scraped = tmp_path / "scraped"
    copy_project(scraped, project_type="cli", include_scraping=True)
    assert "FETCHER_CONTACT" in _agents(scraped)
    body = (scraped / "src" / "daimonion_example" / "fetcher.py").read_text()
    assert "contact@example.com" in body, "fetcher.py must back the placeholder claim"

    bare = tmp_path / "bare"
    copy_project(bare, project_type="cli")
    assert "FETCHER_CONTACT" not in _agents(bare)


def test_checklist_does_not_touch_ethics_gates(tmp_path: Path, render_cache):
    """The checklist coexists with the ethics appendix on gated leaves."""
    copy_project(tmp_path, project_type="cli", include_scraping=True)
    agents = _agents(tmp_path)
    assert SECTION in agents
    assert "スクレイピングの適法性" in agents, "ethics appendix must be intact beside the checklist"


def test_inventory_rows_are_backed_by_template_sources():
    """Every 'File' cell of the inventory names a template/_shared source that exists."""
    import re

    text = DOCS_PAGE.read_text(encoding="utf-8")
    assert text.startswith("# Security-sensitive defaults inventory\n")
    cells = re.findall(r"`(template/[^`]+|_shared/[^`]+)`", text)
    assert len(cells) >= 15, f"inventory must name its sources; found {len(cells)}"
    missing = [cell for cell in cells if not (TOP / cell).exists()]
    assert not missing, f"inventory names sources that do not exist: {missing}"


def test_recommended_fast_path_keeps_checklist_and_appendix(tmp_path: Path, render_cache):
    """The recommended path (BASE answers) renders both checklist and appendix."""
    answers: dict[str, object] = {**answers_mod.BASE, "project_type": "web_api"}
    render_cache.render(tmp_path, answers)
    agents = _agents(tmp_path)
    assert SECTION in agents
    assert "## Field rules (ethics appendix)" in agents
