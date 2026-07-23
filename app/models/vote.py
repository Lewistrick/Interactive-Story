"""Vote ORM model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.story_part import VoteType


class Vote(Base):
    """A user's up/down vote on a story part."""

    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("user_id", "story_part_id", name="unique_user_story_vote"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    story_part_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("story_parts.id"), nullable=False)
    vote_type: Mapped[VoteType] = mapped_column(SQLEnum(VoteType), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", backref="votes")
    story_part = relationship("StoryPart", back_populates="votes")

    def __repr__(self) -> str:
        return (
            f"<Vote(id={self.id}, user_id={self.user_id}, "
            f"story_part_id={self.story_part_id}, type={self.vote_type})>"
        )
