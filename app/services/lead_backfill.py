"""Backfill platform metadata and rank scores for existing leads."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.ranking.lead_ranker import LeadRanker
from app.utils.platform import platform_from_url, resolve_platform

logger = structlog.get_logger(__name__)


def _needs_platform_fix(platform: str | None) -> bool:
    return not platform or platform.strip().lower() in {"web", "unknown", "other"}


async def backfill_platform_and_ranks(session: AsyncSession, ranker: LeadRanker | None = None) -> int:
    """Fix platform from source_url and recalculate rank_score. Returns rows updated."""
    ranker = ranker or LeadRanker()
    leads = list((await session.scalars(select(Lead))).all())
    updated = 0
    for lead in leads:
        changed = False
        derived = platform_from_url(lead.source_url, fallback=lead.platform or "other")
        if _needs_platform_fix(lead.platform):
            fixed = resolve_platform(lead.platform, lead.source_url, fallback=derived)
            if fixed != (lead.platform or ""):
                lead.platform = fixed
                changed = True
        new_rank = ranker.score(
            intent=lead.intent_score,
            urgency=lead.urgency_score,
            engagement=lead.engagement_score,
            source_quality=lead.engagement_score,
            source=lead.source,
            competitor=lead.competitor,
            ingested_at=lead.created_at,
            platform=lead.platform,
            recency_signal=lead.recency_signal,
            source_published_at=lead.source_published_at,
        )
        if abs(new_rank - (lead.rank_score or 0.0)) > 0.0001:
            lead.rank_score = new_rank
            changed = True
        if changed:
            updated += 1
    if updated:
        await session.commit()
    logger.info("lead_backfill.complete", updated=updated, total=len(leads))
    return updated
