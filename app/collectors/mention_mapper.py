"""Map OpenAI collection JSON items to NormalizedMention."""

from __future__ import annotations

from app.models.schemas import ExtractedWebMention, NormalizedMention
from app.utils.platform import resolve_platform


def _sanitize_url(url: str) -> str:
    return (url or "").strip().split()[0]


def mention_from_extracted(item: ExtractedWebMention, *, source: str) -> NormalizedMention | None:
    url = _sanitize_url(item.source_url)
    if not (url.startswith("http://") or url.startswith("https://")):
        return None
    excerpt = (item.excerpt or item.title or "").strip()[:8000]
    title = (item.title or excerpt[:200]).strip()
    platform = resolve_platform(item.platform, url)
    author = (item.author_handle or "").strip() or None
    competitor_mentioned = (item.competitor_mentioned or "").strip() or None
    pain_category = (item.pain_category or "other").strip().lower()[:32] or "other"
    suggested_hook = (item.suggested_hook or "").strip()[:500] or None
    recency_signal = (item.recency_signal or "unknown").strip().lower()[:32] or "unknown"
    return NormalizedMention(
        source=source,
        source_url=url,
        author=author,
        platform=platform,
        title=title,
        raw_text=excerpt,
        cleaned_text=excerpt[:6000],
        competitor_mentioned=competitor_mentioned,
        pain_category=pain_category,
        suggested_hook=suggested_hook,
        recency_signal=recency_signal,
        collection_relevance_score=item.relevance_score,
    )
