"""Bayesian / Wilson scoring and trust-propagated recursive scores.

Pure math helpers are unit-tested without a database. Orchestration helpers
update cached ``recursive_score`` and ``User.reputation_score`` after votes.
"""

import math
import os
from collections.abc import Sequence
from datetime import datetime
from typing import cast
from uuid import UUID

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.reputation_snapshot import ReputationSnapshot
from app.models.story_part import StoryPart, VoteType
from app.models.user import User
from app.models.vote import Vote


def bayesian_average(
    ups: int,
    downs: int,
    *,
    prior_mean: float | None = None,
    prior_weight: float | None = None,
) -> float:
    """Compute Bayesian average of up/down votes on a [-1, 1] scale.

    Args:
        ups: Number of upvotes.
        downs: Number of downvotes.
        prior_mean: Prior mean (defaults to settings).
        prior_weight: Prior weight / pseudo-count (defaults to settings).

    Returns:
        Smoothed score in approximately [-1, 1].
    """
    prior_m = settings.BAYESIAN_PRIOR_MEAN if prior_mean is None else prior_mean
    prior_w = settings.BAYESIAN_PRIOR_WEIGHT if prior_weight is None else prior_weight
    total = ups + downs
    mean = ((ups - downs) / total) if total > 0 else 0.0
    return (total * mean + prior_w * prior_m) / (total + prior_w)


def wilson_lower_bound(
    ups: int,
    downs: int,
    *,
    z: float | None = None,
) -> float:
    """Wilson score interval lower bound for the proportion of upvotes.

    Args:
        ups: Number of upvotes.
        downs: Number of downvotes.
        z: Z-score for confidence (defaults to settings, 1.96 ≈ 95%).

    Returns:
        Lower confidence bound in [0, 1], or 0.0 when there are no votes.
    """
    z_val = settings.WILSON_Z if z is None else z
    n = ups + downs
    if n == 0:
        return 0.0
    phat = ups / n
    z2 = z_val * z_val
    denominator = 1.0 + z2 / n
    centre = phat + z2 / (2.0 * n)
    margin = z_val * math.sqrt((phat * (1.0 - phat) + z2 / (4.0 * n)) / n)
    return (centre - margin) / denominator


def trust_score(reputation: int, *, trust_constant: int | None = None) -> float:
    """Map author reputation to a trust weight in [0, 1).

    Args:
        reputation: Author's reputation score.
        trust_constant: Softening constant (defaults to settings).

    Returns:
        Trust weight ``rep / (rep + C)`` with rep clamped at 0.
    """
    constant = settings.TRUST_CONSTANT if trust_constant is None else trust_constant
    rep = max(0, reputation)
    return rep / (rep + constant)


def rapid_posting_penalty(
    hours_since_previous: float,
    *,
    min_hours: float | None = None,
) -> float:
    """Exponential penalty when consecutive posts are closer than ``min_hours``.

    Args:
        hours_since_previous: Hours between this post and the previous one.
        min_hours: Minimum spacing before full credit (defaults to settings).

    Returns:
        Multiplier in (0, 1] (1.0 means no penalty).
    """
    threshold = settings.RAPID_POSTING_MIN_HOURS if min_hours is None else min_hours
    if hours_since_previous >= threshold:
        return 1.0
    # Decay toward 0 as the gap approaches 0.
    return math.exp(-(threshold - hours_since_previous) / threshold)


def scale_score(value: float, *, scale: int | None = None) -> int:
    """Scale a float score to a stored integer cache value."""
    factor = settings.SCORE_SCALE if scale is None else scale
    return int(round(value * factor))


def compute_recursive_score(
    own_bayesian: float,
    child_contributions: Sequence[tuple[int, float]],
    *,
    scale: int | None = None,
) -> int:
    """Combine own Bayesian score with trust-weighted child recursive scores.

    Args:
        own_bayesian: Bayesian average for this part.
        child_contributions: Pairs of ``(child_recursive_score, child_author_trust)``.
        scale: Scale factor for the own-score term.

    Returns:
        Integer recursive score suitable for caching on ``StoryPart``.
    """
    own = scale_score(own_bayesian, scale=scale)
    children_total = sum(score * trust for score, trust in child_contributions)
    return int(round(own + children_total))


