"""Add pattern_dismissals for suppressing voting-pattern flags.

Revision ID: 006_pattern_dismissals
Revises: 005_reputation_snapshots
Create Date: 2026-07-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006_pattern_dismissals"
down_revision: str | None = "005_reputation_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create pattern_dismissals table."""
    op.create_table(
        "pattern_dismissals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("flag", sa.String(length=64), nullable=False),
        sa.Column("dismissed_by_moderator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["dismissed_by_moderator_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", "flag", name="unique_user_pattern_flag"),
    )
    op.create_index("ix_pattern_dismissals_user_id", "pattern_dismissals", ["user_id"])


def downgrade() -> None:
    """Drop pattern_dismissals table."""
    op.drop_index("ix_pattern_dismissals_user_id", table_name="pattern_dismissals")
    op.drop_table("pattern_dismissals")
