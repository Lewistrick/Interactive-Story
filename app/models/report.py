"""User reports on story parts."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Report(Base):
    """A single user's report of a story part for moderator review."""

    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("reporter_id", "story_part_id", name="unique_reporter_story_report"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    reporter_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    story_part_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("story_parts.id"), nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Report(id={self.id}, reporter_id={self.reporter_id}, "
            f"story_part_id={self.story_part_id})>"
        )
