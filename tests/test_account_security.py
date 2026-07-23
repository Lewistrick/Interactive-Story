"""Unit tests for forced password reset helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import account_security as account_sec


@pytest.mark.asyncio
async def test_force_password_reset_bumps_token_version():
    """Force-reset sets the flag and rotates token_version."""
    user = SimpleNamespace(must_reset_password=False, token_version=2)
    db = AsyncMock()
    await account_sec.force_password_reset(db, user)
    assert user.must_reset_password is True
    assert user.token_version == 3
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_complete_password_change_clears_flag():
    """Changing password clears must_reset_password and bumps token_version."""
    user = SimpleNamespace(
        must_reset_password=True,
        token_version=1,
        password_hash="old",
    )
    db = AsyncMock()
    with patch.object(account_sec, "get_password_hash", return_value="new-hash"):
        await account_sec.complete_password_change(db, user, new_password="secret99")
    assert user.password_hash == "new-hash"
    assert user.must_reset_password is False
    assert user.token_version == 2
