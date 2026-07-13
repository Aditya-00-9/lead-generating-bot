"""OpenAI Responses API + web_search_preview for real-time lead discovery."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlparse

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.collectors.base import BaseCollector
from app.collectors.mention_mapper import mention_from_extracted
from app.collectors.url_page_extractor import UrlPageExtractor
from app.config.settings import Settings
from app.models.schemas import ExtractedWebMention, ExtractedWebMentionsBatch, NormalizedMention
from app.prompts.collection_signals import (
    build_search_queries,
    format_preferred_sources,
    format_seen_urls_block,
    is_weak_listing_url,
    select_urls_for_deep_extract,
)
from app.prompts.openai_collection import WEB_RESEARCH_SYSTEM

logger = structlog.get_logger(__name__)


def _sanitize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    return u.split()[0]


def _url_key(url: str) -> str:
    parsed = urlparse(_sanitize_url(url))
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}".lower()


def merge_extracted_batches(batches: list[ExtractedWebMentionsBatch]) -> ExtractedWebMentionsBatch:
    """Dedupe by URL; keep the item with the highest relevance_score."""
    by_url: dict[str, ExtractedWebMention] = {}
    for batch in batches:
        for item in batch.items:
            key = _url_key(item.source_url)
            if not key or not key.startswith("http"):
                continue
            prev = by_url.get(key)
            if prev is None or item.relevance_score > prev.relevance_score:
                by_url[key] = item
    merged = sorted(by_url.values(), key=lambda x: x.relevance_score, reverse=True)
    return ExtractedWebMentionsBatch(items=merged)


class OpenAIWebResearchCollector(BaseCollector):
    """Uses OpenAI built-in web search to discover candidate URLs, then normalizes to mentions."""

    name = "openai_web_research"
    platform = "web"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        timeout = max(settings.openai_timeout_seconds, settings.openai_collection_timeout_seconds)
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=timeout)
        self.model = (settings.openai_responses_model or settings.openai_model).strip()
        self._search_sem = asyncio.Semaphore(max(1, settings.openai_web_research_search_concurrency))
        self._deep_extract_sem = asyncio.Semaphore(max(1, settings.openai_web_research_deep_extract_concurrency))
        self._page_extractor = UrlPageExtractor(settings)
        self.last_run_web_searches = 0
        self.last_run_deep_extracts = 0
        self._exclude_keys: set[str] = set()
        self._seen_urls_block = ""

    def reset_run_stats(self) -> None:
        self.last_run_web_searches = 0
        self.last_run_deep_extracts = 0
        self._page_extractor.reset_run_stats()

    def _set_exclude_urls(self, exclude_urls: list[str] | None) -> None:
        self._exclude_keys = {_url_key(u) for u in (exclude_urls or []) if _sanitize_url(u)}
        self._seen_urls_block = format_seen_urls_block(
            list(exclude_urls or []),
            max_urls=min(80, max(20, self.settings.openai_web_research_seen_url_limit // 2)),
        )

    def _to_mentions(self, batch: ExtractedWebMentionsBatch) -> list[NormalizedMention]:
        out: list[NormalizedMention] = []
        for it in batch.items:
            if it.relevance_score < self.settings.openai_collection_min_relevance:
                continue
            url = _sanitize_url(it.source_url)
            if is_weak_listing_url(url):
                continue
            if self._exclude_keys and _url_key(url) in self._exclude_keys:
                continue
            mention = mention_from_extracted(it, source="OpenAI Web Research")
            if mention:
                out.append(mention)
        return out

    def _max_tool_calls_for_run(self, *, multi_query: bool) -> int:
        if multi_query:
            return max(1, self.settings.openai_web_research_max_tool_calls_per_search)
        return max(1, self.settings.openai_web_research_max_tool_calls)

    @retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(2), reraise=True)
    async def _run_research(
        self,
        *,
        user_input: str,
        item_limit: int,
        max_tool_calls: int,
    ) -> ExtractedWebMentionsBatch:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "instructions": WEB_RESEARCH_SYSTEM,
            "input": user_input,
            "tools": [{"type": "web_search_preview", "search_context_size": "high"}],
            "tool_choice": "auto",
            "max_tool_calls": max_tool_calls,
            "temperature": 0.2,
            "truncation": "auto",
        }
        resp = await self.client.responses.create(**kwargs)
        raw = (resp.output_text or "").strip()
        if not raw:
            return ExtractedWebMentionsBatch(items=[])
        payload = json.loads(raw)
        batch = ExtractedWebMentionsBatch.model_validate(payload)
        return ExtractedWebMentionsBatch(items=batch.items[:item_limit])

    async def _run_single_focused_search(self, query: str, item_limit: int, max_tool_calls: int) -> ExtractedWebMentionsBatch:
        preferred = format_preferred_sources()
        seen = f"\n{self._seen_urls_block}\n" if self._seen_urls_block else "\n"
        user = (
            f"Search query (run web_search for this exact query):\n{query}\n\n"
            f"Prioritize results from: {preferred}\n"
            f"{seen}"
            f"Return up to {item_limit} strongest items as JSON per system rules. "
            f"Prefer individual permalinks, not product review listing pages."
        )
        async with self._search_sem:
            return await self._run_research(
                user_input=user,
                item_limit=item_limit,
                max_tool_calls=max_tool_calls,
            )

    async def _collect_multi_query(self, keywords: list[str], limit: int) -> ExtractedWebMentionsBatch:
        max_searches = max(1, self.settings.openai_web_research_max_searches)
        queries = build_search_queries(
            self.settings.competitors,
            keywords,
            max_searches=max_searches,
            competitors_per_run=self.settings.openai_web_research_competitors_per_run,
        )
        if not queries:
            return ExtractedWebMentionsBatch(items=[])

        pool_size = max(limit, self.settings.openai_web_research_discovery_pool_size)
        per_search = max(3, min(8, pool_size // max(1, len(queries))))
        tool_calls = self._max_tool_calls_for_run(multi_query=True)

        logger.info(
            "collector.openai_web_research.multi_query_start",
            search_count=len(queries),
            per_search_limit=per_search,
            pool_size=pool_size,
        )

        async def run_one(q: str) -> ExtractedWebMentionsBatch:
            try:
                return await self._run_single_focused_search(q, per_search, tool_calls)
            except Exception as exc:  # noqa: BLE001
                logger.warning("collector.openai_web_research.search_failed", query=q[:120], error=str(exc))
                return ExtractedWebMentionsBatch(items=[])

        batches = await asyncio.gather(*[run_one(q) for q in queries])
        self.last_run_web_searches += len(queries)
        merged = merge_extracted_batches(list(batches))
        logger.info(
            "collector.openai_web_research.multi_query_complete",
            searches=len(queries),
            raw_items=sum(len(b.items) for b in batches),
            unique_items=len(merged.items),
        )
        return ExtractedWebMentionsBatch(items=merged.items[:pool_size])

    async def _deep_extract_batch(
        self, batch: ExtractedWebMentionsBatch, keywords: list[str]
    ) -> ExtractedWebMentionsBatch:
        if not self.settings.openai_web_research_deep_extract or not batch.items:
            return batch
        limit = max(1, self.settings.openai_web_research_deep_extract_limit)
        urls = select_urls_for_deep_extract(batch.items, limit)

        logger.info("collector.openai_web_research.deep_extract_start", url_count=len(urls), pool=len(batch.items))

        async def extract_one(url: str) -> ExtractedWebMentionsBatch:
            async with self._deep_extract_sem:
                return await self._page_extractor.fetch_and_extract(url, keywords, per_url_limit=3)

        extracted = await asyncio.gather(*[extract_one(u) for u in urls])
        self.last_run_deep_extracts += len(urls)
        merged = merge_extracted_batches([batch, *extracted])
        logger.info(
            "collector.openai_web_research.deep_extract_complete",
            fetched=len(urls),
            deep_items=sum(len(b.items) for b in extracted),
            unique_items=len(merged.items),
        )
        return ExtractedWebMentionsBatch(items=merged.items)

    async def _collect_single_shot(self, keywords: list[str], limit: int) -> ExtractedWebMentionsBatch:
        kw_block = "\n".join(f"- {k}" for k in keywords[:40])
        comp_block = "\n".join(f"- {c}" for c in self.settings.competitors[:30])
        preferred = format_preferred_sources()
        seen = f"\n{self._seen_urls_block}\n" if self._seen_urls_block else "\n"
        user = (
            f"Monitoring keywords (find public discussions matching these):\n{kw_block}\n\n"
            f"Competitors / brands of interest:\n{comp_block}\n\n"
            f"Prioritize results from: {preferred}\n"
            f"{seen}"
            f"Run at least 10 separate web_search calls using varied query patterns "
            f"(site:reddit.com, Facebook groups, LinkedIn, alternatives, pricing complaints) "
            f"before returning results.\n"
            f"Prefer individual permalinks over G2/Capterra product review listing pages.\n"
            f"Target at least {min(40, limit * 2)} raw findings, then return up to {limit} strongest items as JSON."
        )
        return await self._run_research(
            user_input=user,
            item_limit=limit,
            max_tool_calls=self._max_tool_calls_for_run(multi_query=False),
        )

    async def collect(
        self,
        keywords: list[str],
        limit: int,
        exclude_urls: list[str] | None = None,
    ) -> list[NormalizedMention]:
        if not self.settings.openai_api_key.strip() or not keywords:
            return []
        try:
            self.reset_run_stats()
            self._set_exclude_urls(exclude_urls)
            if self.settings.openai_web_research_multi_query:
                batch = await self._collect_multi_query(keywords, limit)
            else:
                self.last_run_web_searches = max(1, self.settings.openai_web_research_max_tool_calls)
                batch = await self._collect_single_shot(keywords, limit)
            batch = await self._deep_extract_batch(batch, keywords)
        except Exception as exc:  # noqa: BLE001
            logger.error("collector.openai_web_research.failure", error=str(exc), model=self.model)
            return []
        mentions = self._to_mentions(batch)
        logger.info("collector.openai_web_research.complete", count=len(mentions))
        return mentions[:limit]
