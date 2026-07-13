"""lead collection outreach fields

Revision ID: 20260602_0005
Revises: 20260602_0004
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "20260602_0005"
down_revision = "20260602_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("competitor_mentioned", sa.String(length=64), nullable=True))
    op.add_column("leads", sa.Column("pain_category", sa.String(length=32), nullable=True))
    op.add_column("leads", sa.Column("suggested_hook", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("recency_signal", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "recency_signal")
    op.drop_column("leads", "suggested_hook")
    op.drop_column("leads", "pain_category")
    op.drop_column("leads", "competitor_mentioned")
