"""Add must_reset_password and token_version for forced password reset.

Revision ID: 007_password_reset_fields
Revises: 006_pattern_dismissals
Create Date: 2026-07-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007_password_reset_fields"
down_revision: str | None = "006_pattern_dismissals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add account-security columns on users."""
    op.add_column(
        "users",
        sa.Column(
            "must_reset_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    """Remove account-security columns from users."""
    op.drop_column("users", "token_version")
    op.drop_column("users", "must_reset_password")
