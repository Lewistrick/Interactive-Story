"""Unit tests for velocity / hacked-account heuristics."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services import velocity as velocity_svc


def _old_user(**kwargs):
    """User older than the velocity min-age threshold."""
    defaults = {
        "id": uuid4(),
        "created_at": datetime.now(timezone.utc) - timedelta(days=3),
        "is_quarantined": False,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_velocity_skips_young_accounts(monkeypatch):
    """Accounts newer than the age gate are not quarantined."""
    monkeypatch.setattr(velocity_svc.settings, "VELOCITY_MIN_ACCOUNT_AGE_HOURS", 24.0)
    user = _old_user(created_at=datetime.now(timezone.utc) - timedelta(hours=1))
    request = MagicMock()
    with patch.object(velocity_svc, "_incr_burst", AsyncMock()) as incr:
        result = await velocity_svc.evaluate_velocity_anomaly(
            AsyncMock(), user, request, action="vote"
        )
    assert result is False
    incr.assert_not_awaited()


@pytest.mark.asyncio
async def test_velocity_quarantines_on_burst(monkeypatch):
    """Established accounts hitting the burst limit are quarantined."""
    monkeypatch.setattr(velocity_svc.settings, "VELOCITY_MIN_ACCOUNT_AGE_HOURS", 24.0)
    monkeypatch.setattr(velocity_svc.settings, "VELOCITY_VOTE_BURST_LIMIT", 5)
    monkeypatch.setattr(velocity_svc.settings, "VELOCITY_VOTE_WINDOW_SECONDS", 60)
    user = _old_user()
    db_user = _old_user(id=user.id)
    request = MagicMock()

    with (
        patch.object(velocity_svc, "_incr_burst", AsyncMock(return_value=5)),
        patch.object(velocity_svc, "_ip_shifted", AsyncMock(return_value=True)),
        patch.object(velocity_svc, "_fingerprint_shifted", AsyncMock(return_value=False)),
        patch.object(velocity_svc, "get_user_by_id", AsyncMock(return_value=db_user)),
        patch.object(velocity_svc, "quarantine_user", AsyncMock()) as q,
        patch.object(velocity_svc, "force_password_reset", AsyncMock()) as reset,
    ):
        result = await velocity_svc.evaluate_velocity_anomaly(
            AsyncMock(), user, request, action="vote"
        )

    assert result is True
    q.assert_awaited_once()
    assert q.await_args is not None
    assert "velocity_anomaly" in q.await_args.kwargs["reason"]
    assert "IP changed" in q.await_args.kwargs["reason"]
    assert q.await_args.kwargs["triggered_by"] == "velocity_anomaly"
    reset.assert_awaited_once()


@pytest.mark.asyncio
async def test_velocity_below_limit_no_quarantine(monkeypatch):
    """Counts under the burst limit do not quarantine."""
    monkeypatch.setattr(velocity_svc.settings, "VELOCITY_MIN_ACCOUNT_AGE_HOURS", 24.0)
    monkeypatch.setattr(velocity_svc.settings, "VELOCITY_POST_BURST_LIMIT", 5)
    user = _old_user()
    request = MagicMock()

    with (
        patch.object(velocity_svc, "_incr_burst", AsyncMock(return_value=2)),
        patch.object(velocity_svc, "_ip_shifted", AsyncMock(return_value=False)),
        patch.object(velocity_svc, "_fingerprint_shifted", AsyncMock(return_value=False)),
        patch.object(velocity_svc, "quarantine_user", AsyncMock()) as q,
        patch.object(velocity_svc, "force_password_reset", AsyncMock()) as reset,
    ):
        result = await velocity_svc.evaluate_velocity_anomaly(
            AsyncMock(), user, request, action="post"
        )

    assert result is False
    q.assert_not_awaited()
    reset.assert_not_awaited()


@pytest.mark.asyncio
async def test_velocity_fingerprint_shift_forces_password_reset(monkeypatch):
    """Fingerprint shift on a burst trip forces password reset."""
    monkeypatch.setattr(velocity_svc.settings, "VELOCITY_MIN_ACCOUNT_AGE_HOURS", 24.0)
    monkeypatch.setattr(velocity_svc.settings, "VELOCITY_VOTE_BURST_LIMIT", 5)
    monkeypatch.setattr(velocity_svc.settings, "VELOCITY_VOTE_WINDOW_SECONDS", 60)
    user = _old_user()
    db_user = _old_user(id=user.id)
    request = MagicMock()

    with (
        patch.object(velocity_svc, "_incr_burst", AsyncMock(return_value=5)),
        patch.object(velocity_svc, "_ip_shifted", AsyncMock(return_value=False)),
        patch.object(velocity_svc, "_fingerprint_shifted", AsyncMock(return_value=True)),
        patch.object(velocity_svc, "get_user_by_id", AsyncMock(return_value=db_user)),
        patch.object(velocity_svc, "quarantine_user", AsyncMock()) as q,
        patch.object(velocity_svc, "force_password_reset", AsyncMock()) as reset,
    ):
        result = await velocity_svc.evaluate_velocity_anomaly(
            AsyncMock(), user, request, action="vote"
        )

    assert result is True
    assert q.await_args is not None
    assert "device fingerprint changed" in q.await_args.kwargs["reason"]
    reset.assert_awaited_once()


@pytest.mark.asyncio
async def test_velocity_burst_without_shift_skips_password_reset(monkeypatch):
    """Burst quarantine alone does not force a password reset."""
    monkeypatch.setattr(velocity_svc.settings, "VELOCITY_MIN_ACCOUNT_AGE_HOURS", 24.0)
    monkeypatch.setattr(velocity_svc.settings, "VELOCITY_POST_BURST_LIMIT", 5)
    user = _old_user()
    db_user = _old_user(id=user.id)
    request = MagicMock()

    with (
        patch.object(velocity_svc, "_incr_burst", AsyncMock(return_value=5)),
        patch.object(velocity_svc, "_ip_shifted", AsyncMock(return_value=False)),
        patch.object(velocity_svc, "_fingerprint_shifted", AsyncMock(return_value=False)),
        patch.object(velocity_svc, "get_user_by_id", AsyncMock(return_value=db_user)),
        patch.object(velocity_svc, "quarantine_user", AsyncMock()),
        patch.object(velocity_svc, "force_password_reset", AsyncMock()) as reset,
    ):
        result = await velocity_svc.evaluate_velocity_anomaly(
            AsyncMock(), user, request, action="post"
        )

    assert result is True
    reset.assert_not_awaited()
