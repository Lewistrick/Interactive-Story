"""Periodic reputation score snapshots for moderator charts."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class ReputationSnapshot(Base):
    """Point-in-time reputation score after a recalculation."""

    __tablename__ = "reputation_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    score = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<ReputationSnapshot(user_id={self.user_id}, score={self.score})>"
