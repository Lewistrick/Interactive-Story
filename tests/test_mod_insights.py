"""Unit tests for moderator voting-pattern and reputation insights."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services import mod_insights


@pytest.mark.asyncio
async def test_get_reputation_history_orders_oldest_first():
    """Snapshots are returned oldest → newest for charting."""
    user_id = uuid4()
    older = MagicMock(score=1, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    newer = MagicMock(score=5, created_at=datetime(2026, 1, 2, tzinfo=timezone.utc))

    result = MagicMock()
    result.scalars.return_value.all.return_value = [newer, older]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    rows = await mod_insights.get_reputation_history(db, user_id, limit=10)
    assert [r["score"] for r in rows] == [1, 5]
