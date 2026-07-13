"""Fetch configured URLs and use OpenAI to extract lead candidates (AI-assisted scraping)."""

from __future__ import annotations

import asyncio

import httpx
import structlog

from app.collectors.base import BaseCollector
from app.collectors.mention_mapper import mention_from_extracted
from app.collectors.url_page_extractor import UrlPageExtractor
from app.config.settings import Settings
from app.models.schemas import ExtractedWebMentionsBatch, NormalizedMention
from app.prompts.collection_signals import is_weak_listing_url
from urllib.parse import urlparse

logger = structlog.get_logger(__name__)


def _url_key(url: str) -> str:
    parsed = urlparse((url or "").strip().split()[0])
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}".lower()


class OpenAIUrlScrapeCollector(BaseCollector):
    name = "openai_url_scrape"
    platform = "web"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._extractor = UrlPageExtractor(settings)
        self._sem = asyncio.Semaphore(max(1, settings.openai_url_scrape_concurrency))
        self.last_run_web_searches = 0
        self.last_run_deep_extracts = 0

    def reset_run_stats(self) -> None:
        self.last_run_web_searches = 0
        self.last_run_deep_extracts = 0
        self._extractor.reset_run_stats()

    def _to_mentions(
        self,
        page_url: str,
        batch: ExtractedWebMentionsBatch,
        exclude_keys: set[str],
    ) -> list[NormalizedMention]:
        out: list[NormalizedMention] = []
        for it in batch.items:
            if it.relevance_score < self.settings.openai_collection_min_relevance:
                continue
            if not (it.source_url or "").strip().startswith("http"):
                it = it.model_copy(update={"source_url": page_url})
            url = (it.source_url or "").strip().split()[0]
            if is_weak_listing_url(url):
                continue
            if exclude_keys and _url_key(url) in exclude_keys:
                continue
            mention = mention_from_extracted(it, source="OpenAI Page Extract")
            if mention:
                out.append(mention)
        return out

    async def collect(
        self,
        keywords: list[str],
        limit: int,
        exclude_urls: list[str] | None = None,
    ) -> list[NormalizedMention]:
        urls = self.settings.openai_scraper_url_list
        if not urls or not self.settings.openai_api_key.strip() or not keywords:
            return []
        self.reset_run_stats()
        exclude_keys = {_url_key(u) for u in (exclude_urls or []) if (u or "").strip()}
        per = max(1, min(limit, max(3, limit // max(1, len(urls)))))
        headers = {"User-Agent": self.settings.reddit_user_agent or "kramaai-lead-monitor/1.0"}

        async def scrape_one(http: httpx.AsyncClient, url: str) -> list[NormalizedMention]:
            async with self._sem:
                batch = await self._extractor.fetch_and_extract(
                    url, keywords, per_url_limit=per, http=http
                )
                return self._to_mentions(url, batch, exclude_keys)

        all_mentions: list[NormalizedMention] = []
        async with httpx.AsyncClient(timeout=45.0, headers=headers) as http:
            results = await asyncio.gather(*[scrape_one(http, url) for url in urls])
            for part in results:
                all_mentions.extend(part)
        self.last_run_deep_extracts = self._extractor.last_extract_calls
        logger.info("collector.openai_url_scrape.complete", count=len(all_mentions))
        return all_mentions[:limit]
