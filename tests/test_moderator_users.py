"""Unit tests for moderator users-by-activity listing."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user
from app.db.session import get_db
from app.main import app


def _mod():
    return SimpleNamespace(
        id=uuid4(),
        username="mod",
        reputation_score=100,
        is_quarantined=False,
        is_moderator=True,
        is_blocked=False,
        must_reset_password=False,
        token_version=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
async def mod_client():
    """Authenticated moderator client."""
    mod = _mod()

    async def override_db():
        yield AsyncMock()

    async def override_user():
        return mod

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_users_by_activity(mod_client: AsyncClient):
    """Moderator users endpoint returns activity-sorted summaries."""
    user = SimpleNamespace(
        id=uuid4(),
        username="alice",
        reputation_score=12,
        is_quarantined=False,
        is_blocked=False,
        is_moderator=False,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    activity = datetime(2026, 7, 1, tzinfo=timezone.utc)
    with patch(
        "app.api.v1.moderator.list_users_by_latest_activity",
        AsyncMock(return_value=[{"user": user, "last_activity_at": activity}]),
    ):
        response = await mod_client.get("/api/v1/moderator/users")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["username"] == "alice"
    assert body[0]["last_activity_at"].startswith("2026-07-01")
