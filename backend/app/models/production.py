from datetime import datetime, date

from sqlalchemy import String, Date, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class ProductionRecord(Base, TimestampMixin):
    """Key dates for an order's production run, spec item 5.1."""

    __tablename__ = "production_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    launch_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pre_production_sample_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    estimated_ship_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    order = relationship("Order")


class ProductionProgress(Base):
    """Daily record of which process step a product reached, spec item 5.2."""

    __tablename__ = "production_progress"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    process_step: Mapped[str] = mapped_column(String(128))
    record_date: Mapped[date] = mapped_column(Date, default=date.today)
    status: Mapped[str] = mapped_column(String(32), default="in_progress")

    order = relationship("Order")


class ProductionMaterialIssue(Base):
    """Real-time feedback on material errors/shortages during production, spec item 5.3."""

    __tablename__ = "production_material_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    reported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    order = relationship("Order")
