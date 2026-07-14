from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class PackagingTask(Base, TimestampMixin):
    __tablename__ = "packaging_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/packed/qc_done

    order = relationship("Order")
    qc_records: Mapped[list["PackagingQC"]] = relationship(cascade="all, delete-orphan")


class PackagingQC(Base):
    __tablename__ = "packaging_qc"

    id: Mapped[int] = mapped_column(primary_key=True)
    packaging_task_id: Mapped[int] = mapped_column(ForeignKey("packaging_tasks.id"))
    quantity_checked: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str] = mapped_column(String(16), default="pending")  # pass/fail/pending
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
