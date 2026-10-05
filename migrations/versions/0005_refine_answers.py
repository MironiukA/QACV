"""Store raw and refined clarification answers.

Revision ID: 0005_refine_answers
Revises: 0004_add_application_matches
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_refine_answers"
down_revision = "0004_add_application_matches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clarification_answers", sa.Column("raw_answer", sa.Text(), nullable=True))
    op.add_column("clarification_answers", sa.Column("resume_section", sa.String(length=30), nullable=True))
    op.execute("UPDATE clarification_answers SET raw_answer = answer WHERE raw_answer IS NULL")
    op.alter_column("clarification_answers", "raw_answer", nullable=False)


def downgrade() -> None:
    op.drop_column("clarification_answers", "resume_section")
    op.drop_column("clarification_answers", "raw_answer")
