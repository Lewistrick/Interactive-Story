from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(UserBase):
    id: UUID
    reputation_score: int
    is_quarantined: bool
    quarantine_reason: Optional[str] = None
    quarantine_until: Optional[datetime] = None
    is_moderator: bool
    is_blocked: bool
    created_at: datetime
    updated_at: datetime
    # Reputation tier limits (populated by /auth/me and register enrichment)
    tier_name: Optional[str] = None
    max_teaser_length: Optional[int] = None
    max_content_length: Optional[int] = None
    daily_part_limit: Optional[int] = None
    min_parts_between_own: Optional[int] = None
    can_vote: Optional[bool] = None
    parts_written_today: Optional[int] = None
    can_create_root: Optional[bool] = None
    min_reputation_create_root: Optional[int] = None
    open_root_trees: Optional[int] = None
    max_concurrent_open_trees: Optional[int] = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
