from datetime import datetime

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class TimeoutRule(Base, TimestampMixin):
    __tablename__ = "timeout_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    step_name: Mapped[str] = mapped_column(String(128))
    days_allowed: Mapped[int] = mapped_column(Integer, default=1)
    warning_threshold_days: Mapped[int] = mapped_column(Integer, default=1)


class EscalationRule(Base, TimestampMixin):
    __tablename__ = "escalation_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    step_name: Mapped[str] = mapped_column(String(128))
    overdue_days: Mapped[int] = mapped_column(Integer)
    notify_role: Mapped[str] = mapped_column(String(32))  # e.g. supervisor, director


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    message: Mapped[str] = mapped_column(String(500))
    level: Mapped[str] = mapped_column(String(16), default="info")  # info/warning/critical
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship()
