"""Moderator quarantine queue and resolution endpoints."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_moderator
from app.crud.moderation_user import (
    PartSortField,
    count_authored_parts,
    count_votes_by_type,
    list_authored_parts,
    list_votes_cast,
)
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
    ModeratorUserPart,
    ModeratorUserProfile,
    ModeratorUserVote,
    QuarantineLogResponse,
    ReputationPoint,
    VotingPatternFlag,
    WarnUserRequest,
)
from app.services.mod_insights import get_reputation_history, list_voting_pattern_flags
from app.services.quarantine import (
    block_user,
    lift_quarantine,
    list_open_quarantine_logs,
    list_quarantine_audit_logs,
    mark_story_removed,
    warn_user,
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
                "author_id": story.author_id,
                "teaser": _trim(str(story.teaser), _TEASER_PREVIEW_LEN),
                "content_preview": _trim(str(story.content), _CONTENT_PREVIEW_LEN),
            }
        )
    if log.entity_type == EntityType.USER:
        user = await get_user_by_id(db, str(log.entity_id))
        if user is None:
            return base
        return base.model_copy(update={"author_username": user.username, "author_id": user.id})
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
            if body.action == "allow":
                await lift_quarantine(
                    db,
                    entity_type=item.entity_type,
                    entity_id=item.entity_id,
                    moderator_id=current_user.id,
                )
            elif body.action == "remove":
                if item.entity_type != EntityType.STORY_PART:
                    raise ValueError("remove requires STORY_PART")
                story = await get_story_part_by_id(db, str(item.entity_id))
                if not story:
                    raise ValueError("story part not found")
                await mark_story_removed(db, story, moderator_id=current_user.id)
            elif body.action == "block":
                user_id = item.entity_id
                if item.entity_type == EntityType.STORY_PART:
                    story = await get_story_part_by_id(db, str(item.entity_id))
                    if not story or not story.author_id:
                        raise ValueError("cannot resolve author to block")
                    user_id = story.author_id
                user = await get_user_by_id(db, str(user_id))
                if not user:
                    raise ValueError("user not found")
                await block_user(
                    db,
                    user,
                    moderator_id=current_user.id,
                    reason="Bulk blocked by moderator",
                )
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
    """List accounts with suspicious recent voting patterns."""
    rows = await list_voting_pattern_flags(db, limit=limit)
    return [VotingPatternFlag.model_validate(row) for row in rows]


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
    user = await get_user_by_id(db, str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    rows = await get_reputation_history(db, user_id, limit=limit)
    return [ReputationPoint.model_validate(row) for row in rows]


@router.get("/users/{user_id}", response_model=ModeratorUserProfile)
async def get_moderator_user_profile(
    user_id: UUID,
    _: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Return summary stats for the moderator user history page."""
    user = await get_user_by_id(db, str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    authored_count = await count_authored_parts(db, user_id)
    quarantined_parts_count = await count_authored_parts(db, user_id, quarantined_only=True)
    votes_up, votes_down = await count_votes_by_type(db, user_id)
    return ModeratorUserProfile(
        id=user.id,
        username=user.username,
        reputation_score=int(user.reputation_score),
        is_quarantined=bool(user.is_quarantined),
        quarantine_reason=user.quarantine_reason,
        quarantine_until=user.quarantine_until,
        is_blocked=bool(user.is_blocked),
        is_moderator=bool(user.is_moderator),
        created_at=user.created_at,
        authored_count=authored_count,
        quarantined_parts_count=quarantined_parts_count,
        votes_cast_count=votes_up + votes_down,
        votes_up_count=votes_up,
        votes_down_count=votes_down,
    )


@router.get("/users/{user_id}/parts", response_model=list[ModeratorUserPart])
async def get_moderator_user_parts(
    user_id: UUID,
    sort: PartSortField = Query(PartSortField.AGE),
    order: Literal["asc", "desc"] = Query("desc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    quarantined_only: bool = Query(False),
    _: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """List story parts authored by the user (sortable, paginated)."""
    user = await get_user_by_id(db, str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    parts = await list_authored_parts(
        db,
        user_id,
        sort=sort,
        order=order,
        skip=skip,
        limit=limit,
        quarantined_only=quarantined_only,
    )
    return [ModeratorUserPart.model_validate(part) for part in parts]


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
    user = await get_user_by_id(db, str(user_id))
    if not user:
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
        part = vote.story_part
        if part is None:
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


@router.post("/users/{user_id}/warn", response_model=QuarantineLogResponse)
async def warn_user_endpoint(
    user_id: UUID,
    body: WarnUserRequest,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Warn a user with a temporary write quarantine (default 24h)."""
    user = await get_user_by_id(db, str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    log = await warn_user(
        db,
        user,
        moderator_id=current_user.id,
        reason=body.reason,
        duration_hours=body.duration_hours,
    )
    return await _enrich_log(db, log)
