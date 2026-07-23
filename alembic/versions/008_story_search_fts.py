"""Add generated tsvector + GIN index for story full-text search.

Revision ID: 008_story_search_fts
Revises: 007_password_reset_fields
Create Date: 2026-07-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_story_search_fts"
down_revision: str | None = "007_password_reset_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add search_vector generated column and GIN index."""
    op.add_column(
        "story_parts",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(teaser, '') || ' ' || coalesce(content, ''))",
                persisted=True,
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_story_parts_search_vector",
        "story_parts",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Drop search index and column."""
    op.drop_index("ix_story_parts_search_vector", table_name="story_parts")
    op.drop_column("story_parts", "search_vector")
