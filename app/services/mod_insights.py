"""Moderator insights: voting-pattern flags and reputation history."""

from collections import defaultdict
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

KNOWN_PATTERN_FLAGS = ("heavy_downvoter", "vote_only", "voting_ring")


def pattern_severity(*, flag: str, metric: int) -> int:
    """Compute a sort weight — higher means more urgent for moderators.

    Heavy downvoters dominate the list. Voting rings rank next. Vote-only
    accounts scale with how many votes they cast.
    """
    match flag:
        case "heavy_downvoter":
            return 1_000 + int(metric)
        case "voting_ring":
            return 500 + int(metric)
        case "vote_only":
            return int(metric)
        case _:
            return 0


async def _flag_voting_rings(
    db: AsyncSession,
    *,
    since: datetime,
    dismissed: set[tuple[UUID, str]],
    already_flagged: set[UUID],
) -> list[dict[str, Any]]:
    """Flag users who co-vote the same targets (same type) often enough to look coordinated.

    Builds pairwise co-vote counts from recent votes: whenever two users vote the
    same story part with the same vote type, that pair's shared-target count
    increments. Users whose strongest partnership reaches
    ``VOTING_RING_MIN_SHARED_TARGETS`` are flagged.
    """
    min_shared = settings.VOTING_RING_MIN_SHARED_TARGETS
    scan_limit = settings.VOTING_RING_MAX_VOTES_SCAN
    result = await db.execute(
        select(Vote.user_id, Vote.story_part_id, Vote.vote_type)
        .where(Vote.created_at >= since)
        .order_by(Vote.created_at.desc())
        .limit(scan_limit)
    )
    by_target: dict[tuple[Any, Any], set[UUID]] = defaultdict(set)
    for user_id, part_id, vote_type in result.all():
        by_target[(part_id, vote_type)].add(cast(UUID, user_id))

    pair_counts: dict[tuple[UUID, UUID], int] = defaultdict(int)
    for voters in by_target.values():
        if len(voters) < 2:
            continue
        ordered = sorted(voters, key=str)
        for i, left in enumerate(ordered):
            for right in ordered[i + 1 :]:
                pair_counts[(left, right)] += 1

    best_partner: dict[UUID, tuple[int, UUID]] = {}
    for (left, right), shared in pair_counts.items():
        if shared < min_shared:
            continue
        for user_id, partner_id in ((left, right), (right, left)):
            current = best_partner.get(user_id)
            if current is None or shared > current[0]:
                best_partner[user_id] = (shared, partner_id)

    if not best_partner:
        return []

    user_ids = list(best_partner.keys())
    users_result = await db.execute(
        select(User).where(
            User.id.in_(user_ids),
            User.is_blocked == False,  # noqa: E712
        )
    )
    users_by_id = {u.id: u for u in users_result.scalars().all()}

    flags: list[dict[str, Any]] = []
    for user_id, (shared, partner_id) in best_partner.items():
        if user_id in already_flagged:
            continue
        if (user_id, "voting_ring") in dismissed:
            continue
        user = users_by_id.get(user_id)
        if user is None:
            continue
        partner = users_by_id.get(partner_id)
        partner_name = partner.username if partner is not None else str(partner_id)
        flags.append(
            {
                "user_id": user_id,
                "username": user.username,
                "flag": "voting_ring",
                "detail": (
                    f"Coordinated voting: {shared} shared targets with {partner_name} "
                    f"in {settings.VOTING_PATTERN_LOOKBACK_HOURS:g}h"
                ),
                "reputation_score": int(user.reputation_score),
                "metric": shared,
                "severity": pattern_severity(flag="voting_ring", metric=shared),
            }
        )
    return flags


async def list_voting_pattern_flags(
    db: AsyncSession,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Flag users with suspicious recent voting behaviour, highest severity first.

    Patterns:
    - Heavy downvoter: many DOWN votes in the lookback window
    - Voting ring: co-votes on many of the same targets with another account
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

    seen = {f["user_id"] for f in flags}
    ring_flags = await _flag_voting_rings(
        db, since=since, dismissed=dismissed, already_flagged=seen
    )
    flags.extend(ring_flags)
    seen.update(f["user_id"] for f in ring_flags)

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
