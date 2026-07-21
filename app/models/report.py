"""User reports on story parts."""

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class Report(Base):
    """A single user's report of a story part for moderator review."""

    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("reporter_id", "story_part_id", name="unique_reporter_story_report"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    story_part_id = Column(UUID(as_uuid=True), ForeignKey("story_parts.id"), nullable=False)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<Report(id={self.id}, reporter_id={self.reporter_id}, "
            f"story_part_id={self.story_part_id})>"
        )
