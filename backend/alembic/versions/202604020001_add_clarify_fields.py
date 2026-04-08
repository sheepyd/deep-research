"""add clarify fields

Revision ID: 202604020001
Revises: 202604010001
Create Date: 2026-04-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202604020001"
down_revision = "202604010001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_tasks",
        sa.Column(
            "clarify_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "research_tasks",
        sa.Column(
            "clarify_answers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("research_tasks", "clarify_questions", server_default=None)
    op.alter_column("research_tasks", "clarify_answers", server_default=None)


def downgrade() -> None:
    op.drop_column("research_tasks", "clarify_answers")
    op.drop_column("research_tasks", "clarify_questions")
