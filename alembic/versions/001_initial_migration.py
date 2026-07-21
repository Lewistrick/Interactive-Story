"""Initial migration

Revision ID: 001
Revises:
Create Date: 2026-07-20 12:20:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("reputation_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_quarantined", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("quarantine_reason", sa.String(), nullable=True),
        sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_moderator", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default="false"),
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
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # Create reputation_tiers table
    op.create_table(
        "reputation_tiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("min_score", sa.Integer(), nullable=False),
        sa.Column("max_teaser_length", sa.Integer(), nullable=False),
        sa.Column("max_content_length", sa.Integer(), nullable=False),
        sa.Column("daily_part_limit", sa.Integer(), nullable=False),
        sa.Column("min_parts_between_own", sa.Integer(), nullable=False),
        sa.Column("can_vote_threshold", sa.Integer(), nullable=False),
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
    )

    # Create story_parts table
    op.create_table(
        "story_parts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_part_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("teaser", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("vote_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recursive_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_quarantined", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("quarantine_reason", sa.String(), nullable=True),
        sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("depth_level", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["parent_part_id"],
            ["story_parts.id"],
        ),
    )

    # Create votes table
    op.create_table(
        "votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_part_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vote_type", sa.Enum("UP", "DOWN", name="votetype"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["story_part_id"],
            ["story_parts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.UniqueConstraint("user_id", "story_part_id", name="unique_user_story_vote"),
    )

    # Create quarantine_logs table
    op.create_table(
        "quarantine_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.Enum("USER", "STORY_PART", name="entitytype"), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("triggered_by", sa.String(), nullable=False),
        sa.Column("automatic", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("resolved_by_moderator_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "resolution_action",
            sa.Enum("ALLOWED", "REMOVED", "BLOCKED", name="resolutionaction"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Create user_daily_limits table
    op.create_table(
        "user_daily_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("parts_written", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.UniqueConstraint("user_id", "date", name="unique_user_date"),
    )

    # Insert default reputation tiers
    op.execute("""
        INSERT INTO reputation_tiers (id, name, min_score, max_teaser_length, max_content_length, daily_part_limit, min_parts_between_own, can_vote_threshold)
        VALUES 
            (gen_random_uuid(), 'Novice', 0, 128, 512, 2, 3, 50),
            (gen_random_uuid(), 'Apprentice', 50, 192, 768, 3, 2, 50),
            (gen_random_uuid(), 'Storyteller', 150, 256, 1024, 5, 1, 50),
            (gen_random_uuid(), 'Master', 300, 384, 1536, 10, 0, 50),
            (gen_random_uuid(), 'Legend', 500, 512, 2048, 20, 0, 50)
    """)


def downgrade() -> None:
    op.drop_table("user_daily_limits")
    op.drop_table("quarantine_logs")
    op.drop_table("votes")
    op.drop_table("story_parts")
    op.drop_table("reputation_tiers")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
