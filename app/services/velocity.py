"""Hacked-account heuristics: sudden action bursts and IP shifts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from fastapi import Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import get_client_ip
from app.core.redis import get_redis
from app.crud.user import get_user_by_id
from app.services.quarantine import quarantine_user


class UserLike(Protocol):
    """Minimal user fields for velocity checks."""

    id: Any
    created_at: Any
    is_quarantined: Any


def _account_age_hours(user: UserLike) -> float:
    """Hours since account creation (UTC)."""
    created = user.created_at
    if created is None:
        return 0.0
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created).total_seconds() / 3600.0


async def _incr_burst(key: str, window_seconds: int) -> int:
    """Increment a Redis fixed-window counter; return the new count (0 if Redis down)."""
    client = await get_redis()
    if client is None:
        return 0
    try:
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_seconds)
        return int(count)
    except Exception:
        logger.warning("Velocity counter failed for key={}", key)
        return 0


async def _ip_shifted(user_id: str, request: Request) -> bool:
    """Return True if this request IP differs from the last recorded IP for the user."""
    client = await get_redis()
    if client is None:
        return False
    ip = await get_client_ip(request)
    key = f"vel:lastip:{user_id}"
    try:
        previous = await client.get(key)
        await client.set(key, ip, ex=60 * 60 * 24 * 30)
        if previous is None:
            return False
        return previous != ip
    except Exception:
        return False


async def evaluate_velocity_anomaly(
    db: AsyncSession,
    user: UserLike,
    request: Request,
    *,
    action: str,
) -> bool:
    """Detect sudden posting/voting bursts on established accounts.

    On trip: quarantines the user (moderator review) and returns True.
    New accounts (under ``VELOCITY_MIN_ACCOUNT_AGE_HOURS``) are skipped — they
    already have tier and rapid-post limits. Fail-open when Redis is down.

    Args:
        db: Database session.
        user: Authenticated actor.
        request: Current HTTP request (for IP shift signal).
        action: ``\"post\"`` or ``\"vote\"``.

    Returns:
        True if the user was quarantined by this check.
    """
    if bool(user.is_quarantined):
        return False
    if _account_age_hours(user) < settings.VELOCITY_MIN_ACCOUNT_AGE_HOURS:
        return False

    user_id = str(user.id)
    if action == "post":
        limit = settings.VELOCITY_POST_BURST_LIMIT
        window = settings.VELOCITY_POST_WINDOW_SECONDS
        key = f"vel:post:{user_id}"
    else:
        limit = settings.VELOCITY_VOTE_BURST_LIMIT
        window = settings.VELOCITY_VOTE_WINDOW_SECONDS
        key = f"vel:vote:{user_id}"

    count = await _incr_burst(key, window)
    if count == 0 or count < limit:
        # Still record IP for future shift detection.
        await _ip_shifted(user_id, request)
        return False

    ip_shift = await _ip_shifted(user_id, request)
    reason = (
        f"velocity_anomaly: {count} {action}s in {window}s "
        f"(limit {limit}" + (", IP changed" if ip_shift else "") + ")"
    )
    db_user = await get_user_by_id(db, user_id)
    if db_user is None:
        return False
    await quarantine_user(
        db,
        db_user,
        reason=reason,
        triggered_by="velocity_anomaly",
    )
    logger.warning(
        "Quarantined user {} for velocity anomaly action={} count={} ip_shift={}",
        user_id,
        action,
        count,
        ip_shift,
    )
    return True
