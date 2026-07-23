"""Public and shared user-profile schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UserProfile(BaseModel):
    """Public user summary; mod-only fields are omitted for non-moderators."""

    id: UUID
    username: str
    reputation_score: int
    created_at: datetime
    authored_count: int
    # Present only when the viewer is a moderator.
    is_quarantined: bool | None = None
    quarantine_reason: str | None = None
    quarantine_until: datetime | None = None
    is_blocked: bool | None = None
    is_moderator: bool | None = None
    quarantined_parts_count: int | None = None
    votes_cast_count: int | None = None
    votes_up_count: int | None = None
    votes_down_count: int | None = None


class UserPart(BaseModel):
    """One authored story part on a user profile."""

    id: UUID
    teaser: str
    vote_score: int
    recursive_score: int
    depth_level: int
    is_quarantined: bool
    parent_part_id: UUID | None = None
    created_at: datetime
    children_count: int = 0

    model_config = {"from_attributes": True}
