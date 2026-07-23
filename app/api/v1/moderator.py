"""Moderator quarantine queue and resolution endpoints."""

from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_moderator
from app.crud.moderation_user import list_votes_cast
from app.crud.pattern_dismissal import dismiss_all_flags_for_user, upsert_pattern_dismissal
from app.crud.story import get_story_part_by_id
from app.crud.user import get_user_by_id
from app.db.session import get_db
from app.models.quarantine_log import EntityType, QuarantineLog
from app.models.story_part import VoteType
from app.models.user import User
from app.schemas.moderation import (
    BlockUserRequest,
    BulkModerationRequest,
    BulkModerationResponse,
    DismissPatternRequest,
    ModeratorUserVote,
    QuarantineLogResponse,
    ReputationPoint,
    VotingPatternFlag,
    WarnUserRequest,
)
from app.services.mod_insights import (
    KNOWN_PATTERN_FLAGS,
    get_reputation_history,
    list_voting_pattern_flags,
)
from app.services.quarantine import (
    block_user,
    lift_quarantine,
    list_open_quarantine_logs,
    list_quarantine_audit_logs,
    mark_story_removed,
    unblock_user,
    warn_user,
)

router = APIRouter()

_TEASER_PREVIEW_LEN = 160
_CONTENT_PREVIEW_LEN = 280


def _dismissal_expires_at(duration_hours: float | None) -> datetime | None:
    """Resolve dismiss expiry: ``None`` hours → default; ``0`` → never expires."""
    match duration_hours:
        case None:
            hours = settings.VOTING_PATTERN_DISMISS_DEFAULT_HOURS
        case _:
            hours = duration_hours
    if hours <= 0:
        return None
    return datetime.now(timezone.utc) + timedelta(hours=hours)


async def _auto_dismiss_user_patterns(
    db: AsyncSession,
    *,
    user_id: UUID,
    moderator_id: UUID,
    reason: str,
) -> None:
    """Permanently hide all known pattern flags for a user after warn/block."""
    await dismiss_all_flags_for_user(
        db,
        user_id=user_id,
        flags=list(KNOWN_PATTERN_FLAGS),
        moderator_id=moderator_id,
        expires_at=None,
        reason=reason,
    )


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
    match log.entity_type:
        case EntityType.STORY_PART:
            if (story := await get_story_part_by_id(db, str(log.entity_id))) is None:
                return base
            author = story.author.username if story.author else None
            return base.model_copy(
                update={
                    "author_username": author,
                    "author_id": story.author_id,
                    "teaser": _trim(str(story.teaser), _TEASER_PREVIEW_LEN),
                    "content_preview": _trim(str(story.content), _CONTENT_PREVIEW_LEN),
                }
            )
        case EntityType.USER:
            if (user := await get_user_by_id(db, str(log.entity_id))) is None:
                return base
            return base.model_copy(update={"author_username": user.username, "author_id": user.id})
        case _:
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


@router.post("/bulk", response_model=BulkModerationResponse)
async def bulk_moderation(
    body: BulkModerationRequest,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Apply allow, remove, or block to many queue targets at once."""
    processed = 0
    errors: list[str] = []
    for item in body.items:
        try:
            match body.action:
                case "allow":
                    await lift_quarantine(
                        db,
                        entity_type=item.entity_type,
                        entity_id=item.entity_id,
                        moderator_id=current_user.id,
                    )
                case "remove":
                    if item.entity_type != EntityType.STORY_PART:
                        raise ValueError("remove requires STORY_PART")
                    if (story := await get_story_part_by_id(db, str(item.entity_id))) is None:
                        raise ValueError("story part not found")
                    await mark_story_removed(db, story, moderator_id=current_user.id)
                case "block":
                    user_id = item.entity_id
                    if item.entity_type == EntityType.STORY_PART:
                        if (
                            story := await get_story_part_by_id(db, str(item.entity_id))
                        ) is None or not story.author_id:
                            raise ValueError("cannot resolve author to block")
                        user_id = story.author_id
                    if (user := await get_user_by_id(db, str(user_id))) is None:
                        raise ValueError("user not found")
                    await block_user(
                        db,
                        user,
                        moderator_id=current_user.id,
                        reason="Bulk blocked by moderator",
                    )
                    await _auto_dismiss_user_patterns(
                        db,
                        user_id=cast(UUID, user.id),
                        moderator_id=cast(UUID, current_user.id),
                        reason="Auto-dismissed after bulk block",
                    )
                case _:
                    raise ValueError(f"unknown action {body.action!r}")
            processed += 1
        except Exception as exc:  # noqa: BLE001 — collect per-item failures
            errors.append(f"{item.entity_type}:{item.entity_id}: {exc}")
    return BulkModerationResponse(
        processed=processed,
        failed=len(errors),
        errors=errors,
    )


@router.get("/voting-patterns", response_model=list[VotingPatternFlag])
async def voting_patterns(
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """List accounts with suspicious recent voting patterns (severity desc)."""
    rows = await list_voting_pattern_flags(db, limit=limit)
    return [VotingPatternFlag.model_validate(row) for row in rows]


@router.post("/voting-patterns/dismiss", response_model=VotingPatternFlag)
async def dismiss_voting_pattern(
    body: DismissPatternRequest,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Allow/dismiss a pattern flag so it leaves the Patterns tab until expiry."""
    if body.flag not in KNOWN_PATTERN_FLAGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown flag; expected one of {', '.join(KNOWN_PATTERN_FLAGS)}",
        )
    if (user := await get_user_by_id(db, str(body.user_id))) is None:
        raise HTTPException(status_code=404, detail="User not found")

    expires_at = _dismissal_expires_at(body.duration_hours)
    await upsert_pattern_dismissal(
        db,
        user_id=body.user_id,
        flag=body.flag,
        moderator_id=cast(UUID, current_user.id),
        expires_at=expires_at,
        reason=body.reason,
    )
    # Echo a lightweight confirmation payload for the UI.
    return VotingPatternFlag(
        user_id=body.user_id,
        username=cast(str, user.username),
        flag=body.flag,
        detail="Dismissed",
        reputation_score=int(cast(int, user.reputation_score)),
        metric=0,
        severity=0,
    )


