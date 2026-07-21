"""Reputation-tier limits: length, daily posts, spacing, and vote gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.reputation import (
    get_ancestor_chain,
    get_or_create_daily_limit,
    get_tier_for_score,
    increment_daily_parts_written,
)


class TierLimits(Protocol):
    """Minimal tier attribute interface used by limit checks."""

    name: str
    max_teaser_length: int
    max_content_length: int
    daily_part_limit: int
    min_parts_between_own: int
    can_vote_threshold: int


class UserLike(Protocol):
    """Minimal user attributes needed for limit checks."""

    id: Any
    reputation_score: int
    is_blocked: bool


@dataclass(frozen=True)
class UserLimits:
    """Resolved reputation tier limits for API/UI consumption."""

    tier_name: str
    max_teaser_length: int
    max_content_length: int
    daily_part_limit: int
    min_parts_between_own: int
    can_vote_threshold: int
    can_vote: bool
    parts_written_today: int


@dataclass(frozen=True)
class _DefaultTier:
    """Fallback when the tiers table is empty (should not happen after migrations)."""

    name: str = "Novice"
    min_score: int = 0
    max_teaser_length: int = 128
    max_content_length: int = 512
    daily_part_limit: int = 2
    min_parts_between_own: int = 3
    can_vote_threshold: int = 0


_DEFAULT_TIER = _DefaultTier()


async def resolve_tier(db: AsyncSession, reputation_score: int) -> TierLimits:
    """Resolve the user's reputation tier, falling back to Novice defaults."""
    tier = await get_tier_for_score(db, reputation_score)
    return cast(TierLimits, tier if tier is not None else _DEFAULT_TIER)


async def get_user_limits(db: AsyncSession, user: UserLike) -> UserLimits:
    """Build the full limits snapshot for a user (used by ``/auth/me``)."""
    tier = await resolve_tier(db, user.reputation_score)
    daily = await get_or_create_daily_limit(db, user.id)
    return UserLimits(
        tier_name=tier.name,
        max_teaser_length=tier.max_teaser_length,
        max_content_length=tier.max_content_length,
        daily_part_limit=tier.daily_part_limit,
        min_parts_between_own=tier.min_parts_between_own,
        can_vote_threshold=tier.can_vote_threshold,
        can_vote=user.reputation_score >= tier.can_vote_threshold,
        parts_written_today=cast(int, daily.parts_written),
    )


def check_content_length(teaser: str, content: str, tier: TierLimits) -> None:
    """Raise 400 if teaser or content exceed the tier's max lengths."""
    if len(teaser) > tier.max_teaser_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Teaser exceeds your tier limit of {tier.max_teaser_length} characters "
                f"({tier.name})."
            ),
        )
    if len(content) > tier.max_content_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Content exceeds your tier limit of {tier.max_content_length} characters "
                f"({tier.name})."
            ),
        )


async def check_daily_limit(db: AsyncSession, user: UserLike, tier: TierLimits) -> None:
    """Raise 429 if the user has already used today's posting quota."""
    daily = await get_or_create_daily_limit(db, user.id)
    if daily.parts_written >= tier.daily_part_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Daily part limit reached ({tier.daily_part_limit} for {tier.name}). "
                "Try again tomorrow."
            ),
        )


async def check_spacing_rule(
    db: AsyncSession,
    user: UserLike,
    parent_id: str | UUID,
    tier: TierLimits,
) -> None:
    """Enforce min intervening parts by other authors along the ancestor path.

    Walks from ``parent_id`` toward the root. If a part by the same author is
    found with fewer than ``min_parts_between_own`` intervening parts, reject.
    """
    required = tier.min_parts_between_own
    if required <= 0:
        return

    chain = await get_ancestor_chain(db, parent_id)
    intervening = 0
    for part in chain:
        if part.author_id == user.id:
            if intervening < required:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Spacing rule: need {required} other authors' parts between your "
                        f"contributions ({tier.name}). Found only {intervening}."
                    ),
                )
            return
        intervening += 1


def check_can_vote(user: UserLike, tier: TierLimits) -> None:
    """Raise 403 if the user lacks reputation to vote."""
    if user.reputation_score < tier.can_vote_threshold:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Reputation {user.reputation_score} is below the voting threshold "
                f"of {tier.can_vote_threshold}."
            ),
        )


async def enforce_create_limits(
    db: AsyncSession,
    user: UserLike,
    teaser: str,
    content: str,
    parent_id: Optional[str | UUID] = None,
) -> TierLimits:
    """Run all create/continue limit checks; return the resolved tier.

    Args:
        db: Database session.
        user: Authenticated author.
        teaser: Proposed teaser text.
        content: Proposed content text.
        parent_id: Parent part when continuing; None for root stories.

    Returns:
        The user's reputation tier (for callers that need it).
    """
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is blocked",
        )

    tier = await resolve_tier(db, user.reputation_score)
    check_content_length(teaser, content, tier)
    await check_daily_limit(db, user, tier)
    if parent_id is not None:
        await check_spacing_rule(db, user, parent_id, tier)
    return tier


async def record_part_created(db: AsyncSession, user_id: str | UUID) -> None:
    """Increment the user's daily parts-written counter after a successful create."""
    await increment_daily_parts_written(db, user_id)


async def enforce_vote_limits(db: AsyncSession, user: UserLike) -> None:
    """Run vote-gate checks for the current user."""
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is blocked",
        )
    tier = await resolve_tier(db, user.reputation_score)
    check_can_vote(user, tier)
