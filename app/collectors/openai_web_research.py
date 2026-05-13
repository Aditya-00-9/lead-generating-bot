"""OpenAI Responses API + web_search_preview for real-time lead discovery."""

from __future__ import annotations

import json
from typing import Any

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.collectors.base import BaseCollector
from app.config.settings import Settings
from app.models.schemas import ExtractedWebMentionsBatch, NormalizedMention
from app.prompts.openai_collection import WEB_RESEARCH_SYSTEM

logger = structlog.get_logger(__name__)


def _sanitize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    return u.split()[0]


class OpenAIWebResearchCollector(BaseCollector):
    """Uses OpenAI built-in web search to discover candidate URLs, then normalizes to mentions."""

    name = "openai_web_research"
    platform = "web"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        timeout = max(settings.openai_timeout_seconds, settings.openai_collection_timeout_seconds)
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=timeout)
        self.model = (settings.openai_responses_model or settings.openai_model).strip()

    def _to_mentions(self, batch: ExtractedWebMentionsBatch) -> list[NormalizedMention]:
        out: list[NormalizedMention] = []
        for it in batch.items:
            if it.relevance_score < self.settings.openai_collection_min_relevance:
                continue
            url = _sanitize_url(it.source_url)
            if not (url.startswith("http://") or url.startswith("https://")):
                continue
            excerpt = (it.excerpt or it.title or "").strip()[:8000]
            title = (it.title or excerpt[:200]).strip()
            out.append(
                NormalizedMention(
                    source="OpenAI Web Research",
                    source_url=url,
                    author=None,
                    platform=self.platform,
                    title=title,
                    raw_text=excerpt,
                    cleaned_text=excerpt[:6000],
                )
            )
        return out

    @retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(2), reraise=True)
    async def _run_research(self, keywords: list[str], limit: int) -> ExtractedWebMentionsBatch:
        kw_block = "\n".join(f"- {k}" for k in keywords[:40])
        comp_block = "\n".join(f"- {c}" for c in self.settings.competitors[:30])
        user = (
            f"Monitoring keywords (find public discussions matching these):\n{kw_block}\n\n"
            f"Competitors / brands of interest:\n{comp_block}\n\n"
            f"Return up to {limit} strongest items as JSON per system rules."
        )
        kwargs: dict[str, Any] = {
            "model": self.model,
            "instructions": WEB_RESEARCH_SYSTEM,
            "input": user,
            "tools": [{"type": "web_search_preview", "search_context_size": "high"}],
            "tool_choice": "auto",
            "max_tool_calls": self.settings.openai_web_research_max_tool_calls,
            "temperature": 0.2,
            "text": {"format": {"type": "json_object"}},
            "truncation": "auto",
        }
        resp = await self.client.responses.create(**kwargs)
        raw = (resp.output_text or "").strip()
        if not raw:
            return ExtractedWebMentionsBatch(items=[])
        payload = json.loads(raw)
        return ExtractedWebMentionsBatch.model_validate(payload)

    async def collect(self, keywords: list[str], limit: int) -> list[NormalizedMention]:
        if not self.settings.openai_api_key.strip() or not keywords:
            return []
        try:
            batch = await self._run_research(keywords, limit)
        except Exception as exc:  # noqa: BLE001
            logger.error("collector.openai_web_research.failure", error=str(exc), model=self.model)
            return []
        mentions = self._to_mentions(batch)
        logger.info("collector.openai_web_research.complete", count=len(mentions))
        return mentions[:limit]
