from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, ResponseStatus
from app.models.schemas import AIEnrichmentResult, NormalizedMention


class LeadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        mention: NormalizedMention,
        enrichment: AIEnrichmentResult,
        duplicate_hash: str,
        content_hash: str | None = None,
        rank_score: float = 0.0,
    ) -> Lead:
        lead = Lead(
            source=mention.source,
            source_url=mention.source_url,
            author=mention.author,
            platform=mention.platform,
            raw_text=mention.raw_text,
            cleaned_text=mention.cleaned_text,
            competitor=enrichment.competitor,
            detected_pain_points=enrichment.detected_pain_points,
            intent_score=enrichment.intent_score,
            intent_label=enrichment.intent_label,
            worth_responding=enrichment.worth_responding,
            ai_summary=enrichment.ai_summary,
            suggested_reply=enrichment.suggested_reply,
            sentiment=enrichment.sentiment,
            urgency_score=enrichment.urgency_score,
            engagement_score=enrichment.engagement_score,
            duplicate_hash=duplicate_hash,
            content_hash=content_hash,
            rank_score=rank_score,
            response_status=ResponseStatus.new,
            tags=enrichment.tags,
        )
        self.session.add(lead)
        await self.session.commit()
        await self.session.refresh(lead)
        return lead

    async def get(self, lead_id: UUID | str) -> Lead | None:
        if isinstance(lead_id, str):
            lead_id = UUID(lead_id)
        return await self.session.get(Lead, lead_id)

    async def get_by_content_hash(self, content_hash: str) -> Lead | None:
        row = await self.session.scalar(
            select(Lead)
            .where(Lead.content_hash == content_hash)
            .where(Lead.ai_summary != "")
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
        return row

    async def list(
        self, page: int, page_size: int, competitor: str | None = None, intent_label: str | None = None
    ) -> tuple[int, list[Lead]]:
        query = select(Lead).order_by(Lead.created_at.desc())
        count_query = select(func.count(Lead.id))
        if competitor:
            query = query.where(Lead.competitor == competitor)
            count_query = count_query.where(Lead.competitor == competitor)
        if intent_label:
            query = query.where(Lead.intent_label == intent_label)
            count_query = count_query.where(Lead.intent_label == intent_label)
        total = int((await self.session.scalar(count_query)) or 0)
        rows = await self.session.scalars(query.offset((page - 1) * page_size).limit(page_size))
        return total, list(rows.all())

    async def list_all_for_export(self) -> list[Lead]:
        rows = await self.session.scalars(select(Lead).order_by(Lead.created_at.desc()))
        return list(rows.all())

    async def stats(self) -> dict:
        total = int((await self.session.scalar(select(func.count(Lead.id)))) or 0)
        worth = int((await self.session.scalar(select(func.count(Lead.id)).where(Lead.worth_responding))) or 0)
        return {"total_leads": total, "worth_responding": worth}

    async def quality_stats(self) -> list[dict]:
        rows = await self.session.execute(
            select(
                Lead.competitor,
                func.avg(Lead.human_score).label("avg_human_score"),
                func.count(Lead.id).label("total"),
                func.count(Lead.id).filter(Lead.human_score >= 3).label("high_quality_count"),
            )
            .where(Lead.human_score.isnot(None))
            .group_by(Lead.competitor)
            .order_by(func.avg(Lead.human_score).desc())
        )
        return [
            {
                "competitor": competitor,
                "avg_human_score": round(float(avg or 0), 2),
                "total": int(total),
                "high_quality_count": int(high_quality_count),
            }
            for competitor, avg, total, high_quality_count in rows.all()
        ]

    async def update_status(
        self,
        lead: Lead,
        status: ResponseStatus,
        reviewed_by: str | None = None,
    ) -> Lead:
        now = datetime.now(timezone.utc)
        lead.response_status = status
        if reviewed_by is not None:
            lead.reviewed_by = reviewed_by

        if status == ResponseStatus.reviewed and not lead.reviewed_at:
            lead.reviewed_at = now
        if status == ResponseStatus.posted:
            if not lead.reviewed_at:
                lead.reviewed_at = now
            lead.posted_at = now
        if status in {ResponseStatus.new, ResponseStatus.ignored}:
            lead.posted_at = None
            if status == ResponseStatus.new:
                lead.reviewed_at = None

        await self.session.commit()
        await self.session.refresh(lead)
        return lead

    async def update_human_score(self, lead: Lead, score: int, reviewer: str) -> Lead:
        lead.human_score = score
        lead.reviewed_by = reviewer
        lead.reviewed_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(lead)
        return lead