@router.get(
    "/users/{user_id}/reputation-history",
    response_model=list[ReputationPoint],
)
async def reputation_history(
    user_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Reputation snapshots for sparkline charts (after score recalcs)."""
    if (await get_user_by_id(db, str(user_id))) is None:
        raise HTTPException(status_code=404, detail="User not found")
    rows = await get_reputation_history(db, user_id, limit=limit)
    return [ReputationPoint.model_validate(row) for row in rows]


@router.get("/users/{user_id}/votes", response_model=list[ModeratorUserVote])
async def get_moderator_user_votes(
    user_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    vote_type: VoteType | None = Query(None),
    _: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """List votes cast by the user, newest first."""
    if (await get_user_by_id(db, str(user_id))) is None:
        raise HTTPException(status_code=404, detail="User not found")
    votes = await list_votes_cast(
        db,
        user_id,
        skip=skip,
        limit=limit,
        vote_type=vote_type,
    )
    results: list[ModeratorUserVote] = []
    for vote in votes:
        if (part := vote.story_part) is None:
            continue
        author_name = part.author.username if part.author else None
        results.append(
            ModeratorUserVote(
                vote_id=vote.id,
                vote_type=vote.vote_type,
                voted_at=vote.created_at,
                story_part_id=part.id,
                teaser=str(part.teaser),
                vote_score=int(part.vote_score),
                recursive_score=int(part.recursive_score),
                is_quarantined=bool(part.is_quarantined),
                author_username=author_name,
            )
        )
    return results


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
    if (story := await get_story_part_by_id(db, str(entity_id))) is None:
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
    if (user := await get_user_by_id(db, str(user_id))) is None:
        raise HTTPException(status_code=404, detail="User not found")
    reason = (body.reason if body and body.reason else None) or "Blocked by moderator"
    log = await block_user(
        db,
        user,
        moderator_id=cast(UUID, current_user.id),
        reason=reason,
    )
    await _auto_dismiss_user_patterns(
        db,
        user_id=user_id,
        moderator_id=cast(UUID, current_user.id),
        reason="Auto-dismissed after block",
    )
    return await _enrich_log(db, log)


@router.post("/users/{user_id}/unblock", response_model=QuarantineLogResponse)
async def unblock_user_endpoint(
    user_id: UUID,
    body: BlockUserRequest | None = None,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Clear the blocked flag and lift the user-account quarantine."""
    if (user := await get_user_by_id(db, str(user_id))) is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not bool(user.is_blocked):
        raise HTTPException(status_code=400, detail="User is not blocked")
    reason = (body.reason if body and body.reason else None) or "Unblocked by moderator"
    log = await unblock_user(
        db,
        user,
        moderator_id=cast(UUID, current_user.id),
        reason=reason,
    )
    return await _enrich_log(db, log)


@router.post("/users/{user_id}/warn", response_model=QuarantineLogResponse)
async def warn_user_endpoint(
    user_id: UUID,
    body: WarnUserRequest,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Warn a user with a temporary write quarantine (default 24h)."""
    if (user := await get_user_by_id(db, str(user_id))) is None:
        raise HTTPException(status_code=404, detail="User not found")
    log = await warn_user(
        db,
        user,
        moderator_id=cast(UUID, current_user.id),
        reason=body.reason,
        duration_hours=body.duration_hours,
    )
    await _auto_dismiss_user_patterns(
        db,
        user_id=user_id,
        moderator_id=cast(UUID, current_user.id),
        reason="Auto-dismissed after warn",
    )
    return await _enrich_log(db, log)
