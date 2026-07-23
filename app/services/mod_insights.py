"""Moderator insights: voting-pattern flags and reputation history."""

from datetime import datetime, timedelta, timezone
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.pattern_dismissal import get_active_dismissal_keys
from app.models.reputation_snapshot import ReputationSnapshot
from app.models.story_part import StoryPart, VoteType
from app.models.user import User
from app.models.vote import Vote

KNOWN_PATTERN_FLAGS = ("heavy_downvoter", "vote_only")


def pattern_severity(*, flag: str, metric: int) -> int:
    """Compute a sort weight — higher means more urgent for moderators.

    Heavy downvoters dominate the list. Vote-only accounts scale with how many
    votes they cast (two votes ≈ severity 2; dozens of votes rank higher).
    """
    match flag:
        case "heavy_downvoter":
            return 1_000 + int(metric)
        case "vote_only":
            return int(metric)
        case _:
            return 0


async def list_voting_pattern_flags(
    db: AsyncSession,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Flag users with suspicious recent voting behaviour, highest severity first.

    Patterns:
    - Heavy downvoter: many DOWN votes in the lookback window
    - Vote-only: votes cast but zero authored parts (severity ≈ vote count)

    Active pattern dismissals and blocked users are omitted.
    """
    lookback = timedelta(hours=settings.VOTING_PATTERN_LOOKBACK_HOURS)
    since = datetime.now(timezone.utc) - lookback
    down_threshold = settings.VOTING_PATTERN_DOWNVOTE_THRESHOLD
    dismissed = await get_active_dismissal_keys(db)

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
        .where(User.is_blocked == False)  # noqa: E712
    )
    flags: list[dict[str, Any]] = []
    for user, downs in result.all():
        user_id = cast(UUID, user.id)
        if (user_id, "heavy_downvoter") in dismissed:
            continue
        metric = int(downs)
        flags.append(
            {
                "user_id": user_id,
                "username": user.username,
                "flag": "heavy_downvoter",
                "detail": (f"{metric} down votes in {settings.VOTING_PATTERN_LOOKBACK_HOURS:g}h"),
                "reputation_score": int(user.reputation_score),
                "metric": metric,
                "severity": pattern_severity(flag="heavy_downvoter", metric=metric),
            }
        )

    vote_totals = (
        select(Vote.user_id, func.count(Vote.id).label("votes")).group_by(Vote.user_id).subquery()
    )
    authors = select(StoryPart.author_id).distinct().subquery()
    vote_only = await db.execute(
        select(User, vote_totals.c.votes)
        .join(vote_totals, User.id == vote_totals.c.user_id)
        .outerjoin(authors, User.id == authors.c.author_id)
        .where(
            authors.c.author_id.is_(None),
            User.is_blocked == False,  # noqa: E712
        )
    )
    seen = {f["user_id"] for f in flags}
    for user, votes in vote_only.all():
        user_id = cast(UUID, user.id)
        if user_id in seen:
            continue
        if (user_id, "vote_only") in dismissed:
            continue
        metric = int(votes)
        flags.append(
            {
                "user_id": user_id,
                "username": user.username,
                "flag": "vote_only",
                "detail": f"Has cast {metric} vote(s) but never written a story part",
                "reputation_score": int(user.reputation_score),
                "metric": metric,
                "severity": pattern_severity(flag="vote_only", metric=metric),
            }
        )

    flags.sort(key=lambda row: (-int(row["severity"]), str(row["username"])))
    return flags[:limit]


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
    return [{"score": int(cast(int, row.score)), "created_at": row.created_at} for row in rows]
