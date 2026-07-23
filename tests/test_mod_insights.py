"""Unit tests for moderator voting-pattern and reputation insights."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services import mod_insights
from app.services.mod_insights import pattern_severity


def test_pattern_severity_ranks_heavy_downvoter_above_vote_only():
    """Heavy downvoters outrank rings; rings outrank low-volume vote-only."""
    vote_only_two = pattern_severity(flag="vote_only", metric=2)
    ring = pattern_severity(flag="voting_ring", metric=5)
    heavy = pattern_severity(flag="heavy_downvoter", metric=15)
    assert heavy > ring > vote_only_two
    assert vote_only_two == 2
    assert pattern_severity(flag="vote_only", metric=50) > vote_only_two


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


@pytest.mark.asyncio
async def test_list_voting_pattern_flags_skips_dismissed_and_sorts():
    """Dismissed flags are omitted; remaining flags sort by severity desc."""
    heavy_user = MagicMock(
        id=uuid4(),
        username="heavy",
        reputation_score=3,
        is_blocked=False,
    )
    vote_only_user = MagicMock(
        id=uuid4(),
        username="voter",
        reputation_score=10,
        is_blocked=False,
    )

    down_result = MagicMock()
    down_result.all.return_value = [(heavy_user, 20)]
    vote_only_result = MagicMock()
    vote_only_result.all.return_value = [(vote_only_user, 2)]

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[down_result, vote_only_result])

    with (
        patch.object(mod_insights.settings, "VOTING_PATTERN_LOOKBACK_HOURS", 24.0),
        patch.object(mod_insights.settings, "VOTING_PATTERN_DOWNVOTE_THRESHOLD", 15),
        patch(
            "app.services.mod_insights.get_active_dismissal_keys",
            AsyncMock(return_value={(heavy_user.id, "heavy_downvoter")}),
        ),
        patch.object(mod_insights, "_flag_voting_rings", AsyncMock(return_value=[])),
    ):
        flags = await mod_insights.list_voting_pattern_flags(db, limit=20)

    assert len(flags) == 1
    assert flags[0]["flag"] == "vote_only"
    assert flags[0]["severity"] == 2
    assert flags[0]["metric"] == 2


@pytest.mark.asyncio
async def test_flag_voting_rings_detects_shared_targets(monkeypatch):
    """Users sharing enough same-type votes on the same parts are flagged."""
    monkeypatch.setattr(mod_insights.settings, "VOTING_RING_MIN_SHARED_TARGETS", 2)
    monkeypatch.setattr(mod_insights.settings, "VOTING_PATTERN_LOOKBACK_HOURS", 24.0)
    monkeypatch.setattr(mod_insights.settings, "VOTING_RING_MAX_VOTES_SCAN", 1000)

    u1 = uuid4()
    u2 = uuid4()
    p1, p2 = uuid4(), uuid4()
    vote_rows = [
        (u1, p1, "DOWN"),
        (u2, p1, "DOWN"),
        (u1, p2, "DOWN"),
        (u2, p2, "DOWN"),
    ]
    votes_result = MagicMock()
    votes_result.all.return_value = vote_rows

    user_a = MagicMock(id=u1, username="alice", reputation_score=1, is_blocked=False)
    user_b = MagicMock(id=u2, username="bob", reputation_score=2, is_blocked=False)
    users_result = MagicMock()
    users_result.scalars.return_value.all.return_value = [user_a, user_b]

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[votes_result, users_result])

    flags = await mod_insights._flag_voting_rings(
        db,
        since=datetime(2026, 1, 1, tzinfo=timezone.utc),
        dismissed=set(),
        already_flagged=set(),
    )
    assert len(flags) == 2
    assert {f["flag"] for f in flags} == {"voting_ring"}
    assert all(f["metric"] == 2 for f in flags)
