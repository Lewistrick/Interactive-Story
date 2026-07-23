"""Unit tests for root list sorting and empty search."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.crud import story as story_crud


@pytest.mark.asyncio
async def test_get_root_stories_popular_orders_by_recursive_score():
    """Popular sort uses recursive_score then created_at."""
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result)

    await story_crud.get_root_stories(db, skip=0, limit=10, sort="popular")

    db.execute.assert_awaited_once()
    compiled = str(db.execute.await_args.args[0])
    assert "recursive_score" in compiled.lower()


@pytest.mark.asyncio
async def test_get_root_stories_latest_orders_by_created_at():
    """Latest sort orders by created_at only."""
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result)

    await story_crud.get_root_stories(db, skip=0, limit=10, sort="latest")

    db.execute.assert_awaited_once()
    compiled = str(db.execute.await_args.args[0])
    assert "created_at" in compiled.lower()


@pytest.mark.asyncio
async def test_search_story_parts_empty_query_returns_empty():
    """Blank search queries short-circuit without hitting the DB."""
    db = AsyncMock()
    rows = await story_crud.search_story_parts(db, "   ")
    assert rows == []
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_story_parts_builds_tsquery():
    """Non-empty search issues a database query."""
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result)

    await story_crud.search_story_parts(db, "ancient forest", skip=0, limit=5)
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_root_stories_popular_now_uses_activity_helper():
    """popular_now delegates to the recent-activity listing helper."""
    db = AsyncMock()
    with patch.object(
        story_crud, "_get_root_stories_by_recent_activity", AsyncMock(return_value=[])
    ) as helper:
        await story_crud.get_root_stories(db, skip=0, limit=10, sort="popular_now")
    helper.assert_awaited_once()
