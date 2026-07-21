"""Async Redis client shared by rate limiting."""

import redis.asyncio as redis

from app.core.config import settings

_client: redis.Redis | None = None


async def get_redis() -> redis.Redis | None:
    """Return a shared async Redis client, or None if unavailable/disabled."""
    global _client
    if not settings.RATE_LIMIT_ENABLED:
        return None
    if _client is not None:
        return _client
    try:
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        _client = client
        return _client
    except Exception:
        return None


async def close_redis() -> None:
    """Close the shared Redis client (app shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
