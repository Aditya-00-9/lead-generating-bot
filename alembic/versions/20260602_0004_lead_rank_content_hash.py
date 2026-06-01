"""lead rank_score, content_hash, human_score

Revision ID: 20260602_0004
Revises: 20260528_0003
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "20260602_0004"
down_revision = "20260528_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("content_hash", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("rank_score", sa.Float(), server_default="0", nullable=False))
    op.add_column("leads", sa.Column("human_score", sa.SmallInteger(), nullable=True))
    op.create_index(
        "idx_leads_content_hash",
        "leads",
        ["content_hash"],
        postgresql_where=sa.text("content_hash IS NOT NULL"),
    )
    op.create_index("idx_leads_rank_score", "leads", ["rank_score"])


def downgrade() -> None:
    op.drop_index("idx_leads_rank_score", table_name="leads")
    op.drop_index("idx_leads_content_hash", table_name="leads")
    op.drop_column("leads", "human_score")
    op.drop_column("leads", "rank_score")
    op.drop_column("leads", "content_hash")
