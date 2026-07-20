from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.session import Base


class UserDailyLimit(Base):
    __tablename__ = "user_daily_limits"
    __table_args__ = (UniqueConstraint("user_id", "date", name="unique_user_date"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    parts_written = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self):
        return f"<UserDailyLimit(user_id={self.user_id}, date={self.date}, parts_written={self.parts_written})>"
