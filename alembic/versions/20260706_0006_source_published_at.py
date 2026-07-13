"""add source_published_at to leads

Revision ID: 20260706_0006
Revises: 20260602_0005
Create Date: 2026-07-06
"""

from alembic import op
import sqlalchemy as sa

revision = "20260706_0006"
down_revision = "20260602_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "source_published_at")
