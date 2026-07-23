from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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
    quarantine_reason: str | None = None
    quarantine_until: datetime | None = None
    is_moderator: bool
    is_blocked: bool
    must_reset_password: bool = False
    created_at: datetime
    updated_at: datetime
    # Reputation tier limits (populated by /auth/me and register enrichment)
    tier_name: str | None = None
    max_teaser_length: int | None = None
    max_content_length: int | None = None
    daily_part_limit: int | None = None
    min_parts_between_own: int | None = None
    can_vote: bool | None = None
    parts_written_today: int | None = None
    can_create_root: bool | None = None
    min_reputation_create_root: int | None = None
    open_root_trees: int | None = None
    max_concurrent_open_trees: int | None = None

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    """Payload for changing the current user's password."""

    current_password: str
    new_password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    must_reset_password: bool = False


class TokenData(BaseModel):
    username: str | None = None
