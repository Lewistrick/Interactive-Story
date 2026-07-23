"""Hacked-account heuristics: sudden action bursts, IP and device fingerprint shifts."""

from collections.abc import Awaitable
from datetime import datetime, timezone
from typing import Any, Protocol, cast

from fastapi import Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import get_client_ip
from app.core.redis import get_redis
from app.crud.user import get_user_by_id
from app.services.account_security import force_password_reset
from app.services.quarantine import quarantine_user

DEVICE_FINGERPRINT_HEADER = "X-Device-Fingerprint"


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


def get_device_fingerprint(request: Request) -> str | None:
    """Return a non-empty client device fingerprint header, if present."""
    raw = request.headers.get(DEVICE_FINGERPRINT_HEADER)
    if raw is None:
        return None
    value = raw.strip()
    if not value or len(value) > 128:
        return None
    return value


async def _incr_burst(key: str, window_seconds: int) -> int:
    """Increment a Redis fixed-window counter; return the new count (0 if Redis down)."""
    client = await get_redis()
    if client is None:
        return 0
    try:
        count = int(await cast(Awaitable[int], client.incr(key)))
        if count == 1:
            await client.expire(key, window_seconds)
        return count
    except Exception:
        logger.warning("Velocity counter failed for key={}", key)
        return 0


async def _track_shift(key: str, value: str | None) -> bool:
    """Record ``value`` under ``key``; return True when it differs from the prior value."""
    if not value:
        return False
    client = await get_redis()
    if client is None:
        return False
    try:
        previous = await client.get(key)
        await client.set(key, value, ex=60 * 60 * 24 * 30)
        if previous is None:
            return False
        return previous != value
    except Exception:
        return False


async def _ip_shifted(user_id: str, request: Request) -> bool:
    """Return True if this request IP differs from the last recorded IP for the user."""
    ip = await get_client_ip(request)
    return await _track_shift(f"vel:lastip:{user_id}", ip)


async def _fingerprint_shifted(user_id: str, request: Request) -> bool:
    """Return True if the device fingerprint differs from the last recorded one."""
    fingerprint = get_device_fingerprint(request)
    return await _track_shift(f"vel:lastfp:{user_id}", fingerprint)


async def evaluate_velocity_anomaly(
    db: AsyncSession,
    user: UserLike,
    request: Request,
    *,
    action: str,
) -> bool:
    """Detect sudden posting/voting bursts on established accounts.

    On trip: quarantines the user (moderator review) and returns True.
    When the burst coincides with an IP or device-fingerprint shift, also forces
    a password reset (invalidates JWTs). New accounts (under
    ``VELOCITY_MIN_ACCOUNT_AGE_HOURS``) are skipped — they already have tier and
    rapid-post limits. Fail-open when Redis is down.

    Args:
        db: Database session.
        user: Authenticated actor.
        request: Current HTTP request (for IP / fingerprint shift signals).
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
        # Still record IP / fingerprint for future shift detection.
        await _ip_shifted(user_id, request)
        await _fingerprint_shifted(user_id, request)
        return False

    ip_shift = await _ip_shifted(user_id, request)
    fp_shift = await _fingerprint_shifted(user_id, request)
    extras: list[str] = []
    if ip_shift:
        extras.append("IP changed")
    if fp_shift:
        extras.append("device fingerprint changed")
    extra_note = f", {', '.join(extras)}" if extras else ""
    reason = f"velocity_anomaly: {count} {action}s in {window}s (limit {limit}{extra_note})"
    db_user = await get_user_by_id(db, user_id)
    if db_user is None:
        return False
    await quarantine_user(
        db,
        db_user,
        reason=reason,
        triggered_by="velocity_anomaly",
    )
    if ip_shift or fp_shift:
        await db.refresh(db_user)
        await force_password_reset(db, db_user)
    logger.warning(
        "Quarantined user {} for velocity anomaly action={} count={} ip_shift={} fp_shift={}",
        user_id,
        action,
        count,
        ip_shift,
        fp_shift,
    )
    return True
