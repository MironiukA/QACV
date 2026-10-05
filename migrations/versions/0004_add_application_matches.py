"""Store evidence-backed application matches.

Revision ID: 0004_add_application_matches
Revises: 0003_add_vacancy_analyses
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_application_matches"
down_revision = "0003_add_vacancy_analyses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("vacancy_requirements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("evidence", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("application_matches")
