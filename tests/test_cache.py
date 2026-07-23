"""Unit tests for Redis JSON tree cache helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core import cache as cache_mod


@pytest.mark.asyncio
async def test_cache_get_json_disabled(monkeypatch):
    """Disabled cache never hits Redis."""
    monkeypatch.setattr(cache_mod.settings, "CACHE_ENABLED", False)
    with patch.object(cache_mod, "get_redis", AsyncMock()) as redis:
        assert await cache_mod.cache_get_json("tree:x:q0") is None
    redis.assert_not_awaited()


@pytest.mark.asyncio
async def test_cache_round_trip(monkeypatch):
    """Values are JSON-encoded on set and decoded on get."""
    monkeypatch.setattr(cache_mod.settings, "CACHE_ENABLED", True)
    monkeypatch.setattr(cache_mod.settings, "CACHE_TREE_TTL_SECONDS", 30)
    store: dict[str, str] = {}

    class _FakeRedis:
        async def get(self, key: str):
            return store.get(key)

        async def set(self, key: str, value: str, ex: int | None = None):
            del ex
            store[key] = value

        async def delete(self, *keys: str):
            for key in keys:
                store.pop(key, None)

    with patch.object(cache_mod, "get_redis", AsyncMock(return_value=_FakeRedis())):
        await cache_mod.cache_set_json("tree:1:q0", {"id": "abc"})
        assert await cache_mod.cache_get_json("tree:1:q0") == {"id": "abc"}
        await cache_mod.cache_delete("tree:1:q0")
        assert await cache_mod.cache_get_json("tree:1:q0") is None


@pytest.mark.asyncio
async def test_invalidate_walks_ancestors(monkeypatch):
    """Invalidation deletes cache keys for the part and parents."""
    monkeypatch.setattr(cache_mod.settings, "CACHE_ENABLED", True)
    child_id = uuid4()
    parent_id = uuid4()
    root_id = uuid4()
    child = SimpleNamespace(id=child_id, parent_part_id=parent_id)
    parent = SimpleNamespace(id=parent_id, parent_part_id=root_id)
    root = SimpleNamespace(id=root_id, parent_part_id=None)

    async def _get(_db, sid: str):
        mapping = {str(child_id): child, str(parent_id): parent, str(root_id): root}
        return mapping.get(sid)

    deleted: list[str] = []

    async def _delete(*keys: str) -> None:
        deleted.extend(keys)

    with (
        patch.object(cache_mod, "get_story_part_by_id", side_effect=_get),
        patch.object(cache_mod, "cache_delete", side_effect=_delete),
    ):
        await cache_mod.invalidate_story_tree_cache(AsyncMock(), child_id)

    assert cache_mod.tree_cache_key(child_id, include_quarantined=False) in deleted
    assert cache_mod.tree_cache_key(parent_id, include_quarantined=True) in deleted
    assert cache_mod.tree_cache_key(root_id, include_quarantined=False) in deleted
