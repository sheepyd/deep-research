"""add follow up fields

Revision ID: 202604080001
Revises: 202604020001
Create Date: 2026-04-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202604080001"
down_revision = "202604020001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_tasks",
        sa.Column("parent_task_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "research_tasks",
        sa.Column("research_iteration", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "research_tasks",
        sa.Column("follow_up_request", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_research_tasks_parent_task_id",
        "research_tasks",
        "research_tasks",
        ["parent_task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("research_tasks", "research_iteration", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_research_tasks_parent_task_id", "research_tasks", type_="foreignkey")
    op.drop_column("research_tasks", "follow_up_request")
    op.drop_column("research_tasks", "research_iteration")
    op.drop_column("research_tasks", "parent_task_id")
