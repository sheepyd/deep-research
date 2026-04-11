"""add owner id

Revision ID: 202604110001
Revises: 202604080001
Create Date: 2026-04-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "202604110001"
down_revision = "202604080001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_tasks",
        sa.Column("owner_id", sa.String(length=128), nullable=False, server_default="admin"),
    )
    op.create_index("ix_research_tasks_owner_id", "research_tasks", ["owner_id"], unique=False)
    op.alter_column("research_tasks", "owner_id", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_research_tasks_owner_id", table_name="research_tasks")
    op.drop_column("research_tasks", "owner_id")
