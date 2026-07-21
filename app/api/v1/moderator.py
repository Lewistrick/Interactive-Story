"""Moderator quarantine queue and resolution endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_moderator
from app.crud.story import get_story_part_by_id
from app.crud.user import get_user_by_id
from app.db.session import get_db
from app.models.quarantine_log import EntityType, QuarantineLog
from app.models.user import User
from app.schemas.moderation import (
    BlockUserRequest,
    QuarantineLogResponse,
)
from app.services.quarantine import (
    block_user,
    lift_quarantine,
    list_open_quarantine_logs,
    list_quarantine_audit_logs,
    mark_story_removed,
)

router = APIRouter()

_TEASER_PREVIEW_LEN = 160
_CONTENT_PREVIEW_LEN = 280


def _trim(text: str | None, max_len: int) -> str | None:
    """Trim text for moderator list previews."""
    if text is None:
        return None
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


async def _enrich_log(db: AsyncSession, log: QuarantineLog) -> QuarantineLogResponse:
    """Attach author / teaser / body preview when the entity still exists."""
    base = QuarantineLogResponse.model_validate(log)
    if log.entity_type == EntityType.STORY_PART:
        story = await get_story_part_by_id(db, str(log.entity_id))
        if story is None:
            return base
        author = story.author.username if story.author else None
        return base.model_copy(
            update={
                "author_username": author,
                "teaser": _trim(str(story.teaser), _TEASER_PREVIEW_LEN),
                "content_preview": _trim(str(story.content), _CONTENT_PREVIEW_LEN),
            }
        )
    if log.entity_type == EntityType.USER:
        user = await get_user_by_id(db, str(log.entity_id))
        if user is None:
            return base
        return base.model_copy(update={"author_username": user.username})
    return base


@router.get("/quarantine-queue", response_model=list[QuarantineLogResponse])
async def quarantine_queue(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """List unresolved quarantine items, newest first."""
    logs = await list_open_quarantine_logs(db, skip=skip, limit=limit)
    return [await _enrich_log(db, log) for log in logs]


@router.get("/audit-log", response_model=list[QuarantineLogResponse])
async def audit_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """List all quarantine log entries (open and resolved)."""
    logs = await list_quarantine_audit_logs(db, skip=skip, limit=limit)
    return [await _enrich_log(db, log) for log in logs]


@router.post(
    "/{entity_type}/{entity_id}/allow",
    response_model=QuarantineLogResponse,
)
async def allow_entity(
    entity_type: EntityType,
    entity_id: UUID,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Lift quarantine on a user or story part."""
    log = await lift_quarantine(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        moderator_id=current_user.id,
    )
    return await _enrich_log(db, log)


@router.post(
    "/{entity_type}/{entity_id}/remove",
    response_model=QuarantineLogResponse,
)
async def remove_entity(
    entity_type: EntityType,
    entity_id: UUID,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Permanently hide a story part (soft quarantine + REMOVED resolution).

    Children are not cascade-deleted; they remain addressable by id if not
    themselves quarantined.
    """
    if entity_type != EntityType.STORY_PART:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Remove applies only to story parts; use block for users.",
        )
    story = await get_story_part_by_id(db, str(entity_id))
    if not story:
        raise HTTPException(status_code=404, detail="Story part not found")
    log = await mark_story_removed(db, story, moderator_id=current_user.id)
    return await _enrich_log(db, log)


@router.post("/users/{user_id}/block", response_model=QuarantineLogResponse)
async def block_user_endpoint(
    user_id: UUID,
    body: BlockUserRequest | None = None,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Block a user, quarantine their account and authored parts."""
    user = await get_user_by_id(db, str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    reason = (body.reason if body and body.reason else None) or "Blocked by moderator"
    log = await block_user(
        db,
        user,
        moderator_id=current_user.id,
        reason=reason,
    )
    return await _enrich_log(db, log)
