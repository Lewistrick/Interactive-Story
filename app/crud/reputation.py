"""CRUD helpers for reputation tiers and daily posting limits."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reputation_tier import ReputationTier
from app.models.story_part import StoryPart
from app.models.user_daily_limit import UserDailyLimit


async def get_all_tiers(db: AsyncSession) -> list[ReputationTier]:
    """Return all reputation tiers ordered by min_score ascending."""
    result = await db.execute(select(ReputationTier).order_by(ReputationTier.min_score.asc()))
    return list(result.scalars().all())


async def get_tier_for_score(db: AsyncSession, reputation_score: int) -> Optional[ReputationTier]:
    """Return the highest tier whose ``min_score`` is <= ``reputation_score``.

    Args:
        db: Database session.
        reputation_score: User's current reputation.

    Returns:
        Matching ``ReputationTier``, or None if no tiers are seeded.
    """
    result = await db.execute(
        select(ReputationTier)
        .where(ReputationTier.min_score <= reputation_score)
        .order_by(ReputationTier.min_score.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_or_create_daily_limit(
    db: AsyncSession,
    user_id: str | UUID,
    on_date: date | None = None,
) -> UserDailyLimit:
    """Fetch or create today's ``UserDailyLimit`` row for a user.

    Args:
        db: Database session.
        user_id: User UUID.
        on_date: Calendar date (defaults to UTC today).

    Returns:
        The daily limit row (``parts_written`` may be 0 for a new day).
    """
    day = on_date or datetime.now(timezone.utc).date()
    result = await db.execute(
        select(UserDailyLimit).where(
            UserDailyLimit.user_id == user_id,
            UserDailyLimit.date == day,
        )
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return row

    row = UserDailyLimit(user_id=user_id, date=day, parts_written=0)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def increment_daily_parts_written(
    db: AsyncSession,
    user_id: str | UUID,
    on_date: date | None = None,
) -> UserDailyLimit:
    """Increment ``parts_written`` for the user's daily limit row."""
    row = await get_or_create_daily_limit(db, user_id, on_date=on_date)
    row.parts_written += 1
    await db.commit()
    await db.refresh(row)
    return row


async def get_ancestor_chain(
    db: AsyncSession,
    start_part_id: str | UUID,
) -> list[StoryPart]:
    """Walk from ``start_part_id`` up to the root (inclusive), parent-first.

    Args:
        db: Database session.
        start_part_id: Part to start from (typically the parent being continued).

    Returns:
        List of parts from the start node toward the root.
    """
    chain: list[StoryPart] = []
    current_id: str | UUID | None = start_part_id
    while current_id is not None:
        result = await db.execute(select(StoryPart).where(StoryPart.id == current_id))
        part = result.scalar_one_or_none()
        if part is None:
            break
        chain.append(part)
        parent_id = part.parent_part_id
        current_id = str(parent_id) if parent_id is not None else None
    return chain
