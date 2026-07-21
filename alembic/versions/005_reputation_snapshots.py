"""Reputation snapshots for moderator history charts.

Revision ID: 005_reputation_snapshots
Revises: 004_user_warn
Create Date: 2026-07-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_reputation_snapshots"
down_revision: str | None = "004_user_warn"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create reputation_snapshots table."""
    op.create_table(
        "reputation_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_reputation_snapshots_user_created",
        "reputation_snapshots",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    """Drop reputation_snapshots table."""
    op.drop_index("ix_reputation_snapshots_user_created", table_name="reputation_snapshots")
    op.drop_table("reputation_snapshots")
