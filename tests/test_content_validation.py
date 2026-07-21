"""Unit tests for content validation (blocklist, URLs, duplicates)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services import content_validation as cv


def test_compute_spam_confidence_clean_text():
    """Normal prose scores near zero."""
    assert cv.compute_spam_confidence("A quiet forest", "The wind stirred leaves.") == 0.0


def test_compute_spam_confidence_blocklist_hits():
    """Blocklist words raise confidence enough to quarantine at default 0.8."""
    score = cv.compute_spam_confidence("Buy viagra now", "Also casino bonuses xxx")
    assert score >= 0.8


def test_check_urls_allowed_rejects_novice():
    """Low-reputation authors cannot include links."""
    with pytest.raises(HTTPException) as exc:
        cv.check_urls_allowed("See", "Visit https://spam.example/x", reputation_score=0)
    assert exc.value.status_code == 400


def test_check_urls_allowed_for_trusted():
    """Higher reputation may include links."""
    cv.check_urls_allowed("See", "Visit https://example.com", reputation_score=50)


@pytest.mark.asyncio
async def test_check_not_duplicate_rejects_match():
    """Exact normalized duplicate of a recent part is rejected."""
    db = AsyncMock()
    existing = SimpleNamespace(
        teaser="Hello World",
        content="Once upon a time.",
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [existing]
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(HTTPException) as exc:
        await cv.check_not_duplicate(
            db,
            teaser="  hello   world ",
            content="Once upon a time.",
            author_id=uuid4(),
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_validate_story_content_quarantine_flag(monkeypatch):
    """High spam confidence sets should_quarantine."""
    monkeypatch.setattr(cv.settings, "QUARANTINE_SPAM_CONFIDENCE", 0.8)
    monkeypatch.setattr(cv.settings, "CONTENT_URL_MIN_REPUTATION", 50)
    db = AsyncMock()
    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=empty)
    user = SimpleNamespace(id=uuid4(), reputation_score=100)

    result = await cv.validate_story_content(
        db,
        user,
        "Buy viagra",
        "casino xxx click here now",
    )
    assert result.should_quarantine is True
    assert result.spam_confidence >= 0.8
