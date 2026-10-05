"""Store structured vacancy profiles and chat modes.

Revision ID: 0008_interview_chat
Revises: 0007_screen_feedback
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_interview_chat"
down_revision = "0007_screen_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vacancy_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column("interview_sessions", sa.Column("mode", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("interview_sessions", "mode")
    op.drop_table("vacancy_profiles")
