"""Redis JSON cache helpers for story trees (fail-open)."""

import json
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis
from app.crud.story import get_story_part_by_id


def tree_cache_key(story_id: str | UUID, *, include_quarantined: bool) -> str:
    """Build the Redis key for a cached story tree."""
    flag = "1" if include_quarantined else "0"
    return f"tree:{story_id}:q{flag}"


def _as_part_id(value: Any) -> str | None:
    """Return a UUID string, or None for missing/mock values."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str):
        try:
            return str(UUID(value))
        except ValueError:
            return None
    return None


async def cache_get_json(key: str) -> Any | None:
    """Return a JSON-decoded value from Redis, or None on miss/error/disabled."""
    if not settings.CACHE_ENABLED:
        return None
    client = await get_redis()
    if client is None:
        return None
    try:
        raw = await client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.warning("Cache get failed for key={}", key)
        return None


async def cache_set_json(key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
    """Store a JSON-encoded value in Redis with TTL."""
    if not settings.CACHE_ENABLED:
        return
    client = await get_redis()
    if client is None:
        return
    ttl = ttl_seconds if ttl_seconds is not None else settings.CACHE_TREE_TTL_SECONDS
    try:
        await client.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        logger.warning("Cache set failed for key={}", key)


async def cache_delete(*keys: str) -> None:
    """Delete one or more cache keys (ignore missing / errors)."""
    if not keys or not settings.CACHE_ENABLED:
        return
    client = await get_redis()
    if client is None:
        return
    try:
        await client.delete(*keys)
    except Exception:
        logger.warning("Cache delete failed for keys={}", keys)


async def invalidate_story_tree_cache(db: AsyncSession, story_id: str | UUID) -> None:
    """Invalidate tree caches for a part and every ancestor (any rooted view).

    Fail-open: if the ancestor walk cannot complete (e.g. Redis or DB issues),
    still attempt to drop keys for the touched id. Only follows real UUID parent
    links so mocked sessions cannot loop forever.
    """
    if not settings.CACHE_ENABLED:
        return
    part_id = str(story_id)
    ids: list[str] = [part_id]
    try:
        current = await get_story_part_by_id(db, part_id)
        depth = 0
        while current is not None and depth < 64:
            depth += 1
            parent_key = _as_part_id(getattr(current, "parent_part_id", None))
            if parent_key is None or parent_key in ids:
                break
            ids.append(parent_key)
            current = await get_story_part_by_id(db, parent_key)
    except Exception:
        logger.warning("Tree cache ancestor walk failed for story_id={}", part_id)

    keys: list[str] = []
    for sid in ids:
        keys.append(tree_cache_key(sid, include_quarantined=False))
        keys.append(tree_cache_key(sid, include_quarantined=True))
    await cache_delete(*keys)
