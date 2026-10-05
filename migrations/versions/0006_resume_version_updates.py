"""Track edits to generated resume versions.

Revision ID: 0006_resume_updates
Revises: 0005_refine_answers
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_resume_updates"
down_revision = "0005_refine_answers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resume_versions",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("resume_versions", "updated_at")
