from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic import ConfigDict

from app.models.lead import IntentLabel, ResponseStatus


class NormalizedMention(BaseModel):
    source: str
    source_url: str
    author: str | None = None
    platform: str
    title: str = ""
    raw_text: str
    cleaned_text: str


class AIEnrichmentResult(BaseModel):
    competitor: str
    detected_pain_points: list[str] = Field(default_factory=list)
    intent_score: float
    intent_label: IntentLabel
    worth_responding: bool
    ai_summary: str
    suggested_reply: str
    sentiment: str
    urgency_score: float
    engagement_score: float
    tags: list[str] = Field(default_factory=list)


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    source: str
    source_url: str
    author: str | None
    platform: str
    competitor: str
    detected_pain_points: list[str]
    intent_score: float
    intent_label: IntentLabel
    worth_responding: bool
    ai_summary: str
    suggested_reply: str
    sentiment: str
    urgency_score: float
    engagement_score: float
    response_status: ResponseStatus
    reviewed_by: str | None
    tags: list[str]


class LeadsListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[LeadResponse]


class ReclassifyRequest(BaseModel):
    lead_id: UUID


class GenerateReplyRequest(BaseModel):
    lead_id: UUID
    tone: str = "empathetic"
