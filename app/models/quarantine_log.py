"""Quarantine audit log model."""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EntityType(str, enum.Enum):
    """What kind of entity a quarantine log refers to."""

    USER = "USER"
    STORY_PART = "STORY_PART"


class ResolutionAction(str, enum.Enum):
    """How a quarantine item was resolved."""

    ALLOWED = "ALLOWED"
    REMOVED = "REMOVED"
    BLOCKED = "BLOCKED"
    WARNED = "WARNED"


class QuarantineLog(Base):
    """Record of an automatic or manual quarantine action."""

    __tablename__ = "quarantine_logs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    entity_type: Mapped[EntityType] = mapped_column(SQLEnum(EntityType), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    triggered_by: Mapped[str] = mapped_column(String, nullable=False)
    automatic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    resolved_by_moderator_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    resolution_action: Mapped[ResolutionAction | None] = mapped_column(
        SQLEnum(ResolutionAction), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<QuarantineLog(id={self.id}, entity_type={self.entity_type}, "
            f"entity_id={self.entity_id})>"
        )
