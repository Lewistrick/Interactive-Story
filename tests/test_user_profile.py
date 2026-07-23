"""Tests for public user profile and authored-parts APIs."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user, get_current_user_optional
from app.db.session import get_db
from app.main import app


def _viewer(*, is_moderator=False):
    """Optional auth fixture."""
    return SimpleNamespace(
        id=uuid4(),
        username="viewer",
        reputation_score=10,
        is_quarantined=False,
        is_moderator=is_moderator,
        is_blocked=False,
    )


def _target_user():
    """Subject of the user profile page."""
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
async def test_public_user_profile_hides_mod_fields():
    """Anonymous profile omits quarantine / vote internals."""
    target = _target_user()
    db = AsyncMock()

    async def override_db():
        yield db

    async def override_viewer():
        return None

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = override_viewer

    with (
        patch("app.api.v1.users.get_user_by_id", AsyncMock(return_value=target)),
        patch(
            "app.api.v1.users.count_authored_parts",
            AsyncMock(return_value=40),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/users/{target.id}")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "chaos_user_03"
    assert body["authored_count"] == 40
    assert body["is_moderator"] is False
    assert body["is_quarantined"] is None
    assert body["votes_cast_count"] is None


@pytest.mark.asyncio
async def test_public_profile_shows_moderator_badge():
    """Anyone can see that a profile belongs to a moderator."""
    target = _target_user()
    target.is_moderator = True
    db = AsyncMock()

    async def override_db():
        yield db

    async def override_viewer():
        return None

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = override_viewer

    with (
        patch("app.api.v1.users.get_user_by_id", AsyncMock(return_value=target)),
        patch(
            "app.api.v1.users.count_authored_parts",
            AsyncMock(return_value=3),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/users/{target.id}")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["is_moderator"] is True


@pytest.mark.asyncio
async def test_moderator_user_profile_includes_status():
    """Moderator viewers receive quarantine and vote counts."""
    viewer = _viewer(is_moderator=True)
    target = _target_user()
    db = AsyncMock()

    async def override_db():
        yield db

    async def override_viewer():
        return viewer

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = override_viewer

    with (
        patch("app.api.v1.users.get_user_by_id", AsyncMock(return_value=target)),
        patch(
            "app.api.v1.users.count_authored_parts",
            AsyncMock(side_effect=[48, 6, 48]),
        ),
        patch(
            "app.api.v1.users.count_votes_by_type",
            AsyncMock(return_value=(180, 132)),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/users/{target.id}")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["is_quarantined"] is True
    assert body["is_moderator"] is False
    assert body["quarantined_parts_count"] == 6
    assert body["votes_cast_count"] == 312


@pytest.mark.asyncio
async def test_public_user_parts_exclude_quarantined():
    """Public parts list excludes quarantined rows by default."""
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

    async def override_viewer():
        return None

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = override_viewer

    with (
        patch("app.api.v1.users.get_user_by_id", AsyncMock(return_value=target)),
        patch(
            "app.api.v1.users.list_authored_parts",
            AsyncMock(return_value=[part]),
        ) as list_parts,
        patch(
            "app.api.v1.users.get_children_count",
            AsyncMock(return_value=0),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/users/{target.id}/parts")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["children_count"] == 0
    assert list_parts.await_args is not None
    assert list_parts.await_args.kwargs["exclude_quarantined"] is True


@pytest.mark.asyncio
async def test_delete_own_leaf_story_part():
    """Authors can hard-delete a leaf part they own."""
    author = _viewer()
    story_id = uuid4()
    parent_id = uuid4()
    story = SimpleNamespace(
        id=story_id,
        author_id=author.id,
        parent_part_id=parent_id,
        is_quarantined=False,
    )
    db = AsyncMock()

    async def override_db():
        yield db

    async def override_user():
        return author

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with (
        patch(
            "app.api.v1.stories.get_story_part_by_id",
            AsyncMock(return_value=story),
        ),
        patch(
            "app.api.v1.stories.get_children_count",
            AsyncMock(return_value=0),
        ),
        patch(
            "app.api.v1.stories.delete_story_part",
            AsyncMock(return_value=parent_id),
        ) as delete_part,
        patch(
            "app.api.v1.stories.update_story_recursive_scores",
            AsyncMock(),
        ),
        patch(
            "app.api.v1.stories.recalculate_user_reputation",
            AsyncMock(),
        ),
        patch(
            "app.api.v1.stories.enforce_user_not_quarantined",
            lambda _u: None,
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/api/v1/stories/{story_id}")

    app.dependency_overrides.clear()
    assert response.status_code == 204
    delete_part.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_story_part_with_children_rejected():
    """Cannot delete a part that still has continuations."""
    author = _viewer()
    story_id = uuid4()
    story = SimpleNamespace(
        id=story_id,
        author_id=author.id,
        parent_part_id=None,
        is_quarantined=False,
    )
    db = AsyncMock()

    async def override_db():
        yield db

    async def override_user():
        return author

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with (
        patch(
            "app.api.v1.stories.get_story_part_by_id",
            AsyncMock(return_value=story),
        ),
        patch(
            "app.api.v1.stories.get_children_count",
            AsyncMock(return_value=2),
        ),
        patch(
            "app.api.v1.stories.enforce_user_not_quarantined",
            lambda _u: None,
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/api/v1/stories/{story_id}")

    app.dependency_overrides.clear()
    assert response.status_code == 400
