from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import enum
from app.db.session import Base


class VoteType(str, enum.Enum):
    UP = "UP"
    DOWN = "DOWN"


class StoryPart(Base):
    __tablename__ = "story_parts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_part_id = Column(UUID(as_uuid=True), ForeignKey("story_parts.id"), nullable=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    teaser = Column(String, nullable=False)
    content = Column(String, nullable=False)
    vote_score = Column(Integer, default=0, nullable=False)
    recursive_score = Column(Integer, default=0, nullable=False)
    is_quarantined = Column(Boolean, default=False, nullable=False)
    quarantine_reason = Column(String, nullable=True)
    quarantined_at = Column(DateTime(timezone=True), nullable=True)
    depth_level = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    author = relationship("User", backref="story_parts")
    parent = relationship("StoryPart", remote_side=[id], backref="children")
    votes = relationship("Vote", back_populates="story_part", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<StoryPart(id={self.id}, teaser='{self.teaser[:20]}...', author_id={self.author_id})>"
        )
