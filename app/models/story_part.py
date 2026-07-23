"""Story part and vote-type models."""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class VoteType(str, enum.Enum):
    """Up or down vote on a story part."""

    UP = "UP"
    DOWN = "DOWN"


class StoryPart(Base):
    """One node in a collaborative story tree."""

    __tablename__ = "story_parts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    parent_part_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("story_parts.id"), nullable=True
    )
    author_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    teaser: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    vote_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recursive_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_quarantined: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quarantine_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    quarantined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    depth_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    author = relationship("User", backref="story_parts")
    parent = relationship("StoryPart", remote_side=[id], backref="children")
    votes = relationship("Vote", back_populates="story_part", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"<StoryPart(id={self.id}, teaser='{self.teaser[:20]}...', author_id={self.author_id})>"
        )
