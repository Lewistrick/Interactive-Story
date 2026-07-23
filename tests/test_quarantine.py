"""Unit tests for quarantine apply/lift and automatic triggers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.quarantine_log import EntityType, ResolutionAction
from app.services import quarantine as quarantine_svc


def _story(**kwargs):
    """Build a lightweight story-like object."""
    defaults = {
        "id": uuid4(),
        "vote_score": 0,
        "is_quarantined": False,
        "quarantine_reason": None,
        "quarantined_at": None,
        "author_id": uuid4(),
    }
    return SimpleNamespace(**(defaults | kwargs))


def _user(**kwargs):
    """Build a lightweight user-like object."""
    defaults = {
        "id": uuid4(),
        "reputation_score": 0,
        "is_quarantined": False,
        "quarantine_reason": None,
        "quarantined_at": None,
        "is_blocked": False,
        "is_moderator": False,
    }
    return SimpleNamespace(**(defaults | kwargs))


def _db() -> AsyncMock:
    """Async session mock."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


def test_assert_story_visible_hides_from_public():
    """Non-moderators cannot see quarantined parts."""
    story = _story(is_quarantined=True)
    with pytest.raises(HTTPException) as exc:
        quarantine_svc.assert_story_visible(story, viewer=None)
    assert exc.value.status_code == 404


def test_assert_story_visible_allows_moderator():
    """Moderators can view quarantined parts."""
    story = _story(is_quarantined=True)
    mod = _user(is_moderator=True)
    quarantine_svc.assert_story_visible(story, viewer=mod)


def test_enforce_user_not_quarantined():
    """Quarantined users cannot write or vote."""
    with pytest.raises(HTTPException) as exc:
        quarantine_svc.enforce_user_not_quarantined(_user(is_quarantined=True))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_quarantine_story_part_writes_log():
    """Quarantining a part sets flags and adds a log."""
    db = _db()
    story = _story()
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=empty)

    log = await quarantine_svc.quarantine_story_part(
        db,
        story,
        reason="test",
        triggered_by="unit_test",
    )

    assert story.is_quarantined is True
    assert story.quarantine_reason == "test"
    db.add.assert_called()
    db.commit.assert_awaited()
    assert log.entity_type == EntityType.STORY_PART
    assert log.automatic is True


@pytest.mark.asyncio
async def test_evaluate_story_score_quarantine_triggers():
    """Score at or below threshold quarantines the part."""
    db = _db()
    story = _story(vote_score=-5)
    with (
        patch.object(quarantine_svc, "get_story_part_by_id", AsyncMock(return_value=story)),
        patch.object(
            quarantine_svc,
            "quarantine_story_part",
            AsyncMock(return_value=MagicMock()),
        ) as q,
        patch.object(quarantine_svc.settings, "QUARANTINE_STORY_SCORE_THRESHOLD", -5),
    ):
        await quarantine_svc.evaluate_story_score_quarantine(db, str(story.id))
    q.assert_awaited_once()


@pytest.mark.asyncio
async def test_evaluate_story_score_skips_above_threshold():
    """Positive scores do not quarantine."""
    db = _db()
    story = _story(vote_score=2)
    with (
        patch.object(quarantine_svc, "get_story_part_by_id", AsyncMock(return_value=story)),
        patch.object(quarantine_svc, "quarantine_story_part", AsyncMock()) as q,
        patch.object(quarantine_svc.settings, "QUARANTINE_STORY_SCORE_THRESHOLD", -5),
    ):
        await quarantine_svc.evaluate_story_score_quarantine(db, str(story.id))
    q.assert_not_awaited()


@pytest.mark.asyncio
async def test_lift_quarantine_resolves_as_allowed():
    """Allow lifts quarantine and marks the log ALLOWED."""
    db = _db()
    story = _story(is_quarantined=True, quarantine_reason="x")
    open_log = SimpleNamespace(
        resolved_by_moderator_id=None,
        resolution_action=None,
        resolved_at=None,
    )
    mod_id = uuid4()

    with (
        patch.object(quarantine_svc, "get_story_part_by_id", AsyncMock(return_value=story)),
        patch.object(quarantine_svc, "_open_log", AsyncMock(return_value=open_log)),
    ):
        log = await quarantine_svc.lift_quarantine(
            db,
            entity_type=EntityType.STORY_PART,
            entity_id=story.id,
            moderator_id=mod_id,
        )

    assert story.is_quarantined is False
    assert log.resolution_action == ResolutionAction.ALLOWED
    assert log.resolved_by_moderator_id == mod_id


@pytest.mark.asyncio
async def test_mark_story_removed_keeps_quarantined():
    """Remove soft-hides the part without clearing quarantine."""
    db = _db()
    story = _story(is_quarantined=True)
    open_log = SimpleNamespace(
        resolved_by_moderator_id=None,
        resolution_action=None,
        resolved_at=None,
    )
    mod_id = uuid4()

    with patch.object(quarantine_svc, "_open_log", AsyncMock(return_value=open_log)):
        log = await quarantine_svc.mark_story_removed(db, story, moderator_id=mod_id)

    assert story.is_quarantined is True
    assert log.resolution_action == ResolutionAction.REMOVED


@pytest.mark.asyncio
async def test_evaluate_rapid_posting_quarantine():
    """Too many recent parts quarantine the user."""
    db = _db()
    user = _user()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=count_result)

    with (
        patch.object(quarantine_svc, "get_user_by_id", AsyncMock(return_value=user)),
        patch.object(quarantine_svc, "quarantine_user", AsyncMock()) as q,
        patch.object(quarantine_svc.settings, "QUARANTINE_RAPID_POSTING_COUNT", 5),
        patch.object(quarantine_svc.settings, "RAPID_POSTING_MIN_HOURS", 1.0),
    ):
        await quarantine_svc.evaluate_rapid_posting_quarantine(db, str(user.id))
    q.assert_awaited_once()


@pytest.mark.asyncio
async def test_block_user_quarantines_parts():
    """Blocking a user flags the account and authored parts."""
    db = _db()
    user = _user()
    part = _story(author_id=user.id, is_quarantined=False)
    parts_result = MagicMock()
    parts_result.scalars.return_value.all.return_value = [part]
    db.execute = AsyncMock(return_value=parts_result)
    open_log = SimpleNamespace(
        resolved_by_moderator_id=None,
        resolution_action=None,
        resolved_at=None,
    )
    mod_id = uuid4()

    with patch.object(quarantine_svc, "_open_log", AsyncMock(return_value=open_log)):
        log = await quarantine_svc.block_user(db, user, moderator_id=mod_id)

    assert user.is_blocked is True
    assert user.is_quarantined is True
    assert part.is_quarantined is True
    assert log.resolution_action == ResolutionAction.BLOCKED


@pytest.mark.asyncio
async def test_unblock_user_clears_block_and_quarantine():
    """Unblocking clears is_blocked and user quarantine; leaves parts alone."""
    db = _db()
    user = _user(is_blocked=True, is_quarantined=True, quarantine_reason="blocked")
    open_log = SimpleNamespace(
        reason="blocked",
        resolved_by_moderator_id=None,
        resolution_action=None,
        resolved_at=None,
    )
    mod_id = uuid4()

    with patch.object(quarantine_svc, "_open_log", AsyncMock(return_value=open_log)):
        log = await quarantine_svc.unblock_user(db, user, moderator_id=mod_id)

    assert user.is_blocked is False
    assert user.is_quarantined is False
    assert user.quarantine_reason is None
    assert log.resolution_action == ResolutionAction.ALLOWED
