"""FastAPI story endpoint tests with mocked CRUD (no real database)."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user, get_current_user_optional
from app.db.session import get_db
from app.main import app
from app.models.story_part import VoteType
from app.schemas.story import StoryPartTree


def _user():
    return SimpleNamespace(
        id=uuid4(),
        username="tester",
        reputation_score=0,
        is_quarantined=False,
        is_moderator=False,
        is_blocked=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _story(*, story_id=None, parent_id=None, depth=0, vote_score=0, children_count=0):
    sid = story_id or uuid4()
    author_id = uuid4()
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=sid,
        teaser="A teaser",
        content="Story content here.",
        parent_part_id=parent_id,
        author_id=author_id,
        vote_score=vote_score,
        recursive_score=0,
        is_quarantined=False,
        quarantine_reason=None,
        depth_level=depth,
        created_at=now,
        updated_at=now,
        author=SimpleNamespace(username="author"),
        children_count=children_count,
    )


@pytest.fixture
async def client():
    """HTTP client with DB dependency stubbed out."""
    user = _user()

    async def override_db():
        yield AsyncMock()

    async def override_user():
        return user

    async def override_user_optional():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_current_user_optional] = override_user_optional

    rate_patch = patch("app.api.v1.stories.enforce_rate_limit", AsyncMock())
    rapid_patch = patch("app.api.v1.stories.evaluate_rapid_posting_quarantine", AsyncMock())
    content_patch = patch(
        "app.api.v1.stories.validate_story_content",
        AsyncMock(return_value=SimpleNamespace(spam_confidence=0.0, should_quarantine=False)),
    )
    velocity_patch = patch(
        "app.api.v1.stories.evaluate_velocity_anomaly",
        AsyncMock(return_value=False),
    )
    invalidate_patch = patch("app.api.v1.stories.invalidate_story_tree_cache", AsyncMock())
    cache_get_patch = patch("app.api.v1.stories.cache_get_json", AsyncMock(return_value=None))
    cache_set_patch = patch("app.api.v1.stories.cache_set_json", AsyncMock())
    rate_patch.start()
    rapid_patch.start()
    content_patch.start()
    velocity_patch.start()
    invalidate_patch.start()
    cache_get_patch.start()
    cache_set_patch.start()

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            setattr(ac, "user", user)
            yield ac
    finally:
        rate_patch.stop()
        rapid_patch.stop()
        content_patch.stop()
        velocity_patch.stop()
        invalidate_patch.stop()
        cache_get_patch.stop()
        cache_set_patch.stop()
        app.dependency_overrides.clear()


@pytest.fixture
async def anon_client():
    """HTTP client without an authenticated user."""

    async def override_db():
        yield AsyncMock()

    async def override_user_optional():
        return None

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_optional] = override_user_optional

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_root_stories_empty(client: AsyncClient):
    """Empty list when CRUD returns no roots."""
    with (
        patch("app.api.v1.stories.get_root_stories", AsyncMock(return_value=[])),
    ):
        response = await client.get("/api/v1/stories/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_root_stories_returns_items(client: AsyncClient):
    """Listed stories include author and children_count."""
    story = _story()
    with (
        patch("app.api.v1.stories.get_root_stories", AsyncMock(return_value=[story])),
        patch("app.api.v1.stories.get_children_count", AsyncMock(return_value=2)),
    ):
        response = await client.get("/api/v1/stories/")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(story.id)
    assert body[0]["children_count"] == 2
    assert body[0]["author_username"] == "author"


@pytest.mark.asyncio
async def test_list_root_stories_passes_popular_sort(client: AsyncClient):
    """Popular sort is forwarded to CRUD."""
    with patch("app.api.v1.stories.get_root_stories", AsyncMock(return_value=[])) as get_roots:
        response = await client.get("/api/v1/stories/", params={"sort": "popular"})
    assert response.status_code == 200
    get_roots.assert_awaited_once()
    assert get_roots.await_args is not None
    assert get_roots.await_args.kwargs.get("sort") == "popular"


@pytest.mark.asyncio
async def test_search_stories_returns_matches(client: AsyncClient):
    """Search endpoint returns matched parts as list rows."""
    story = _story()
    with (
        patch("app.api.v1.stories.search_story_parts", AsyncMock(return_value=[story])),
        patch("app.api.v1.stories.get_children_count", AsyncMock(return_value=1)),
    ):
        response = await client.get("/api/v1/stories/search", params={"q": "forest"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["teaser"] == "A teaser"


@pytest.mark.asyncio
async def test_get_story_not_found(client: AsyncClient):
    """Missing story returns 404."""
    with patch("app.api.v1.stories.get_story_part_by_id", AsyncMock(return_value=None)):
        response = await client.get(f"/api/v1/stories/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_story_includes_user_vote(client: AsyncClient):
    """Authenticated GET includes the caller's vote."""
    story = _story(vote_score=3)
    existing_vote = SimpleNamespace(vote_type=VoteType.UP)
    with (
        patch("app.api.v1.stories.get_story_part_by_id", AsyncMock(return_value=story)),
        patch("app.api.v1.stories.get_children_count", AsyncMock(return_value=0)),
        patch("app.api.v1.stories.get_user_vote", AsyncMock(return_value=existing_vote)),
    ):
        response = await client.get(f"/api/v1/stories/{story.id}")
    assert response.status_code == 200
    assert response.json()["user_vote"] == "UP"
    assert response.json()["vote_score"] == 3


