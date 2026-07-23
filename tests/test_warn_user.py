"""Tests for moderator warn + temporary quarantine expiry."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from typing import cast

import pytest

from app.models.quarantine_log import ResolutionAction
from app.models.user import User
from app.services import quarantine as quarantine_svc


@pytest.mark.asyncio
async def test_warn_user_sets_temporary_quarantine(monkeypatch):
    """Warn quarantines the user until quarantine_until without blocking."""
    monkeypatch.setattr(quarantine_svc.settings, "WARN_DEFAULT_HOURS", 24.0)
    db = AsyncMock()
    db.add = MagicMock()
    user = SimpleNamespace(
        id=uuid4(),
        is_quarantined=False,
        quarantine_reason=None,
        quarantined_at=None,
        quarantine_until=None,
        is_blocked=False,
    )
    mod_id = uuid4()

    with patch.object(quarantine_svc, "_open_log", AsyncMock(return_value=None)):
        log = await quarantine_svc.warn_user(
            db,
            cast(User, user),
            moderator_id=mod_id,
            reason="Please keep it civil.",
        )

    assert user.is_quarantined is True
    assert user.is_blocked is False
    assert user.quarantine_reason == "Please keep it civil."
    assert user.quarantine_until is not None
    assert log.resolution_action == ResolutionAction.WARNED


@pytest.mark.asyncio
async def test_maybe_expire_lifts_when_past_until():
    """Expired temporary quarantines are cleared automatically."""
    db = AsyncMock()
    user = SimpleNamespace(
        id=uuid4(),
        is_quarantined=True,
        quarantine_reason="warn",
        quarantined_at=datetime.now(timezone.utc) - timedelta(hours=2),
        quarantine_until=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    with patch.object(quarantine_svc, "_open_log", AsyncMock(return_value=None)):
        lifted = await quarantine_svc.maybe_expire_user_quarantine(db, cast(User, user))

    assert lifted is True
    assert user.is_quarantined is False
    assert user.quarantine_until is None


@pytest.mark.asyncio
async def test_maybe_expire_keeps_active_warn():
    """Active temporary quarantines are left alone."""
    db = AsyncMock()
    user = SimpleNamespace(
        id=uuid4(),
        is_quarantined=True,
        quarantine_reason="warn",
        quarantined_at=datetime.now(timezone.utc),
        quarantine_until=datetime.now(timezone.utc) + timedelta(hours=12),
    )
    lifted = await quarantine_svc.maybe_expire_user_quarantine(db, cast(User, user))
    assert lifted is False
    assert user.is_quarantined is True
