"""Pydantic schemas for reports and moderator quarantine workflows."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.quarantine_log import EntityType, ResolutionAction


class ReportCreate(BaseModel):
    """Optional reason when reporting a story part."""

    reason: Optional[str] = Field(None, max_length=512)


class ReportResponse(BaseModel):
    """Confirmation after submitting a report."""

    id: UUID
    story_part_id: UUID
    reporter_id: UUID
    reason: Optional[str] = None
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
    resolved_by_moderator_id: Optional[UUID] = None
    resolution_action: Optional[ResolutionAction] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    # Enriched preview (populated for STORY_PART / USER when the entity still exists)
    author_username: Optional[str] = None
    author_id: Optional[UUID] = None
    teaser: Optional[str] = None
    content_preview: Optional[str] = None

    model_config = {"from_attributes": True}


class BlockUserRequest(BaseModel):
    """Optional reason when blocking a user."""

    reason: Optional[str] = Field("Blocked by moderator", max_length=512)


class WarnUserRequest(BaseModel):
    """Warning message and optional temporary quarantine duration."""

    reason: str = Field(..., min_length=1, max_length=512)
    duration_hours: Optional[float] = Field(None, gt=0, le=24 * 30)
