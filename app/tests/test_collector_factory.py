"""Collector wiring: skip unconfigured sources; minimal OpenAI + KEYWORDS path."""

from __future__ import annotations

from app.collectors.google_alerts import GoogleAlertsCollector
from app.collectors.openai_url_scrape import OpenAIUrlScrapeCollector
from app.collectors.openai_web_research import OpenAIWebResearchCollector
from app.collectors.placeholders import PlaceholderCollector
from app.collectors.reddit import RedditCollector
from app.config.settings import Settings
from app.services.collector_factory import build_collectors


def test_build_collectors_openai_only_when_no_other_sources() -> None:
    s = Settings(
        openai_api_key="sk-test",
        keywords="foo,bar",
        reddit_client_id="",
        reddit_client_secret="",
        google_alert_rss_urls="",
        enable_placeholder_sources=False,
        enable_openai_web_research=True,
    )
    cols = build_collectors(s)
    assert len(cols) == 1
    assert isinstance(cols[0], OpenAIWebResearchCollector)


def test_build_collectors_skips_placeholder_google_feeds() -> None:
    s = Settings(
        openai_api_key="sk-test",
        keywords="x",
        google_alert_rss_urls="https://www.google.com/alerts/feeds/0000/0000",
        enable_placeholder_sources=False,
    )
    kinds = [type(c) for c in build_collectors(s)]
    assert GoogleAlertsCollector not in kinds
    assert OpenAIWebResearchCollector in kinds


def test_build_collectors_adds_reddit_when_configured() -> None:
    s = Settings(
        openai_api_key="sk-test",
        keywords="x",
        reddit_client_id="id",
        reddit_client_secret="secret",
        enable_placeholder_sources=False,
    )
    kinds = [type(c) for c in build_collectors(s)]
    assert RedditCollector in kinds


def test_build_collectors_url_scrape_when_urls_set() -> None:
    s = Settings(
        openai_api_key="sk-test",
        keywords="x",
        openai_scraper_urls="https://example.com/page",
        enable_placeholder_sources=False,
    )
    kinds = [type(c) for c in build_collectors(s)]
    assert OpenAIUrlScrapeCollector in kinds


def test_build_collectors_placeholders_opt_in() -> None:
    s = Settings(
        openai_api_key="sk-test",
        keywords="x",
        enable_placeholder_sources=True,
    )
    cols = build_collectors(s)
    ph = [c for c in cols if isinstance(c, PlaceholderCollector)]
    assert len(ph) == 4
