from datetime import datetime, timezone
from typing import Literal

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.classifiers.openai_enricher import OpenAIEnricher
from app.config.settings import get_settings
from app.db.session import get_db_session
from app.observability.collector_health import all_collector_health, get_last_run_snapshot
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
from app.services.quality_feedback import aggregate_high_quality_combos, build_quality_feedback_report
from app.storage.lead_repository import LeadRepository

router = APIRouter(prefix="/api")


@router.get("/leads", response_model=LeadsListResponse)
async def get_leads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    competitor: str | None = None,
    intent_label: str | None = None,
    sort: Literal["rank_score", "created_at"] = Query(default="rank_score"),
    session: AsyncSession = Depends(get_db_session),
) -> LeadsListResponse:
    repo = LeadRepository(session)
    total, items = await repo.list(
        page=page, page_size=page_size, competitor=competitor, intent_label=intent_label, sort=sort
    )
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
    base = await LeadRepository(session).stats()
    base["last_run"] = get_last_run_snapshot()
    base["collectors"] = [asdict(row) for row in all_collector_health()]
    return base


@router.get("/stats/last-run")
async def get_last_run_stats() -> dict:
    return get_last_run_snapshot()


@router.get("/stats/quality-combos")
async def get_quality_combos(
    min_avg_score: float = Query(default=4.0, ge=1.0, le=5.0),
    min_samples: int = Query(default=2, ge=1),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    settings = get_settings()
    combos = await aggregate_high_quality_combos(
        session,
        min_avg_score=min_avg_score or settings.quality_feedback_min_avg_score,
        min_samples=min_samples or settings.quality_feedback_min_samples,
    )
    return build_quality_feedback_report(combos)


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
        competitor_mentioned=lead.competitor_mentioned,
        pain_category=lead.pain_category,
        suggested_hook=lead.suggested_hook,
        recency_signal=lead.recency_signal,
        source_published_at=lead.source_published_at,
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
        ingested_at=lead.created_at or datetime.now(timezone.utc),
        platform=lead.platform,
        recency_signal=lead.recency_signal,
        source_published_at=lead.source_published_at,
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
