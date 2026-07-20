from sqlalchemy import Column, DateTime, ForeignKey, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.models.story_part import VoteType
from app.db.session import Base


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("user_id", "story_part_id", name="unique_user_story_vote"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    story_part_id = Column(UUID(as_uuid=True), ForeignKey("story_parts.id"), nullable=False)
    vote_type = Column(SQLEnum(VoteType), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", backref="votes")
    story_part = relationship("StoryPart", back_populates="votes")

    def __repr__(self):
        return f"<Vote(id={self.id}, user_id={self.user_id}, story_part_id={self.story_part_id}, type={self.vote_type})>"
