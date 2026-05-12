import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IntentLabel(str, enum.Enum):
    high = "HIGH"
    medium = "MEDIUM"
    low = "LOW"


class ResponseStatus(str, enum.Enum):
    new = "NEW"
    reviewed = "REVIEWED"
    posted = "POSTED"
    ignored = "IGNORED"


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_created_at", "created_at"),
        Index("ix_leads_competitor", "competitor"),
        Index("ix_leads_intent_label", "intent_label"),
        Index("ix_leads_duplicate_hash", "duplicate_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)

    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_text: Mapped[str] = mapped_column(Text, nullable=False)
    competitor: Mapped[str] = mapped_column(String(64), nullable=False)
    detected_pain_points: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    intent_score: Mapped[float] = mapped_column(Float, nullable=False)
    intent_label: Mapped[IntentLabel] = mapped_column(Enum(IntentLabel), nullable=False)
    worth_responding: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ai_summary: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_reply: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment: Mapped[str] = mapped_column(String(32), nullable=False)
    urgency_score: Mapped[float] = mapped_column(Float, nullable=False)
    engagement_score: Mapped[float] = mapped_column(Float, nullable=False)
    duplicate_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    response_status: Mapped[ResponseStatus] = mapped_column(Enum(ResponseStatus), default=ResponseStatus.new)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)


class LeadReportRow(Base):
    __tablename__ = "lead_reports"
    __table_args__ = (
        Index("ix_lead_reports_date", "date"),
        Index("ix_lead_reports_competitor", "competitor"),
        Index("ix_lead_reports_intent", "intent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    link: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    competitor: Mapped[str] = mapped_column(String(64), nullable=False)
    pain_point: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(16), nullable=False)
    suggested_reply: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="New")
