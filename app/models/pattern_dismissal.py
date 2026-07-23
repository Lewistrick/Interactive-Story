"""Moderator dismissals for voting-pattern flags."""

from sqlalchemy import Column, String, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class PatternDismissal(Base):
    """Suppress a voting-pattern flag for a user until ``expires_at``.

    When ``expires_at`` is null, the dismissal never expires (until deleted).
    """

    __tablename__ = "pattern_dismissals"
    __table_args__ = (UniqueConstraint("user_id", "flag", name="unique_user_pattern_flag"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    flag = Column(String(64), nullable=False)
    dismissed_by_moderator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason = Column(String(512), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<PatternDismissal(user_id={self.user_id}, flag={self.flag!r})>"
