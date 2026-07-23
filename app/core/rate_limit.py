"""Redis-backed fixed-window rate limiting for write-heavy endpoints."""

from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.redis import get_redis


async def get_client_ip(request: Request) -> str:
    """Best-effort client IP (honours X-Forwarded-For from the proxy)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


async def enforce_rate_limit(
    request: Request,
    *,
    bucket: str,
    limit: int,
    user_id: str | None = None,
) -> None:
    """Increment a Redis counter and raise 429 when the window is exhausted.

    When rate limiting is disabled or Redis is unreachable, the check is
    skipped (fail-open) so local unit tests without Redis still run.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return
    client = await get_redis()
    if client is None:
        return

    ip = await get_client_ip(request)
    identity = f"{ip}:{user_id}" if user_id else ip
    key = f"rl:{bucket}:{identity}"
    window = settings.RATE_LIMIT_WINDOW_SECONDS

    try:
        count = int(await cast("Awaitable[int]", client.incr(key)))
        if count == 1:
            await client.expire(key, window)
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded for {bucket} "
                    f"({limit} requests per {window}s). Try again shortly."
                ),
            )
    except HTTPException:
        raise
    except Exception:
        # Fail open if Redis errors mid-request.
        return


def rate_limit_auth() -> Callable:
    """Dependency: rate-limit unauthenticated auth endpoints by IP."""

    async def _dep(request: Request) -> None:
        await enforce_rate_limit(
            request,
            bucket="auth",
            limit=settings.RATE_LIMIT_AUTH_MAX,
        )

    return _dep


def rate_limit_write() -> Callable:
    """Dependency: rate-limit authenticated write endpoints by IP.

    User id is not required here; callers that already have the user may
    pass a tighter check via ``enforce_rate_limit`` directly.
    """

    async def _dep(request: Request) -> None:
        await enforce_rate_limit(
            request,
            bucket="write",
            limit=settings.RATE_LIMIT_WRITE_MAX,
        )

    return _dep


# Default FastAPI dependencies
RequireAuthRateLimit = Depends(rate_limit_auth())
RequireWriteRateLimit = Depends(rate_limit_write())
