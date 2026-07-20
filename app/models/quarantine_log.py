from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum
from app.db.session import Base


class EntityType(str, enum.Enum):
    USER = "USER"
    STORY_PART = "STORY_PART"


class ResolutionAction(str, enum.Enum):
    ALLOWED = "ALLOWED"
    REMOVED = "REMOVED"
    BLOCKED = "BLOCKED"


class QuarantineLog(Base):
    __tablename__ = "quarantine_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(SQLEnum(EntityType), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    reason = Column(String, nullable=False)
    triggered_by = Column(String, nullable=False)  # system rule name or moderator_id
    automatic = Column(Boolean, default=True, nullable=False)
    resolved_by_moderator_id = Column(UUID(as_uuid=True), nullable=True)
    resolution_action = Column(SQLEnum(ResolutionAction), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<QuarantineLog(id={self.id}, entity_type={self.entity_type}, entity_id={self.entity_id})>"
