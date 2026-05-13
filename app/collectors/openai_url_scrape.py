"""Fetch configured URLs and use OpenAI to extract lead candidates (AI-assisted scraping)."""

from __future__ import annotations

import json
import re
from html import unescape

import httpx
import structlog
from bs4 import BeautifulSoup
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.collectors.base import BaseCollector
from app.config.settings import Settings
from app.models.schemas import ExtractedWebMentionsBatch, NormalizedMention
from app.prompts.openai_collection import URL_EXTRACT_SYSTEM

logger = structlog.get_logger(__name__)

_MAX_PAGE_CHARS = 100_000


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class OpenAIUrlScrapeCollector(BaseCollector):
    name = "openai_url_scrape"
    platform = "web"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        timeout = max(settings.openai_timeout_seconds, settings.openai_collection_timeout_seconds)
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=timeout)
        self.extract_model = (settings.openai_collection_model or settings.openai_model).strip()

    @retry(wait=wait_exponential(min=1, max=20), stop=stop_after_attempt(2), reraise=True)
    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> str:
        r = await client.get(url, follow_redirects=True)
        r.raise_for_status()
        return r.text

    @retry(wait=wait_exponential(min=1, max=20), stop=stop_after_attempt(2), reraise=True)
    async def _extract_from_text(self, page_url: str, page_text: str, keywords: list[str], per_url_limit: int) -> ExtractedWebMentionsBatch:
        kw_block = ", ".join(keywords[:30])
        comp_block = ", ".join(self.settings.competitors[:20])
        user = (
            f"Page URL: {page_url}\n"
            f"Monitoring keywords: {kw_block}\n"
            f"Competitors: {comp_block}\n"
            f"Return up to {per_url_limit} items.\n\n"
            f"Page text:\n{page_text[:_MAX_PAGE_CHARS]}"
        )
        resp = await self.client.chat.completions.create(
            model=self.extract_model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": URL_EXTRACT_SYSTEM},
                {"role": "user", "content": user},
            ],
        )
        raw = (resp.choices[0].message.content or "{}").strip()
        payload = json.loads(raw)
        return ExtractedWebMentionsBatch.model_validate(payload)

    def _to_mentions(self, page_url: str, batch: ExtractedWebMentionsBatch) -> list[NormalizedMention]:
        out: list[NormalizedMention] = []
        for it in batch.items:
            if it.relevance_score < self.settings.openai_collection_min_relevance:
                continue
            url = (it.source_url or "").strip().split()[0]
            if not (url.startswith("http://") or url.startswith("https://")):
                url = page_url
            excerpt = (it.excerpt or it.title or "").strip()[:8000]
            title = (it.title or excerpt[:200]).strip()
            out.append(
                NormalizedMention(
                    source="OpenAI Page Extract",
                    source_url=url,
                    author=None,
                    platform=self.platform,
                    title=title,
                    raw_text=excerpt,
                    cleaned_text=excerpt[:6000],
                )
            )
        return out

    async def collect(self, keywords: list[str], limit: int) -> list[NormalizedMention]:
        urls = self.settings.openai_scraper_url_list
        if not urls or not self.settings.openai_api_key.strip() or not keywords:
            return []
        per = max(1, min(limit, max(3, limit // max(1, len(urls)))))
        all_mentions: list[NormalizedMention] = []
        headers = {"User-Agent": self.settings.reddit_user_agent or "kramaai-lead-monitor/1.0"}
        async with httpx.AsyncClient(timeout=45.0, headers=headers) as http:
            for url in urls:
                if len(all_mentions) >= limit:
                    break
                try:
                    html = await self._fetch_page(http, url)
                    text = _html_to_text(html)
                    if len(text) < 80:
                        logger.info("collector.openai_url_scrape.skip_short", url=url, text_len=len(text))
                        continue
                    batch = await self._extract_from_text(url, text, keywords, per)
                    all_mentions.extend(self._to_mentions(url, batch))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("collector.openai_url_scrape.page_failed", url=url, error=str(exc))
                    continue
        logger.info("collector.openai_url_scrape.complete", count=len(all_mentions))
        return all_mentions[:limit]
