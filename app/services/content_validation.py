"""Content validation: blocklist spam score, duplicates, and URL gates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.story_part import StoryPart

# Conservative starter blocklist (words/phrases). Extend via env later if needed.
_BLOCKLIST_WORDS = frozenset(
    {
        "viagra",
        "cialis",
        "cryptoairdrop",
        "freebitcoin",
        "clickhere",
        "makemoneyfast",
        "porn",
        "xxx",
        "casino",
        "gambling-spam",
    }
)

_BLOCKLIST_PHRASES = (
    "work from home $$$",
    "buy followers",
    "click here now",
    "limited time offer",
    "double your bitcoin",
)

_URL_RE = re.compile(
    r"(?:https?://|www\.)\S+|(?:[a-z0-9-]+\.)+(?:com|net|org|io|co|xyz|info)\b",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)


class UserLike(Protocol):
    """Minimal user fields for content checks."""

    id: Any
    reputation_score: int


@dataclass(frozen=True)
class ContentValidationResult:
    """Outcome of soft checks that may quarantine after create."""

    spam_confidence: float
    should_quarantine: bool


def normalize_text(text: str) -> str:
    """Collapse whitespace and lowercase for duplicate comparison."""
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_urls(text: str) -> list[str]:
    """Return URL-like substrings found in text."""
    return _URL_RE.findall(text) if text else []


def compute_spam_confidence(teaser: str, content: str) -> float:
    """Estimate spam likelihood from blocklist hits (0.0–1.0).

    Each matched word contributes 0.4; each matched phrase contributes 0.85.
    Score is capped at 1.0. Compared to ``QUARANTINE_SPAM_CONFIDENCE``.
    """
    combined = f"{teaser}\n{content}".lower()
    score = 0.0
    for phrase in _BLOCKLIST_PHRASES:
        if phrase in combined:
            score += 0.85
    tokens = set(_TOKEN_RE.findall(combined))
    for word in tokens:
        if word.lower() in _BLOCKLIST_WORDS:
            score += 0.4
    return min(1.0, score)


def check_urls_allowed(teaser: str, content: str, reputation_score: int) -> None:
    """Reject posts with links when reputation is below the URL gate."""
    if reputation_score >= settings.CONTENT_URL_MIN_REPUTATION:
        return
    combined = f"{teaser}\n{content}"
    if extract_urls(combined):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Links are not allowed until your reputation reaches "
                f"{settings.CONTENT_URL_MIN_REPUTATION}."
            ),
        )


async def check_not_duplicate(
    db: AsyncSession,
    *,
    teaser: str,
    content: str,
    author_id: Any,
) -> None:
    """Reject near-exact copy-paste of recent teaser+content."""
    del author_id  # reserved for future author-scoped lookbacks
    norm_teaser = normalize_text(teaser)
    norm_content = normalize_text(content)
    lookback = settings.CONTENT_DUPLICATE_LOOKBACK

    result = await db.execute(
        select(StoryPart).order_by(StoryPart.created_at.desc()).limit(lookback)
    )
    for part in result.scalars().all():
        if (
            normalize_text(str(part.teaser)) == norm_teaser
            and normalize_text(str(part.content)) == norm_content
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate content: this text was already published recently.",
            )


async def validate_story_content(
    db: AsyncSession,
    user: UserLike,
    teaser: str,
    content: str,
) -> ContentValidationResult:
    """Run hard rejects (URLs, duplicates) and compute spam quarantine signal.

    Args:
        db: Database session.
        user: Authenticated author.
        teaser: Proposed teaser.
        content: Proposed body.

    Returns:
        Soft-check result; caller should quarantine when ``should_quarantine``.
    """
    check_urls_allowed(teaser, content, int(user.reputation_score))
    await check_not_duplicate(db, teaser=teaser, content=content, author_id=user.id)

    confidence = compute_spam_confidence(teaser, content)
    should_quarantine = confidence >= settings.QUARANTINE_SPAM_CONFIDENCE
    return ContentValidationResult(
        spam_confidence=confidence,
        should_quarantine=should_quarantine,
    )
