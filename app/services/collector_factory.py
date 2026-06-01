"""Build the collector list from settings — skips sources that are not configured."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.collectors.base import BaseCollector
from app.collectors.google_alerts import GoogleAlertsCollector
from app.collectors.openai_url_scrape import OpenAIUrlScrapeCollector
from app.collectors.openai_web_research import OpenAIWebResearchCollector
from app.collectors.placeholders import PlaceholderCollector
from app.collectors.reddit import RedditCollector

if TYPE_CHECKING:
    from app.config.settings import Settings


def build_collectors(settings: "Settings") -> list[BaseCollector]:
    """OpenAI discovery → optional URL scrape → Reddit (if creds) → Google Alerts (if real feeds) → placeholders."""
    collectors: list[BaseCollector] = []

    if settings.openai_discovery_enabled:
        collectors.append(OpenAIWebResearchCollector(settings))

    if settings.openai_scraper_url_list:
        collectors.append(OpenAIUrlScrapeCollector(settings))

    if settings.reddit_configured:
        collectors.append(RedditCollector(settings))

    if settings.google_alerts_configured:
        collectors.append(GoogleAlertsCollector(settings))

    if settings.enable_placeholder_sources:
        collectors.extend(
            [
                PlaceholderCollector("G2", "review-site"),
                PlaceholderCollector("Capterra", "review-site"),
                PlaceholderCollector("App Store", "app-store"),
                PlaceholderCollector("Play Store", "play-store"),
            ]
        )

    if not collectors and settings.openai_api_key.strip() and settings.keyword_list:
        collectors.append(OpenAIWebResearchCollector(settings))

    return collectors
