"""Store local AI analyses for vacancies.

Revision ID: 0003_add_vacancy_analyses
Revises: 0002_add_resume_files
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_vacancy_analyses"
down_revision = "0002_add_resume_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vacancy_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("vacancy_analyses")
