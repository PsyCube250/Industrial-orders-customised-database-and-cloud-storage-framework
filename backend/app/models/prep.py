from datetime import date

from sqlalchemy import String, Integer, Numeric, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class PrepTask(Base, TimestampMixin):
    """Cutting / material-prep task, auto-generated per spec item 4.1."""

    __tablename__ = "prep_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    process_name: Mapped[str] = mapped_column(String(128))
    assigned_worker_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")

    order = relationship("Order")
    worker = relationship("User")
    subtasks: Mapped[list["PrepSubtask"]] = relationship(cascade="all, delete-orphan")


class PrepSubtask(Base):
    __tablename__ = "prep_subtasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    prep_task_id: Mapped[int] = mapped_column(ForeignKey("prep_tasks.id"))
    name: Mapped[str] = mapped_column(String(128))
    percent_complete: Mapped[int] = mapped_column(Integer, default=0)