@pytest.mark.asyncio
async def test_create_root_requires_auth(anon_client: AsyncClient):
    """Unauthenticated create is rejected."""
    response = await anon_client.post(
        "/api/v1/stories/",
        json={"teaser": "Nope", "content": "Should fail auth."},
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_root_story(client: AsyncClient):
    """Authenticated create returns 201 with depth 0."""
    created = _story()
    with (
        patch("app.api.v1.stories.enforce_create_limits", AsyncMock()),
        patch("app.api.v1.stories.record_part_created", AsyncMock()),
        patch("app.api.v1.stories.create_story_part", AsyncMock(return_value=created)),
        patch("app.api.v1.stories.get_story_part_by_id", AsyncMock(return_value=created)),
        patch("app.api.v1.stories.get_children_count", AsyncMock(return_value=0)),
    ):
        response = await client.post(
            "/api/v1/stories/",
            json={"teaser": "Hello", "content": "Once upon a time..."},
        )
    assert response.status_code == 201
    assert response.json()["id"] == str(created.id)
    assert response.json()["depth_level"] == 0


@pytest.mark.asyncio
async def test_create_root_rejects_when_limits_fail(client: AsyncClient):
    """Limit enforcement failures surface as the raised HTTP status."""
    with patch(
        "app.api.v1.stories.enforce_create_limits",
        AsyncMock(side_effect=HTTPException(status_code=429, detail="Daily part limit reached")),
    ):
        response = await client.post(
            "/api/v1/stories/",
            json={"teaser": "Hello", "content": "Once upon a time..."},
        )
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_continue_missing_parent(client: AsyncClient):
    """Continue on unknown parent returns 404."""
    with patch("app.api.v1.stories.get_story_part_by_id", AsyncMock(return_value=None)):
        response = await client.post(
            f"/api/v1/stories/{uuid4()}/continue",
            json={"teaser": "Branch", "content": "Goes nowhere."},
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_story_tree_endpoint(client: AsyncClient):
    """Tree endpoint returns nested StoryPartTree payload."""
    root_id = uuid4()
    child_id = uuid4()
    now = datetime.now(timezone.utc)
    author_id = uuid4()
    tree = StoryPartTree(
        id=root_id,
        teaser="Root",
        content="Root content",
        parent_part_id=None,
        author_id=author_id,
        vote_score=0,
        recursive_score=0,
        is_quarantined=False,
        depth_level=0,
        created_at=now,
        updated_at=now,
        author_username="author",
        children_count=1,
        children=[
            StoryPartTree(
                id=child_id,
                teaser="Child",
                content="Child content",
                parent_part_id=root_id,
                author_id=author_id,
                vote_score=0,
                recursive_score=0,
                is_quarantined=False,
                depth_level=1,
                created_at=now,
                updated_at=now,
                author_username="author",
                children_count=0,
                children=[],
            )
        ],
    )
    with (
        patch(
            "app.api.v1.stories.get_story_part_by_id",
            AsyncMock(
                return_value=SimpleNamespace(
                    id=root_id,
                    is_quarantined=False,
                    quarantine_reason=None,
                )
            ),
        ),
        patch("app.api.v1.stories.build_story_tree", AsyncMock(return_value=tree)),
    ):
        response = await client.get(f"/api/v1/stories/{root_id}/tree")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(root_id)
    assert len(data["children"]) == 1
    assert data["children"][0]["id"] == str(child_id)


@pytest.mark.asyncio
async def test_vote_toggle_removes_same_vote(client: AsyncClient):
    """Posting the same vote type again removes it (no vote gate)."""
    story = _story(vote_score=1)
    existing = SimpleNamespace(vote_type=VoteType.UP, story_part_id=story.id)
    updated_story = _story(story_id=story.id, vote_score=0)

    with (
        patch(
            "app.api.v1.stories.get_story_part_by_id",
            AsyncMock(side_effect=[story, updated_story]),
        ),
        patch("app.api.v1.stories.get_user_vote", AsyncMock(return_value=existing)),
        patch("app.api.v1.stories.delete_vote", AsyncMock()),
    ):
        response = await client.post(
            f"/api/v1/stories/{story.id}/vote",
            json={"vote_type": "UP"},
        )
    assert response.status_code == 200
    assert response.json()["removed"] is True
    assert response.json()["vote_score"] == 0


@pytest.mark.asyncio
async def test_vote_create_new(client: AsyncClient):
    """First vote creates an upvote and returns score 1."""
    story = _story(vote_score=0)
    after = _story(story_id=story.id, vote_score=1)
    user_id = getattr(client, "user").id
    new_vote = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        story_part_id=story.id,
        vote_type=VoteType.UP,
        created_at=datetime.now(timezone.utc),
    )
    with (
        patch("app.api.v1.stories.enforce_vote_limits", AsyncMock()),
        patch(
            "app.api.v1.stories.get_story_part_by_id",
            AsyncMock(side_effect=[story, after]),
        ),
        patch("app.api.v1.stories.get_user_vote", AsyncMock(return_value=None)),
        patch("app.api.v1.stories.create_vote", AsyncMock(return_value=new_vote)),
    ):
        response = await client.post(
            f"/api/v1/stories/{story.id}/vote",
            json={"vote_type": "UP"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["removed"] is False
    assert body["vote_type"] == "UP"
    assert body["vote_score"] == 1


@pytest.mark.asyncio
async def test_vote_rejected_by_reputation_gate(client: AsyncClient):
    """Users below the vote threshold receive 403."""
    story = _story()
    with (
        patch(
            "app.api.v1.stories.get_story_part_by_id",
            AsyncMock(return_value=story),
        ),
        patch("app.api.v1.stories.get_user_vote", AsyncMock(return_value=None)),
        patch(
            "app.api.v1.stories.enforce_vote_limits",
            AsyncMock(
                side_effect=HTTPException(status_code=403, detail="below the voting threshold")
            ),
        ),
    ):
        response = await client.post(
            f"/api/v1/stories/{story.id}/vote",
            json={"vote_type": "UP"},
        )
    assert response.status_code == 403
