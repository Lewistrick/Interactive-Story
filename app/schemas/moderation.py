"""Pydantic schemas for reports and moderator quarantine workflows."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.quarantine_log import EntityType, ResolutionAction


class ReportCreate(BaseModel):
    """Optional reason when reporting a story part."""

    reason: str | None = Field(None, max_length=512)


class ReportResponse(BaseModel):
    """Confirmation after submitting a report."""

    id: UUID
    story_part_id: UUID
    reporter_id: UUID
    reason: str | None = None
    created_at: datetime
    quarantined: bool = False
    report_count: int = 1

    model_config = {"from_attributes": True}


class QuarantineLogResponse(BaseModel):
    """Quarantine log row for the moderator queue / audit log."""

    id: UUID
    entity_type: EntityType
    entity_id: UUID
    reason: str
    triggered_by: str
    automatic: bool
    resolved_by_moderator_id: UUID | None = None
    resolution_action: ResolutionAction | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    # Enriched preview (populated for STORY_PART / USER when the entity still exists)
    author_username: str | None = None
    author_id: UUID | None = None
    teaser: str | None = None
    content_preview: str | None = None

    model_config = {"from_attributes": True}


class BlockUserRequest(BaseModel):
    """Optional reason when blocking a user."""

    reason: str | None = Field("Blocked by moderator", max_length=512)


class WarnUserRequest(BaseModel):
    """Warning message and optional temporary quarantine duration."""

    reason: str = Field(..., min_length=1, max_length=512)
    duration_hours: float | None = Field(None, gt=0, le=24 * 30)


class BulkModerationItem(BaseModel):
    """One target for a bulk moderation action."""

    entity_type: EntityType
    entity_id: UUID


class BulkModerationRequest(BaseModel):
    """Bulk allow / remove / block on queue items."""

    action: str = Field(..., pattern="^(allow|remove|block)$")
    items: list[BulkModerationItem] = Field(..., min_length=1, max_length=50)


class BulkModerationResponse(BaseModel):
    """Summary of a bulk moderation run."""

    processed: int
    failed: int
    errors: list[str] = []


class VotingPatternFlag(BaseModel):
    """A suspicious voting pattern for moderator review."""

    user_id: UUID
    username: str
    flag: str
    detail: str
    reputation_score: int


class ReputationPoint(BaseModel):
    """One point on a reputation history sparkline."""

    score: int
    created_at: datetime
