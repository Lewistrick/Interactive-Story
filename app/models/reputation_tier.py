from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.session import Base


class ReputationTier(Base):
    __tablename__ = "reputation_tiers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)
    min_score = Column(Integer, nullable=False)
    max_teaser_length = Column(Integer, nullable=False)
    max_content_length = Column(Integer, nullable=False)
    daily_part_limit = Column(Integer, nullable=False)
    min_parts_between_own = Column(Integer, nullable=False)
    can_vote_threshold = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self):
        return f"<ReputationTier(name='{self.name}', min_score={self.min_score})>"
