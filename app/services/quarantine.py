"""Quarantine apply/lift, logging, and automatic trigger evaluation."""

from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.story import get_story_part_by_id
from app.crud.user import get_user_by_id
from app.models.quarantine_log import EntityType, QuarantineLog, ResolutionAction
from app.models.story_part import StoryPart
from app.models.user import User


def enforce_user_not_quarantined(user: User) -> None:
    """Raise 403 if the user account is quarantined (writes blocked)."""
    if bool(user.is_quarantined):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is quarantined and cannot post or vote.",
        )


def assert_story_visible(story: StoryPart, viewer: User | None) -> None:
    """Raise 404 for quarantined parts unless the viewer is a moderator."""
    if not bool(story.is_quarantined):
        return
    if viewer is not None and bool(viewer.is_moderator):
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Story part not found",
    )


async def _open_log(
    db: AsyncSession,
    entity_type: EntityType,
    entity_id: UUID,
) -> QuarantineLog | None:
    """Return the newest unresolved quarantine log for an entity, if any."""
    result = await db.execute(
        select(QuarantineLog)
        .where(
            QuarantineLog.entity_type == entity_type,
            QuarantineLog.entity_id == entity_id,
            QuarantineLog.resolved_at.is_(None),
        )
        .order_by(QuarantineLog.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _resolve_log(
    log: QuarantineLog,
    *,
    moderator_id: UUID,
    action: ResolutionAction,
    now: datetime,
) -> None:
    """Mark a quarantine log as resolved."""
    setattr(log, "resolved_by_moderator_id", moderator_id)
    setattr(log, "resolution_action", action)
    setattr(log, "resolved_at", now)


async def quarantine_story_part(
    db: AsyncSession,
    story: StoryPart,
    *,
    reason: str,
    triggered_by: str,
    automatic: bool = True,
) -> QuarantineLog:
    """Quarantine a story part and append a QuarantineLog entry.

    Idempotent when already quarantined with an open log: returns the open log.
    """
    story_id = cast(UUID, story.id)
    open_log = await _open_log(db, EntityType.STORY_PART, story_id)
    if bool(story.is_quarantined) and open_log is not None:
        return open_log

    now = datetime.now(timezone.utc)
    setattr(story, "is_quarantined", True)
    setattr(story, "quarantine_reason", reason)
    setattr(story, "quarantined_at", now)

    log = QuarantineLog(
        entity_type=EntityType.STORY_PART,
        entity_id=story_id,
        reason=reason,
        triggered_by=triggered_by,
        automatic=automatic,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def quarantine_user(
    db: AsyncSession,
    user: User,
    *,
    reason: str,
    triggered_by: str,
    automatic: bool = True,
) -> QuarantineLog:
    """Quarantine a user account and append a QuarantineLog entry."""
    user_id = cast(UUID, user.id)
    open_log = await _open_log(db, EntityType.USER, user_id)
    if bool(user.is_quarantined) and open_log is not None:
        return open_log

    now = datetime.now(timezone.utc)
    setattr(user, "is_quarantined", True)
    setattr(user, "quarantine_reason", reason)
    setattr(user, "quarantined_at", now)

    log = QuarantineLog(
        entity_type=EntityType.USER,
        entity_id=user_id,
        reason=reason,
        triggered_by=triggered_by,
        automatic=automatic,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def lift_quarantine(
    db: AsyncSession,
    *,
    entity_type: EntityType,
    entity_id: UUID,
    moderator_id: UUID,
) -> QuarantineLog:
    """Lift quarantine on a user or story part and resolve the open log as ALLOWED."""
    if entity_type == EntityType.STORY_PART:
        story = await get_story_part_by_id(db, str(entity_id))
        if not story:
            raise HTTPException(status_code=404, detail="Story part not found")
        setattr(story, "is_quarantined", False)
        setattr(story, "quarantine_reason", None)
        setattr(story, "quarantined_at", None)
    else:
        user = await get_user_by_id(db, str(entity_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        setattr(user, "is_quarantined", False)
        setattr(user, "quarantine_reason", None)
        setattr(user, "quarantined_at", None)
        setattr(user, "quarantine_until", None)

    log = await _open_log(db, entity_type, entity_id)
    now = datetime.now(timezone.utc)
    if log is None:
        log = QuarantineLog(
            entity_type=entity_type,
            entity_id=entity_id,
            reason="Manual allow (no open log)",
            triggered_by=str(moderator_id),
            automatic=False,
        )
        db.add(log)
        await db.flush()

    _resolve_log(log, moderator_id=moderator_id, action=ResolutionAction.ALLOWED, now=now)
    await db.commit()
    await db.refresh(log)
    return log


async def mark_story_removed(
    db: AsyncSession,
    story: StoryPart,
    *,
    moderator_id: UUID,
) -> QuarantineLog:
    """Permanently hide a story part (soft): quarantine + resolve as REMOVED."""
    now = datetime.now(timezone.utc)
    story_id = cast(UUID, story.id)
    setattr(story, "is_quarantined", True)
    if not story.quarantine_reason:
        setattr(story, "quarantine_reason", "Removed by moderator")
    if not story.quarantined_at:
        setattr(story, "quarantined_at", now)

    log = await _open_log(db, EntityType.STORY_PART, story_id)
    if log is None:
        log = QuarantineLog(
            entity_type=EntityType.STORY_PART,
            entity_id=story_id,
            reason="Removed by moderator",
            triggered_by=str(moderator_id),
            automatic=False,
        )
        db.add(log)
        await db.flush()

    _resolve_log(log, moderator_id=moderator_id, action=ResolutionAction.REMOVED, now=now)
    await db.commit()
    await db.refresh(log)
    return log


async def warn_user(
    db: AsyncSession,
    user: User,
    *,
    moderator_id: UUID,
    reason: str,
    duration_hours: float | None = None,
) -> QuarantineLog:
    """Issue a warning: temporary quarantine without blocking or cascading parts.

    Args:
        db: Database session.
        user: Target user.
        moderator_id: Acting moderator.
        reason: Message shown to the user and stored on the log.
        duration_hours: How long the write quarantine lasts (defaults to settings).

    Returns:
        Resolved QuarantineLog with action WARNED.
    """
    hours = settings.WARN_DEFAULT_HOURS if duration_hours is None else float(duration_hours)
    if hours <= 0:
        raise HTTPException(status_code=400, detail="duration_hours must be positive")

    now = datetime.now(timezone.utc)
    until = now + timedelta(hours=hours)
    user_id = cast(UUID, user.id)

    setattr(user, "is_quarantined", True)
    setattr(user, "quarantine_reason", reason)
    setattr(user, "quarantined_at", now)
    setattr(user, "quarantine_until", until)
    # Warnings are temporary — never flip is_blocked here.

    log = await _open_log(db, EntityType.USER, user_id)
    if log is None:
        log = QuarantineLog(
            entity_type=EntityType.USER,
            entity_id=user_id,
            reason=reason,
            triggered_by=str(moderator_id),
            automatic=False,
        )
        db.add(log)
        await db.flush()
    else:
        setattr(log, "reason", reason)
        setattr(log, "automatic", False)
        setattr(log, "triggered_by", str(moderator_id))

    _resolve_log(log, moderator_id=moderator_id, action=ResolutionAction.WARNED, now=now)
    await db.commit()
    await db.refresh(log)
    return log


async def maybe_expire_user_quarantine(db: AsyncSession, user: User) -> bool:
    """Clear a temporary warn quarantine when ``quarantine_until`` has passed.

    Returns:
        True if the quarantine was lifted.
    """
    if not bool(user.is_quarantined):
        return False
    until = user.quarantine_until
    if until is None:
        return False
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) < until:
        return False

    user_id = cast(UUID, user.id)
    setattr(user, "is_quarantined", False)
    setattr(user, "quarantine_reason", None)
    setattr(user, "quarantined_at", None)
    setattr(user, "quarantine_until", None)

    open_log = await _open_log(db, EntityType.USER, user_id)
    if open_log is not None:
        _resolve_log(
            open_log,
            moderator_id=user_id,  # system expiry; no moderator
            action=ResolutionAction.ALLOWED,
            now=datetime.now(timezone.utc),
        )
        setattr(open_log, "triggered_by", "warn_expiry")

    await db.commit()
    return True


async def block_user(
    db: AsyncSession,
    user: User,
    *,
    moderator_id: UUID,
    reason: str = "Blocked by moderator",
) -> QuarantineLog:
    """Block a user, quarantine their account, and resolve the log as BLOCKED."""
    now = datetime.now(timezone.utc)
    user_id = cast(UUID, user.id)
    setattr(user, "is_blocked", True)
    setattr(user, "is_quarantined", True)
    setattr(user, "quarantine_reason", reason)
    setattr(user, "quarantined_at", now)
    setattr(user, "quarantine_until", None)

    result = await db.execute(
        select(StoryPart).where(
            StoryPart.author_id == user_id,
            StoryPart.is_quarantined == False,  # noqa: E712
        )
    )
    for part in result.scalars().all():
        setattr(part, "is_quarantined", True)
        setattr(part, "quarantine_reason", reason)
        setattr(part, "quarantined_at", now)

    log = await _open_log(db, EntityType.USER, user_id)
    if log is None:
        log = QuarantineLog(
            entity_type=EntityType.USER,
            entity_id=user_id,
            reason=reason,
            triggered_by=str(moderator_id),
            automatic=False,
        )
        db.add(log)
        await db.flush()

    _resolve_log(log, moderator_id=moderator_id, action=ResolutionAction.BLOCKED, now=now)
    await db.commit()
    await db.refresh(log)
    return log


async def evaluate_story_score_quarantine(db: AsyncSession, story_id: str) -> None:
    """Quarantine a part when its vote_score falls to the configured threshold."""
    story = await get_story_part_by_id(db, story_id)
    if not story or bool(story.is_quarantined):
        return
    if cast(int, story.vote_score) <= settings.QUARANTINE_STORY_SCORE_THRESHOLD:
        await quarantine_story_part(
            db,
            story,
            reason=(
                f"vote_score {story.vote_score} <= {settings.QUARANTINE_STORY_SCORE_THRESHOLD}"
            ),
            triggered_by="story_score_threshold",
        )


async def evaluate_user_reputation_quarantine(db: AsyncSession, user_id: str) -> None:
    """Quarantine a user when reputation falls to the configured threshold."""
    user = await get_user_by_id(db, user_id)
    if not user or bool(user.is_quarantined):
        return
    if cast(int, user.reputation_score) <= settings.QUARANTINE_USER_REPUTATION_THRESHOLD:
        await quarantine_user(
            db,
            user,
            reason=(
                f"reputation_score {user.reputation_score} <= "
                f"{settings.QUARANTINE_USER_REPUTATION_THRESHOLD}"
            ),
            triggered_by="user_reputation_threshold",
        )


async def evaluate_rapid_posting_quarantine(db: AsyncSession, user_id: str) -> None:
    """Quarantine a user who posts too many parts inside the rapid-post window."""
    user = await get_user_by_id(db, user_id)
    if not user or bool(user.is_quarantined):
        return

    window = timedelta(hours=settings.RAPID_POSTING_MIN_HOURS)
    since = datetime.now(timezone.utc) - window
    result = await db.execute(
        select(func.count())
        .select_from(StoryPart)
        .where(StoryPart.author_id == cast(UUID, user.id), StoryPart.created_at >= since)
    )
    count = int(result.scalar_one())
    if count >= settings.QUARANTINE_RAPID_POSTING_COUNT:
        await quarantine_user(
            db,
            user,
            reason=(
                f"rapid_posting: {count} parts within "
                f"{settings.RAPID_POSTING_MIN_HOURS}h "
                f"(threshold {settings.QUARANTINE_RAPID_POSTING_COUNT})"
            ),
            triggered_by="rapid_posting",
        )


async def evaluate_quarantine_after_score_refresh(
    db: AsyncSession,
    story_id: str,
    author_id: str,
) -> None:
    """Run score- and reputation-based quarantine checks after a score refresh."""
    await evaluate_story_score_quarantine(db, story_id)
    await evaluate_user_reputation_quarantine(db, author_id)


async def list_open_quarantine_logs(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 50,
) -> list[QuarantineLog]:
    """List unresolved quarantine logs, newest first."""
    result = await db.execute(
        select(QuarantineLog)
        .where(QuarantineLog.resolved_at.is_(None))
        .order_by(QuarantineLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_quarantine_audit_logs(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 50,
) -> list[QuarantineLog]:
    """List all quarantine logs (open and resolved), newest first."""
    result = await db.execute(
        select(QuarantineLog).order_by(QuarantineLog.created_at.desc()).offset(skip).limit(limit)
    )
    return list(result.scalars().all())
