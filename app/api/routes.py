from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.classifiers.openai_enricher import OpenAIEnricher
from app.config.settings import get_settings
from app.db.session import get_db_session
from app.models.schemas import (
    GenerateReplyRequest,
    LeadResponse,
    LeadsListResponse,
    NormalizedMention,
    ReclassifyRequest,
    UpdateLeadScoreRequest,
    UpdateLeadStatusRequest,
)
from app.ranking.lead_ranker import LeadRanker
from app.storage.lead_repository import LeadRepository

router = APIRouter(prefix="/api")


@router.get("/leads", response_model=LeadsListResponse)
async def get_leads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    competitor: str | None = None,
    intent_label: str | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> LeadsListResponse:
    repo = LeadRepository(session)
    total, items = await repo.list(page=page, page_size=page_size, competitor=competitor, intent_label=intent_label)
    return LeadsListResponse(total=total, page=page, page_size=page_size, items=[LeadResponse.model_validate(i) for i in items])


@router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: str, session: AsyncSession = Depends(get_db_session)) -> LeadResponse:
    repo = LeadRepository(session)
    lead = await repo.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadResponse.model_validate(lead)


@router.get("/stats/quality")
async def get_quality_stats(session: AsyncSession = Depends(get_db_session)) -> list[dict]:
    return await LeadRepository(session).quality_stats()


@router.get("/stats")
async def get_stats(session: AsyncSession = Depends(get_db_session)) -> dict:
    return await LeadRepository(session).stats()


@router.patch("/leads/{lead_id}/score", response_model=LeadResponse)
async def update_lead_score(
    lead_id: str, payload: UpdateLeadScoreRequest, session: AsyncSession = Depends(get_db_session)
) -> LeadResponse:
    repo = LeadRepository(session)
    lead = await repo.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    updated = await repo.update_human_score(lead, payload.score, payload.reviewer)
    return LeadResponse.model_validate(updated)


@router.post("/reclassify")
async def reclassify(payload: ReclassifyRequest, session: AsyncSession = Depends(get_db_session)) -> dict:
    repo = LeadRepository(session)
    lead = await repo.get(payload.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    mention = NormalizedMention(
        source=lead.source,
        source_url=lead.source_url,
        author=lead.author,
        platform=lead.platform,
        title="",
        raw_text=lead.raw_text,
        cleaned_text=lead.cleaned_text,
    )
    enriched = await OpenAIEnricher(get_settings()).enrich(mention)
    lead.competitor = enriched.competitor
    lead.detected_pain_points = enriched.detected_pain_points
    lead.intent_score = enriched.intent_score
    lead.intent_label = enriched.intent_label
    lead.worth_responding = enriched.worth_responding
    lead.ai_summary = enriched.ai_summary
    lead.suggested_reply = enriched.suggested_reply
    lead.sentiment = enriched.sentiment
    lead.urgency_score = enriched.urgency_score
    lead.engagement_score = enriched.engagement_score
    lead.tags = enriched.tags
    lead.rank_score = LeadRanker().score(
        intent=enriched.intent_score,
        urgency=enriched.urgency_score,
        engagement=enriched.engagement_score,
        source_quality=enriched.engagement_score,
        source=lead.source,
        competitor=enriched.competitor,
        created_at=lead.created_at or datetime.now(timezone.utc),
    )
    await session.commit()
    return {"status": "ok"}


@router.post("/generate-reply")
async def generate_reply(payload: GenerateReplyRequest, session: AsyncSession = Depends(get_db_session)) -> dict:
    repo = LeadRepository(session)
    lead = await repo.get(payload.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"lead_id": str(lead.id), "tone": payload.tone, "suggested_reply": lead.suggested_reply}


@router.post("/leads/{lead_id}/status", response_model=LeadResponse)
async def update_lead_status(
    lead_id: str, payload: UpdateLeadStatusRequest, session: AsyncSession = Depends(get_db_session)
) -> LeadResponse:
    repo = LeadRepository(session)
    lead = await repo.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    updated = await repo.update_status(lead, payload.response_status, payload.reviewed_by)
    return LeadResponse.model_validate(updated)
