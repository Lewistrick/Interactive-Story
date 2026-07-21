"""Alembic migration: reports table for user-flagged story parts.

Revision ID: 003_reports
Revises: 002_novice_can_vote
Create Date: 2026-07-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_reports"
down_revision: Union[str, None] = "002_novice_can_vote"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the reports table."""
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_part_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["story_part_id"], ["story_parts.id"]),
        sa.UniqueConstraint("reporter_id", "story_part_id", name="unique_reporter_story_report"),
    )
    op.create_index("ix_reports_story_part_id", "reports", ["story_part_id"])


def downgrade() -> None:
    """Drop the reports table."""
    op.drop_index("ix_reports_story_part_id", table_name="reports")
    op.drop_table("reports")
