"""Auth endpoint tests with mocked user CRUD (no real database)."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user
from app.core.security import get_password_hash
from app.db.session import get_db
from app.main import app


def _user(username: str = "alice", password: str = "secret123"):
    return SimpleNamespace(
        id=uuid4(),
        username=username,
        password_hash=get_password_hash(password),
        reputation_score=0,
        is_quarantined=False,
        is_moderator=False,
        is_blocked=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _limits():
    return SimpleNamespace(
        tier_name="Novice",
        max_teaser_length=128,
        max_content_length=512,
        daily_part_limit=2,
        min_parts_between_own=3,
        can_vote_threshold=50,
        can_vote=False,
        parts_written_today=0,
    )


@pytest.fixture
async def client():
    """HTTP client with DB dependency stubbed out."""

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """New users can register."""
    created = _user("newuser")
    with (
        patch("app.api.v1.auth.get_user_by_username", AsyncMock(return_value=None)),
        patch("app.api.v1.auth.create_user", AsyncMock(return_value=created)),
        patch("app.api.v1.auth.get_user_limits", AsyncMock(return_value=_limits())),
    ):
        response = await client.post(
            "/api/v1/auth/register",
            json={"username": "newuser", "password": "secret123"},
        )
    assert response.status_code == 200
    assert response.json()["username"] == "newuser"
    assert response.json()["tier_name"] == "Novice"
    assert response.json()["can_vote"] is False


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient):
    """Duplicate usernames are rejected."""
    existing = _user("taken")
    with patch("app.api.v1.auth.get_user_by_username", AsyncMock(return_value=existing)):
        response = await client.post(
            "/api/v1/auth/register",
            json={"username": "taken", "password": "secret123"},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Valid credentials return a JWT access token."""
    user = _user("alice", "secret123")
    with patch("app.api.v1.auth.authenticate_user", AsyncMock(return_value=user)):
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "secret123"},
        )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid(client: AsyncClient):
    """Bad credentials return 401."""
    with patch("app.api.v1.auth.authenticate_user", AsyncMock(return_value=None)):
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "wrong"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client: AsyncClient):
    """Authenticated /me returns the current user profile with tier limits."""
    user = _user("alice")

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    with patch("app.api.v1.auth.get_user_limits", AsyncMock(return_value=_limits())):
        response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert body["tier_name"] == "Novice"
    assert body["max_teaser_length"] == 128
    assert body["can_vote"] is False
    assert body["parts_written_today"] == 0
