"""Tests for Redis rate limiting and report auto-quarantine API behaviour."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core import rate_limit as rate_limit_mod
from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.quarantine_log import EntityType


class _FakeRedis:
    """In-memory Redis stand-in for rate-limit tests."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, _seconds: int) -> bool:
        return True


@pytest.mark.asyncio
async def test_enforce_rate_limit_raises_429():
    """Exceeding the window limit yields HTTP 429."""
    fake = _FakeRedis()
    request = MagicMock()
    request.headers = {}
    request.client = SimpleNamespace(host="127.0.0.1")

    with patch.object(rate_limit_mod, "get_redis", AsyncMock(return_value=fake)):
        await rate_limit_mod.enforce_rate_limit(request, bucket="auth", limit=2)
        await rate_limit_mod.enforce_rate_limit(request, bucket="auth", limit=2)
        with pytest.raises(HTTPException) as exc:
            await rate_limit_mod.enforce_rate_limit(request, bucket="auth", limit=2)
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_enforce_rate_limit_skips_without_redis():
    """Missing Redis fails open."""
    request = MagicMock()
    request.headers = {}
    request.client = SimpleNamespace(host="127.0.0.1")
    with patch.object(rate_limit_mod, "get_redis", AsyncMock(return_value=None)):
        await rate_limit_mod.enforce_rate_limit(request, bucket="auth", limit=1)
        await rate_limit_mod.enforce_rate_limit(request, bucket="auth", limit=1)


def _make_user(*, is_moderator=False, is_quarantined=False):
    """Auth user fixture."""
    return SimpleNamespace(
        id=uuid4(),
        username="reporter",
        reputation_score=10,
        is_quarantined=is_quarantined,
        is_moderator=is_moderator,
        is_blocked=False,
    )


def _make_story(*, is_quarantined=False):
    """Story part fixture."""
    author = SimpleNamespace(username="author")
    return SimpleNamespace(
        id=uuid4(),
        teaser="T",
        content="C",
        parent_part_id=None,
        author_id=uuid4(),
        vote_score=0,
        recursive_score=0,
        is_quarantined=is_quarantined,
        quarantine_reason=None,
        depth_level=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        author=author,
    )


@pytest.mark.asyncio
async def test_report_auto_quarantines_at_threshold():
    """Third distinct report quarantines the story part."""
    user = _make_user()
    story = _make_story()
    db = AsyncMock()

    report = SimpleNamespace(
        id=uuid4(),
        story_part_id=story.id,
        reporter_id=user.id,
        reason=None,
        created_at=datetime.now(timezone.utc),
    )

    async def override_db():
        yield db

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with (
        patch("app.api.v1.stories.enforce_rate_limit", AsyncMock()),
        patch("app.api.v1.stories.get_story_part_by_id", AsyncMock(return_value=story)),
        patch("app.api.v1.stories.get_user_report", AsyncMock(return_value=None)),
        patch("app.api.v1.stories.create_report", AsyncMock(return_value=report)),
        patch("app.api.v1.stories.count_reports_for_part", AsyncMock(return_value=3)),
        patch(
            "app.api.v1.stories.quarantine_story_part",
            AsyncMock(),
        ) as q,
        patch.object(settings, "QUARANTINE_MIN_REPORTS", 3),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/api/v1/stories/{story.id}/report", json={})

    app.dependency_overrides.clear()
    assert response.status_code == 201
    body = response.json()
    assert body["quarantined"] is True
    assert body["report_count"] == 3
    q.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_quarantined_story_404_for_public():
    """Quarantined parts are hidden from anonymous readers."""
    story = _make_story(is_quarantined=True)
    db = AsyncMock()

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db

    with patch("app.api.v1.stories.get_story_part_by_id", AsyncMock(return_value=story)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/stories/{story.id}")

    app.dependency_overrides.clear()
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_moderator_queue_requires_moderator():
    """Non-moderators cannot access the quarantine queue."""
    user = _make_user(is_moderator=False)
    db = AsyncMock()

    async def override_db():
        yield db

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/moderator/quarantine-queue")

    app.dependency_overrides.clear()
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_moderator_queue_ok_for_moderator():
    """Moderators receive the open quarantine queue."""
    user = _make_user(is_moderator=True)
    db = AsyncMock()
    log = SimpleNamespace(
        id=uuid4(),
        entity_type=EntityType.STORY_PART,
        entity_id=uuid4(),
        reason="test",
        triggered_by="unit",
        automatic=True,
        resolved_by_moderator_id=None,
        resolution_action=None,
        resolved_at=None,
        created_at=datetime.now(timezone.utc),
    )

    async def override_db():
        yield db

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    story = SimpleNamespace(
        teaser="A quarantined teaser",
        content="Body text that should appear in the queue preview.",
        author=SimpleNamespace(username="alice"),
        author_id=uuid4(),
    )

    with (
        patch(
            "app.api.v1.moderator.list_open_quarantine_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "app.api.v1.moderator.get_story_part_by_id",
            AsyncMock(return_value=story),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/moderator/quarantine-queue")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["reason"] == "test"
    assert body[0]["author_username"] == "alice"
    assert body[0]["teaser"] == "A quarantined teaser"
    assert "Body text" in body[0]["content_preview"]
