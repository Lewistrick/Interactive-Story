from sqlalchemy import Column, String, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    reputation_score = Column(Integer, default=0, nullable=False)
    is_quarantined = Column(Boolean, default=False, nullable=False)
    quarantine_reason = Column(String, nullable=True)
    quarantined_at = Column(DateTime(timezone=True), nullable=True)
    quarantine_until = Column(DateTime(timezone=True), nullable=True)
    is_moderator = Column(Boolean, default=False, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self):
        return (
            f"<User(id={self.id}, username='{self.username}', reputation={self.reputation_score})>"
        )
