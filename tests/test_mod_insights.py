"""Unit tests for moderator voting-pattern and reputation insights."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services import mod_insights
from app.services.mod_insights import pattern_severity


def test_pattern_severity_ranks_heavy_downvoter_above_vote_only():
    """Heavy downvoters outrank low-volume vote-only accounts."""
    vote_only_two = pattern_severity(flag="vote_only", metric=2)
    heavy = pattern_severity(flag="heavy_downvoter", metric=15)
    assert heavy > vote_only_two
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
    ):
        flags = await mod_insights.list_voting_pattern_flags(db, limit=20)

    assert len(flags) == 1
    assert flags[0]["flag"] == "vote_only"
    assert flags[0]["severity"] == 2
    assert flags[0]["metric"] == 2