def compute_user_reputation(
    ups: int,
    downs: int,
    part_created_ats: Sequence[datetime],
    *,
    reputation_scale: int | None = None,
    min_hours: float | None = None,
) -> int:
    """Compute user reputation from aggregate votes and posting cadence.

    Uses the Wilson lower bound of all votes received on authored parts,
    scaled to an integer, then multiplies by the product of rapid-posting
    penalties between consecutive authored parts (sorted by time).

    Args:
        ups: Total upvotes across authored parts.
        downs: Total downvotes across authored parts.
        part_created_ats: Creation timestamps of authored parts.
        reputation_scale: Scale for Wilson → integer.
        min_hours: Rapid-posting threshold.

    Returns:
        Integer reputation score (may be 0 for new users).
    """
    scale = settings.REPUTATION_SCALE if reputation_scale is None else reputation_scale
    base = wilson_lower_bound(ups, downs) * scale

    sorted_times = sorted(part_created_ats)
    penalty = 1.0
    for prev, curr in zip(sorted_times, sorted_times[1:]):
        delta_hours = (curr - prev).total_seconds() / 3600.0
        penalty *= rapid_posting_penalty(delta_hours, min_hours=min_hours)

    return int(round(base * penalty))


async def count_votes_for_part(db: AsyncSession, story_id: str | UUID) -> tuple[int, int]:
    """Return ``(ups, downs)`` for a story part."""
    result = await db.execute(
        select(Vote.vote_type, func.count(Vote.id))
        .where(Vote.story_part_id == story_id)
        .group_by(Vote.vote_type)
    )
    ups = 0
    downs = 0
    for vote_type, count in result.all():
        if vote_type == VoteType.UP:
            ups = count
        elif vote_type == VoteType.DOWN:
            downs = count
    return ups, downs


async def _child_contributions(
    db: AsyncSession,
    parent_id: str | UUID,
) -> list[tuple[int, float]]:
    """Load direct children with author trust for recursive scoring."""
    result = await db.execute(
        select(StoryPart)
        .options(selectinload(StoryPart.author))
        .where(StoryPart.parent_part_id == parent_id)
    )
    children = list(result.scalars().all())
    contributions: list[tuple[int, float]] = []
    for child in children:
        author_rep = cast(int, child.author.reputation_score) if child.author else 0
        contributions.append(((child.recursive_score), trust_score(author_rep)))
    return contributions


async def update_story_recursive_scores(db: AsyncSession, story_id: str | UUID) -> None:
    """Recompute ``recursive_score`` for ``story_id`` and all ancestors."""
    current_id: str | UUID | None = story_id
    while current_id is not None:
        result = await db.execute(select(StoryPart).where(StoryPart.id == current_id))
        part = result.scalar_one_or_none()
        if part is None:
            break

        part_id = str(part.id)
        ups, downs = await count_votes_for_part(db, part_id)
        bayesian = bayesian_average(ups, downs)
        contributions = await _child_contributions(db, part_id)
        setattr(part, "recursive_score", compute_recursive_score(bayesian, contributions))

        parent_id = part.parent_part_id
        current_id = str(parent_id) if parent_id is not None else None

    await db.commit()


async def recalculate_user_reputation(db: AsyncSession, user_id: str | UUID) -> int:
    """Recalculate and persist a user's reputation from their authored parts.

    Args:
        db: Database session.
        user_id: User UUID.

    Returns:
        Updated reputation score (0 if the user is missing).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return 0

    parts_result = await db.execute(select(StoryPart).where(StoryPart.author_id == user_id))
    parts = list(parts_result.scalars().all())
    if not parts:
        setattr(user, "reputation_score", 0)
        db.add(ReputationSnapshot(user_id=user.id, score=0))
        await db.commit()
        return 0

    total_ups = 0
    total_downs = 0
    for part in parts:
        ups, downs = await count_votes_for_part(db, str(part.id))
        total_ups += ups
        total_downs += downs

    created_ats = [part.created_at for part in parts if part.created_at is not None]
    new_score = compute_user_reputation(total_ups, total_downs, created_ats)
    setattr(user, "reputation_score", new_score)
    db.add(ReputationSnapshot(user_id=user.id, score=new_score))
    await db.commit()
    return int(new_score)


async def refresh_scores_after_vote(story_id: str, author_id: str) -> None:
    """Background entrypoint: refresh recursive scores and author reputation.

    Opens a fresh DB session so it is safe to run after the request session
    has closed. No-ops when ``SKIP_SCORE_REFRESH=1`` (unit tests only).

    Note: ``SKIP_DB_INIT`` only disables ``create_all`` on startup; it must not
    gate this path — Docker Compose sets ``SKIP_DB_INIT=1`` in production-like
    local stacks while still needing live score refresh.
    """
    if os.getenv("SKIP_SCORE_REFRESH") == "1":
        return

    from app.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            await update_story_recursive_scores(db, story_id)
            await recalculate_user_reputation(db, author_id)
            from app.core.cache import invalidate_story_tree_cache
            from app.services.quarantine import evaluate_quarantine_after_score_refresh

            await invalidate_story_tree_cache(db, story_id)
            await evaluate_quarantine_after_score_refresh(db, story_id, author_id)
    except Exception:
        logger.exception(
            "Score refresh failed for story_id={} author_id={}",
            story_id,
            author_id,
        )
        raise
