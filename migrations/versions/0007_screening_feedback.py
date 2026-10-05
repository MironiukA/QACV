"""Store screening topics and feedback.

Revision ID: 0007_screen_feedback
Revises: 0006_resume_updates
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_screen_feedback"
down_revision = "0006_resume_updates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interview_sessions", sa.Column("feedback", sa.Text(), nullable=True))
    op.add_column("interview_sessions", sa.Column("passed", sa.Boolean(), nullable=True))
    op.add_column("interview_messages", sa.Column("topic", sa.String(length=150), nullable=True))
    op.add_column("interview_messages", sa.Column("feedback", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("interview_messages", "feedback")
    op.drop_column("interview_messages", "topic")
    op.drop_column("interview_sessions", "passed")
    op.drop_column("interview_sessions", "feedback")
