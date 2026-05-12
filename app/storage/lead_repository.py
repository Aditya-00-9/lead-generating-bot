from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, ResponseStatus
from app.models.schemas import AIEnrichmentResult, NormalizedMention


class LeadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, mention: NormalizedMention, enrichment: AIEnrichmentResult, duplicate_hash: str) -> Lead:
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

    async def stats(self) -> dict:
        total = int((await self.session.scalar(select(func.count(Lead.id)))) or 0)
        worth = int((await self.session.scalar(select(func.count(Lead.id)).where(Lead.worth_responding))) or 0)
        return {"total_leads": total, "worth_responding": worth}
