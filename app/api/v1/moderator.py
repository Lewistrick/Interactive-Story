"""Moderator quarantine queue and resolution endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_moderator
from app.crud.story import get_story_part_by_id
from app.crud.user import get_user_by_id
from app.db.session import get_db
from app.models.quarantine_log import EntityType
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


@router.get("/quarantine-queue", response_model=list[QuarantineLogResponse])
async def quarantine_queue(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """List unresolved quarantine items, newest first."""
    logs = await list_open_quarantine_logs(db, skip=skip, limit=limit)
    return [QuarantineLogResponse.model_validate(log) for log in logs]


@router.get("/audit-log", response_model=list[QuarantineLogResponse])
async def audit_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """List all quarantine log entries (open and resolved)."""
    logs = await list_quarantine_audit_logs(db, skip=skip, limit=limit)
    return [QuarantineLogResponse.model_validate(log) for log in logs]


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
    return QuarantineLogResponse.model_validate(log)


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
    return QuarantineLogResponse.model_validate(log)


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
    return QuarantineLogResponse.model_validate(log)
