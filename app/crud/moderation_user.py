"""CRUD helpers for moderator user-history views."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.story_part import StoryPart, VoteType
from app.models.vote import Vote


class PartSortField(str, Enum):
    """Allowed sort keys for a user's authored parts."""

    AGE = "age"
    VOTE_SCORE = "vote_score"
    RECURSIVE_SCORE = "recursive_score"


async def count_authored_parts(
    db: AsyncSession,
    user_id: UUID,
    *,
    quarantined_only: bool = False,
) -> int:
    """Count story parts authored by ``user_id``."""
    query = select(func.count(StoryPart.id)).where(StoryPart.author_id == user_id)
    if quarantined_only:
        query = query.where(StoryPart.is_quarantined.is_(True))
    result = await db.execute(query)
    return int(result.scalar_one())


async def count_votes_by_type(db: AsyncSession, user_id: UUID) -> tuple[int, int]:
    """Return ``(up_count, down_count)`` for votes cast by ``user_id``."""
    result = await db.execute(
        select(Vote.vote_type, func.count(Vote.id))
        .where(Vote.user_id == user_id)
        .group_by(Vote.vote_type)
    )
    ups = 0
    downs = 0
    for vote_type, count in result.all():
        if vote_type == VoteType.UP:
            ups = int(count)
        elif vote_type == VoteType.DOWN:
            downs = int(count)
    return ups, downs


async def list_authored_parts(
    db: AsyncSession,
    user_id: UUID,
    *,
    sort: PartSortField = PartSortField.AGE,
    order: Literal["asc", "desc"] = "desc",
    skip: int = 0,
    limit: int = 50,
    quarantined_only: bool = False,
) -> list[StoryPart]:
    """List parts authored by ``user_id`` with sort and pagination."""
    query = select(StoryPart).where(StoryPart.author_id == user_id)
    if quarantined_only:
        query = query.where(StoryPart.is_quarantined.is_(True))

    if sort == PartSortField.VOTE_SCORE:
        column = StoryPart.vote_score
    elif sort == PartSortField.RECURSIVE_SCORE:
        column = StoryPart.recursive_score
    else:
        column = StoryPart.created_at

    primary = column.asc() if order == "asc" else column.desc()
    # Stable tie-breaker so pages do not shuffle.
    query = query.order_by(primary, StoryPart.id.asc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_votes_cast(
    db: AsyncSession,
    user_id: UUID,
    *,
    skip: int = 0,
    limit: int = 50,
    vote_type: VoteType | None = None,
) -> list[Vote]:
    """List votes cast by ``user_id`` with the target story part loaded.

    Returns:
        Vote rows newest first; each has ``story_part`` (and author) loaded.
    """
    query = (
        select(Vote)
        .options(selectinload(Vote.story_part).selectinload(StoryPart.author))
        .where(Vote.user_id == user_id)
    )
    if vote_type is not None:
        query = query.where(Vote.vote_type == vote_type)
    query = query.order_by(Vote.created_at.desc(), Vote.id.asc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())
