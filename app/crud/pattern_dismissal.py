"""CRUD for voting-pattern dismissals."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pattern_dismissal import PatternDismissal


async def get_active_dismissal_keys(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> set[tuple[UUID, str]]:
    """Return ``(user_id, flag)`` pairs with a non-expired dismissal."""
    moment = now or datetime.now(timezone.utc)
    result = await db.execute(
        select(PatternDismissal.user_id, PatternDismissal.flag).where(
            or_(
                PatternDismissal.expires_at.is_(None),
                PatternDismissal.expires_at > moment,
            )
        )
    )
    return {(row[0], row[1]) for row in result.all()}


async def upsert_pattern_dismissal(
    db: AsyncSession,
    *,
    user_id: UUID,
    flag: str,
    moderator_id: UUID,
    expires_at: datetime | None,
    reason: str | None = None,
    commit: bool = True,
) -> PatternDismissal:
    """Create or refresh a dismissal for ``(user_id, flag)``."""
    result = await db.execute(
        select(PatternDismissal).where(
            and_(
                PatternDismissal.user_id == user_id,
                PatternDismissal.flag == flag,
            )
        )
    )
    row = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row is None:
        row = PatternDismissal(
            user_id=user_id,
            flag=flag,
            dismissed_by_moderator_id=moderator_id,
            reason=reason,
            expires_at=expires_at,
        )
        db.add(row)
    else:
        setattr(row, "dismissed_by_moderator_id", moderator_id)
        setattr(row, "reason", reason)
        setattr(row, "expires_at", expires_at)
        setattr(row, "updated_at", now)
    if commit:
        await db.commit()
        await db.refresh(row)
    else:
        await db.flush()
    return row


async def dismiss_all_flags_for_user(
    db: AsyncSession,
    *,
    user_id: UUID,
    flags: list[str],
    moderator_id: UUID,
    expires_at: datetime | None,
    reason: str | None = None,
) -> None:
    """Upsert dismissals for each flag on a user (e.g. after warn/block)."""
    for flag in flags:
        await upsert_pattern_dismissal(
            db,
            user_id=user_id,
            flag=flag,
            moderator_id=moderator_id,
            expires_at=expires_at,
            reason=reason,
            commit=False,
        )
    await db.commit()
