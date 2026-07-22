"""Tests for moderator user history profile / parts / votes APIs."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.story_part import VoteType


def _moderator():
    """Moderator auth fixture."""
    return SimpleNamespace(
        id=uuid4(),
        username="mod",
        reputation_score=100,
        is_quarantined=False,
        is_moderator=True,
        is_blocked=False,
    )


def _target_user():
    """Subject of the user-history page."""
    return SimpleNamespace(
        id=uuid4(),
        username="chaos_user_03",
        reputation_score=12,
        is_quarantined=True,
        quarantine_reason="rapid_posting",
        quarantine_until=None,
        is_moderator=False,
        is_blocked=False,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_moderator_user_profile():
    """Profile endpoint returns counts and quarantine status."""
    mod = _moderator()
    target = _target_user()
    db = AsyncMock()

    async def override_db():
        yield db

    async def override_user():
        return mod

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with (
        patch("app.api.v1.moderator.get_user_by_id", AsyncMock(return_value=target)),
        patch(
            "app.api.v1.moderator.count_authored_parts",
            AsyncMock(side_effect=[48, 6]),
        ),
        patch(
            "app.api.v1.moderator.count_votes_by_type",
            AsyncMock(return_value=(180, 132)),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/moderator/users/{target.id}")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "chaos_user_03"
    assert body["authored_count"] == 48
    assert body["quarantined_parts_count"] == 6
    assert body["votes_cast_count"] == 312
    assert body["votes_up_count"] == 180
    assert body["votes_down_count"] == 132
    assert body["is_quarantined"] is True


@pytest.mark.asyncio
async def test_moderator_user_parts_sorted():
    """Parts list returns authored rows."""
    mod = _moderator()
    target = _target_user()
    db = AsyncMock()
    part = SimpleNamespace(
        id=uuid4(),
        teaser="A teaser",
        vote_score=2,
        recursive_score=10,
        depth_level=1,
        is_quarantined=False,
        parent_part_id=None,
        created_at=datetime.now(timezone.utc),
    )

    async def override_db():
        yield db

    async def override_user():
        return mod

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with (
        patch("app.api.v1.moderator.get_user_by_id", AsyncMock(return_value=target)),
        patch(
            "app.api.v1.moderator.list_authored_parts",
            AsyncMock(return_value=[part]),
        ) as list_mock,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/moderator/users/{target.id}/parts",
                params={"sort": "vote_score", "order": "desc", "limit": 5},
            )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["teaser"] == "A teaser"
    assert body[0]["vote_score"] == 2
    list_mock.assert_awaited()
    assert list_mock.await_args is not None
    kwargs = list_mock.await_args.kwargs
    assert kwargs["sort"].value == "vote_score"
    assert kwargs["order"] == "desc"
    assert kwargs["limit"] == 5


@pytest.mark.asyncio
async def test_moderator_user_votes():
    """Votes list includes UP/DOWN and target teaser."""
    mod = _moderator()
    target = _target_user()
    db = AsyncMock()
    part_id = uuid4()
    author = SimpleNamespace(username="other")
    part = SimpleNamespace(
        id=part_id,
        teaser="Voted teaser",
        vote_score=-3,
        recursive_score=-5,
        is_quarantined=False,
        author=author,
    )
    vote = SimpleNamespace(
        id=uuid4(),
        vote_type=VoteType.DOWN,
        created_at=datetime.now(timezone.utc),
        story_part=part,
    )

    async def override_db():
        yield db

    async def override_user():
        return mod

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with (
        patch("app.api.v1.moderator.get_user_by_id", AsyncMock(return_value=target)),
        patch(
            "app.api.v1.moderator.list_votes_cast",
            AsyncMock(return_value=[vote]),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/moderator/users/{target.id}/votes")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["vote_type"] == "DOWN"
    assert body[0]["teaser"] == "Voted teaser"
    assert body[0]["author_username"] == "other"


@pytest.mark.asyncio
async def test_moderator_user_profile_404():
    """Missing user yields 404."""
    mod = _moderator()
    db = AsyncMock()

    async def override_db():
        yield db

    async def override_user():
        return mod

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with patch("app.api.v1.moderator.get_user_by_id", AsyncMock(return_value=None)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/moderator/users/{uuid4()}")

    app.dependency_overrides.clear()
    assert response.status_code == 404
