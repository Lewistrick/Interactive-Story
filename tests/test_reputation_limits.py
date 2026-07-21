"""Tests for reputation limit enforcement helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.reputation import (
    check_can_vote,
    check_concurrent_open_trees,
    check_content_length,
    check_daily_limit,
    check_min_reputation_for_root,
    check_sibling_branch_spacing,
    check_spacing_rule,
    enforce_create_limits,
    enforce_vote_limits,
)


def _tier(**overrides):
    base = dict(
        name="Novice",
        max_teaser_length=128,
        max_content_length=512,
        daily_part_limit=2,
        min_parts_between_own=3,
        can_vote_threshold=50,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _user(reputation: int = 0):
    return SimpleNamespace(
        id=uuid4(),
        reputation_score=reputation,
        is_blocked=False,
    )


def test_check_content_length_ok():
    """Content within tier limits passes."""
    check_content_length("short", "also short", _tier())


def test_check_content_length_teaser_too_long():
    """Teaser over the tier max raises 400."""
    with pytest.raises(HTTPException) as exc:
        check_content_length("x" * 129, "ok", _tier())
    assert exc.value.status_code == 400
    assert "Teaser" in exc.value.detail


def test_check_content_length_content_too_long():
    """Body over the tier max raises 400."""
    with pytest.raises(HTTPException) as exc:
        check_content_length("ok", "y" * 513, _tier())
    assert exc.value.status_code == 400
    assert "Content" in exc.value.detail


@pytest.mark.asyncio
async def test_check_daily_limit_allows_under_cap(monkeypatch):
    """Users under the daily cap can post."""
    from app.services import reputation as rep

    async def fake_daily(_db, _uid):
        return SimpleNamespace(parts_written=1)

    monkeypatch.setattr(rep, "get_or_create_daily_limit", fake_daily)
    await check_daily_limit(AsyncMock(), _user(), _tier(daily_part_limit=2))


@pytest.mark.asyncio
async def test_check_daily_limit_blocks_at_cap(monkeypatch):
    """Hitting the daily cap raises 429."""
    from app.services import reputation as rep

    async def fake_daily(_db, _uid):
        return SimpleNamespace(parts_written=2)

    monkeypatch.setattr(rep, "get_or_create_daily_limit", fake_daily)
    with pytest.raises(HTTPException) as exc:
        await check_daily_limit(AsyncMock(), _user(), _tier(daily_part_limit=2))
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_check_spacing_rule_blocks_too_soon(monkeypatch):
    """Same author too close on the ancestor path raises 403."""
    from app.services import reputation as rep

    user = _user()
    parent_id = uuid4()
    own_part = SimpleNamespace(author_id=user.id)
    other = SimpleNamespace(author_id=uuid4())

    async def fake_chain(_db, _start):
        return [other, own_part]

    monkeypatch.setattr(rep, "get_ancestor_chain", fake_chain)
    with pytest.raises(HTTPException) as exc:
        await check_spacing_rule(AsyncMock(), user, parent_id, _tier(min_parts_between_own=3))
    assert exc.value.status_code == 403
    assert "Spacing" in exc.value.detail


@pytest.mark.asyncio
async def test_check_spacing_rule_allows_enough_intervening(monkeypatch):
    """Enough other authors between own parts is allowed."""
    from app.services import reputation as rep

    user = _user()
    others = [SimpleNamespace(author_id=uuid4()) for _ in range(3)]
    own_part = SimpleNamespace(author_id=user.id)

    async def fake_chain(_db, _start):
        return [*others, own_part]

    monkeypatch.setattr(rep, "get_ancestor_chain", fake_chain)
    await check_spacing_rule(AsyncMock(), user, uuid4(), _tier(min_parts_between_own=3))


@pytest.mark.asyncio
async def test_check_spacing_skipped_when_zero(monkeypatch):
    """Master/Legend spacing of 0 skips the check."""
    from app.services import reputation as rep

    called = False

    async def fake_chain(_db, _start):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(rep, "get_ancestor_chain", fake_chain)
    await check_spacing_rule(AsyncMock(), _user(), uuid4(), _tier(min_parts_between_own=0))
    assert called is False


def test_check_can_vote_blocks_below_threshold():
    """Reputation below the tier threshold cannot vote."""
    with pytest.raises(HTTPException) as exc:
        check_can_vote(_user(0), _tier(can_vote_threshold=50))
    assert exc.value.status_code == 403


def test_check_can_vote_allows_novice_with_zero_threshold():
    """Novice threshold of 0 allows voting at reputation 0."""
    check_can_vote(_user(0), _tier(can_vote_threshold=0))


def test_check_can_vote_allows_threshold():
    """Reputation at the threshold can vote."""
    check_can_vote(_user(50), _tier(can_vote_threshold=50))


@pytest.mark.asyncio
async def test_enforce_vote_limits_blocked_user():
    """Blocked accounts cannot vote."""
    user = _user(100)
    user.is_blocked = True
    with pytest.raises(HTTPException) as exc:
        await enforce_vote_limits(AsyncMock(), user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_enforce_create_limits_wires_checks(monkeypatch):
    """enforce_create_limits runs length, daily, and continue-path checks."""
    from app.services import reputation as rep

    tier = _tier()
    calls: list[str] = []

    async def fake_resolve(_db, _score):
        return tier

    async def fake_daily(_db, _user, _tier):
        calls.append("daily")

    async def fake_spacing(_db, _user, _parent, _tier):
        calls.append("spacing")

    async def fake_sibling(_db, _user, _parent):
        calls.append("sibling")

    monkeypatch.setattr(rep, "resolve_tier", fake_resolve)
    monkeypatch.setattr(rep, "check_daily_limit", fake_daily)
    monkeypatch.setattr(rep, "check_spacing_rule", fake_spacing)
    monkeypatch.setattr(rep, "check_sibling_branch_spacing", fake_sibling)

    result = await enforce_create_limits(
        AsyncMock(), _user(), "teaser", "content", parent_id=uuid4()
    )
    assert result is tier
    assert calls == ["daily", "spacing", "sibling"]


@pytest.mark.asyncio
async def test_enforce_create_limits_root_gates(monkeypatch):
    """Root creates run min-reputation and concurrent-tree checks."""
    from app.services import reputation as rep

    tier = _tier()
    calls: list[str] = []

    async def fake_resolve(_db, _score):
        return tier

    async def fake_daily(_db, _user, _tier):
        calls.append("daily")

    def fake_min(user):
        calls.append("min_root")

    async def fake_trees(_db, _user):
        calls.append("trees")

    monkeypatch.setattr(rep, "resolve_tier", fake_resolve)
    monkeypatch.setattr(rep, "check_daily_limit", fake_daily)
    monkeypatch.setattr(rep, "check_min_reputation_for_root", fake_min)
    monkeypatch.setattr(rep, "check_concurrent_open_trees", fake_trees)

    result = await enforce_create_limits(
        AsyncMock(), _user(60), "teaser", "content", parent_id=None
    )
    assert result is tier
    assert calls == ["daily", "min_root", "trees"]


def test_check_min_reputation_for_root_blocks(monkeypatch):
    """Below MIN_REPUTATION_CREATE_ROOT raises 403."""
    from app.services import reputation as rep

    monkeypatch.setattr(rep.settings, "MIN_REPUTATION_CREATE_ROOT", 50)
    with pytest.raises(HTTPException) as exc:
        check_min_reputation_for_root(_user(0))
    assert exc.value.status_code == 403


def test_check_min_reputation_for_root_allows(monkeypatch):
    """At or above the minimum can create roots."""
    from app.services import reputation as rep

    monkeypatch.setattr(rep.settings, "MIN_REPUTATION_CREATE_ROOT", 50)
    check_min_reputation_for_root(_user(50))


@pytest.mark.asyncio
async def test_check_concurrent_open_trees_blocks(monkeypatch):
    """Too many open roots raises 403."""
    from app.services import reputation as rep

    monkeypatch.setattr(rep.settings, "MAX_CONCURRENT_OPEN_TREES", 3)

    async def fake_count(_db, _uid):
        return 3

    monkeypatch.setattr(rep, "count_open_root_stories_by_author", fake_count)
    with pytest.raises(HTTPException) as exc:
        await check_concurrent_open_trees(AsyncMock(), _user())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_check_sibling_branch_spacing_blocks(monkeypatch):
    """A recent sibling branch by the same author raises 429."""
    from datetime import datetime, timedelta, timezone

    from app.services import reputation as rep

    monkeypatch.setattr(rep.settings, "SIBLING_BRANCH_COOLDOWN_SECONDS", 3600)
    user = _user()
    recent = SimpleNamespace(created_at=datetime.now(timezone.utc) - timedelta(seconds=30))

    async def fake_latest(_db, _parent, _author):
        return recent

    monkeypatch.setattr(rep, "get_latest_child_by_author", fake_latest)
    with pytest.raises(HTTPException) as exc:
        await check_sibling_branch_spacing(AsyncMock(), user, uuid4())
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_check_sibling_branch_spacing_allows_after_cooldown(monkeypatch):
    """Branches after the cooldown window are allowed."""
    from datetime import datetime, timedelta, timezone

    from app.services import reputation as rep

    monkeypatch.setattr(rep.settings, "SIBLING_BRANCH_COOLDOWN_SECONDS", 60)
    old = SimpleNamespace(created_at=datetime.now(timezone.utc) - timedelta(seconds=120))

    async def fake_latest(_db, _parent, _author):
        return old

    monkeypatch.setattr(rep, "get_latest_child_by_author", fake_latest)
    await check_sibling_branch_spacing(AsyncMock(), _user(), uuid4())
