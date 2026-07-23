"""Public user profile endpoints."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_optional
from app.crud.moderation_user import (
    PartSortField,
    count_authored_parts,
    count_votes_by_type,
    list_authored_parts,
)
from app.crud.story import get_children_count
from app.crud.user import get_user_by_id
from app.db.session import get_db
from app.models.user import User
from app.schemas.user_profile import UserPart, UserProfile

router = APIRouter()


@router.get("/{user_id}", response_model=UserProfile)
async def get_user_profile(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_current_user_optional),
):
    """Return a public user summary; moderators get extra status fields."""
    if (user := await get_user_by_id(db, str(user_id))) is None:
        raise HTTPException(status_code=404, detail="User not found")

    is_mod = bool(viewer and viewer.is_moderator)
    authored_count = await count_authored_parts(
        db,
        user_id,
        exclude_quarantined=not is_mod,
    )

    profile = UserProfile(
        id=user.id,
        username=user.username,
        reputation_score=int(user.reputation_score),
        created_at=user.created_at,
        authored_count=authored_count,
        is_moderator=bool(user.is_moderator),
    )
    if is_mod:
        quarantined_parts_count = await count_authored_parts(db, user_id, quarantined_only=True)
        votes_up, votes_down = await count_votes_by_type(db, user_id)
        profile = profile.model_copy(
            update={
                "is_quarantined": bool(user.is_quarantined),
                "quarantine_reason": user.quarantine_reason,
                "quarantine_until": user.quarantine_until,
                "is_blocked": bool(user.is_blocked),
                "quarantined_parts_count": quarantined_parts_count,
                "votes_cast_count": votes_up + votes_down,
                "votes_up_count": votes_up,
                "votes_down_count": votes_down,
                "authored_count": await count_authored_parts(db, user_id),
            }
        )
    return profile


@router.get("/{user_id}/parts", response_model=list[UserPart])
async def get_user_parts(
    user_id: UUID,
    sort: PartSortField = Query(PartSortField.AGE),
    order: Literal["asc", "desc"] = Query("desc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    include_quarantined: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_current_user_optional),
):
    """List authored parts. Quarantined parts only when a moderator opts in."""
    if (await get_user_by_id(db, str(user_id))) is None:
        raise HTTPException(status_code=404, detail="User not found")

    is_mod = bool(viewer and viewer.is_moderator)
    show_quarantined = is_mod and include_quarantined
    parts = await list_authored_parts(
        db,
        user_id,
        sort=sort,
        order=order,
        skip=skip,
        limit=limit,
        exclude_quarantined=not show_quarantined,
    )
    results: list[UserPart] = []
    for part in parts:
        children_count = await get_children_count(db, str(part.id))
        results.append(
            UserPart(
                id=part.id,
                teaser=str(part.teaser),
                vote_score=int(part.vote_score),
                recursive_score=int(part.recursive_score),
                depth_level=int(part.depth_level),
                is_quarantined=bool(part.is_quarantined),
                parent_part_id=part.parent_part_id,
                created_at=part.created_at,
                children_count=children_count,
            )
        )
    return results
