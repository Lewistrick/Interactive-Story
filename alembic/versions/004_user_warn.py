"""Add user quarantine_until and WARNED resolution action.

Revision ID: 004_user_warn
Revises: 003_reports
Create Date: 2026-07-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_user_warn"
down_revision: Union[str, None] = "003_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add temporary quarantine expiry and WARNED enum value."""
    op.add_column(
        "users",
        sa.Column("quarantine_until", sa.DateTime(timezone=True), nullable=True),
    )
    # PostgreSQL enum alteration (existing resolutionaction type from 001).
    op.execute("ALTER TYPE resolutionaction ADD VALUE IF NOT EXISTS 'WARNED'")


def downgrade() -> None:
    """Drop quarantine_until (enum value WARNED is left in place — PG limitation)."""
    op.drop_column("users", "quarantine_until")
