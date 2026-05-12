"""create lead_reports table

Revision ID: 20260506_0002
Revises: 20260506_0001
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260506_0002"
down_revision = "20260506_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("link", sa.String(length=1024), nullable=False),
        sa.Column("competitor", sa.String(length=64), nullable=False),
        sa.Column("pain_point", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(length=16), nullable=False),
        sa.Column("suggested_reply", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("link"),
    )
    op.create_index("ix_lead_reports_date", "lead_reports", ["date"], unique=False)
    op.create_index("ix_lead_reports_competitor", "lead_reports", ["competitor"], unique=False)
    op.create_index("ix_lead_reports_intent", "lead_reports", ["intent"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_lead_reports_intent", table_name="lead_reports")
    op.drop_index("ix_lead_reports_competitor", table_name="lead_reports")
    op.drop_index("ix_lead_reports_date", table_name="lead_reports")
    op.drop_table("lead_reports")
