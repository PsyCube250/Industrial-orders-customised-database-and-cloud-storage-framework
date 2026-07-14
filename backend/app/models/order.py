from datetime import datetime, date

from sqlalchemy import String, Integer, Date, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

# Fixed pipeline of steps an order moves through; used to seed OrderProgressStep rows
# and to drive the tracking progress bar / timeout escalation.
ORDER_WORKFLOW_STEPS = [
    "样品制作",  # Sample production
    "采购备料",  # Procurement / material prep
    "生产",      # Production
    "包装",      # Packaging
    "出货",      # Shipping
]


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(128), index=True)
    product_name: Mapped[str] = mapped_column(String(128), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="in_progress"
    )  # in_progress/paused/cancelled/completed
    notes: Mapped[str] = mapped_column(Text, default="")

    attachments: Mapped[list["OrderAttachment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    progress_steps: Mapped[list["OrderProgressStep"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderProgressStep.sequence"
    )
    change_logs: Mapped[list["OrderChangeLog"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderAttachment(Base):
    __tablename__ = "order_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order: Mapped["Order"] = relationship(back_populates="attachments")


class OrderProgressStep(Base):
    """One row per workflow step per order, drives the tracking progress bar."""

    __tablename__ = "order_progress_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    step_name: Mapped[str] = mapped_column(String(128))
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/in_progress/done
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="progress_steps")

    @property
    def is_overdue(self) -> bool:
        if self.status == "done" or self.due_at is None:
            return False
        return datetime.utcnow() > self.due_at


class OrderChangeLog(Base):
    __tablename__ = "order_change_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    change_type: Mapped[str] = mapped_column(String(32))  # delivery_date/cancel/pause/resume
    old_value: Mapped[str] = mapped_column(String(255), default="")
    new_value: Mapped[str] = mapped_column(String(255), default="")
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order: Mapped["Order"] = relationship(back_populates="change_logs")
