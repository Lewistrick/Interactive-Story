"""Moderator insights: voting-pattern flags and reputation history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.reputation_snapshot import ReputationSnapshot
from app.models.story_part import StoryPart, VoteType
from app.models.user import User
from app.models.vote import Vote


async def list_voting_pattern_flags(
    db: AsyncSession,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Flag users with suspicious recent voting behaviour.

    Patterns:
    - Heavy downvoter: many DOWN votes in the lookback window
    - Vote-only: votes cast but zero authored parts
    """
    lookback = timedelta(hours=settings.VOTING_PATTERN_LOOKBACK_HOURS)
    since = datetime.now(timezone.utc) - lookback
    down_threshold = settings.VOTING_PATTERN_DOWNVOTE_THRESHOLD

    down_counts = (
        select(Vote.user_id, func.count(Vote.id).label("downs"))
        .where(Vote.vote_type == VoteType.DOWN, Vote.created_at >= since)
        .group_by(Vote.user_id)
        .having(func.count(Vote.id) >= down_threshold)
        .subquery()
    )
    result = await db.execute(
        select(User, down_counts.c.downs)
        .join(down_counts, User.id == down_counts.c.user_id)
        .order_by(down_counts.c.downs.desc())
        .limit(limit)
    )
    flags: list[dict[str, Any]] = []
    for user, downs in result.all():
        flags.append(
            {
                "user_id": user.id,
                "username": user.username,
                "flag": "heavy_downvoter",
                "detail": f"{downs} downvotes in {settings.VOTING_PATTERN_LOOKBACK_HOURS}h",
                "reputation_score": user.reputation_score,
            }
        )

    # Vote-only accounts (any votes, no story parts)
    vote_users = select(Vote.user_id).distinct().subquery()
    authors = select(StoryPart.author_id).distinct().subquery()
    vote_only = await db.execute(
        select(User)
        .join(vote_users, User.id == vote_users.c.user_id)
        .outerjoin(authors, User.id == authors.c.author_id)
        .where(authors.c.author_id.is_(None))
        .limit(limit)
    )
    seen = {f["user_id"] for f in flags}
    for user in vote_only.scalars().all():
        if user.id in seen:
            continue
        flags.append(
            {
                "user_id": user.id,
                "username": user.username,
                "flag": "vote_only",
                "detail": "Has voted but never written a story part",
                "reputation_score": user.reputation_score,
            }
        )
    return flags


async def get_reputation_history(
    db: AsyncSession,
    user_id: str | UUID,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return recent reputation snapshots oldest→newest for charting."""
    result = await db.execute(
        select(ReputationSnapshot)
        .where(ReputationSnapshot.user_id == user_id)
        .order_by(ReputationSnapshot.created_at.desc())
        .limit(limit)
    )
    rows = list(reversed(result.scalars().all()))
    return [
        {"score": int(cast(int, row.score)), "created_at": row.created_at}
        for row in rows
    ]
