"""create leads table

Revision ID: 20260506_0001
Revises:
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260506_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("cleaned_text", sa.Text(), nullable=False),
        sa.Column("competitor", sa.String(length=64), nullable=False),
        sa.Column("detected_pain_points", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("intent_score", sa.Float(), nullable=False),
        sa.Column("intent_label", sa.Enum("high", "medium", "low", name="intentlabel"), nullable=False),
        sa.Column("worth_responding", sa.Boolean(), nullable=False),
        sa.Column("ai_summary", sa.Text(), nullable=False),
        sa.Column("suggested_reply", sa.Text(), nullable=False),
        sa.Column("sentiment", sa.String(length=32), nullable=False),
        sa.Column("urgency_score", sa.Float(), nullable=False),
        sa.Column("engagement_score", sa.Float(), nullable=False),
        sa.Column("duplicate_hash", sa.String(length=128), nullable=False),
        sa.Column("response_status", sa.Enum("new", "reviewed", "posted", "ignored", name="responsestatus"), nullable=False),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_url"),
    )
    op.create_index("ix_leads_created_at", "leads", ["created_at"], unique=False)
    op.create_index("ix_leads_competitor", "leads", ["competitor"], unique=False)
    op.create_index("ix_leads_intent_label", "leads", ["intent_label"], unique=False)
    op.create_index("ix_leads_duplicate_hash", "leads", ["duplicate_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_leads_duplicate_hash", table_name="leads")
    op.drop_index("ix_leads_intent_label", table_name="leads")
    op.drop_index("ix_leads_competitor", table_name="leads")
    op.drop_index("ix_leads_created_at", table_name="leads")
    op.drop_table("leads")
    op.execute("DROP TYPE IF EXISTS intentlabel")
    op.execute("DROP TYPE IF EXISTS responsestatus")
