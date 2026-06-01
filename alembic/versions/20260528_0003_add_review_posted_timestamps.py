"""add reviewed_at and posted_at to leads

Revision ID: 20260528_0003
Revises: 20260506_0002
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20260528_0003"
down_revision = "20260506_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "posted_at")
    op.drop_column("leads", "reviewed_at")
