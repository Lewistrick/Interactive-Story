from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.story_part import VoteType


class StoryPartBase(BaseModel):
    teaser: str = Field(..., min_length=1, max_length=512)
    content: str = Field(..., min_length=1, max_length=2048)


class StoryPartCreate(StoryPartBase):
    parent_part_id: UUID | None = None


class StoryPartUpdate(BaseModel):
    teaser: str | None = Field(None, min_length=1, max_length=512)
    content: str | None = Field(None, min_length=1, max_length=2048)


class StoryPartResponse(StoryPartBase):
    id: UUID
    parent_part_id: UUID | None
    author_id: UUID
    vote_score: int
    recursive_score: int
    is_quarantined: bool
    quarantine_reason: str | None = None
    depth_level: int
    created_at: datetime
    updated_at: datetime
    author_username: str | None = None
    children_count: int = 0
    user_vote: VoteType | None = None

    model_config = {"from_attributes": True}


class StoryPartTree(StoryPartResponse):
    children: list["StoryPartTree"] = []


class VoteCreate(BaseModel):
    vote_type: VoteType


class VoteResponse(BaseModel):
    id: UUID
    user_id: UUID
    story_part_id: UUID
    vote_type: VoteType
    created_at: datetime
    removed: bool = False

    model_config = {"from_attributes": True}


class VoteActionResponse(BaseModel):
    """Response for vote create/update/remove actions."""

    id: UUID | None = None
    user_id: UUID | None = None
    story_part_id: UUID
    vote_type: VoteType | None = None
    created_at: datetime | None = None
    removed: bool = False
    vote_score: int


class StoryListResponse(BaseModel):
    id: UUID
    teaser: str
    author_id: UUID
    vote_score: int
    recursive_score: int
    created_at: datetime
    author_username: str | None = None
    children_count: int = 0

    model_config = {"from_attributes": True}
