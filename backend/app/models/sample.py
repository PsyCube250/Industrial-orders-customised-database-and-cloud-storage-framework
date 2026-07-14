from datetime import datetime, date

from sqlalchemy import String, Integer, Numeric, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class Sample(Base, TimestampMixin):
    __tablename__ = "samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="assigned")

    order = relationship("Order")
    assignee = relationship("User")
    photos: Mapped[list["SamplePhoto"]] = relationship(cascade="all, delete-orphan")
    shipments: Mapped[list["SampleShipment"]] = relationship(cascade="all, delete-orphan")
    confirmations: Mapped[list["SampleConfirmation"]] = relationship(cascade="all, delete-orphan")
    materials: Mapped[list["SampleMaterial"]] = relationship(cascade="all, delete-orphan")


class SamplePhoto(Base):
    __tablename__ = "sample_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"))
    photo_path: Mapped[str] = mapped_column(String(500))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SampleShipment(Base):
    __tablename__ = "sample_shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"))
    tracking_no: Mapped[str] = mapped_column(String(128))
    shipped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SampleConfirmation(Base):
    __tablename__ = "sample_confirmations"

    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"))
    result: Mapped[str] = mapped_column(String(16))  # pass/fail
    proof_path: Mapped[str] = mapped_column(String(500), default="")
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SampleMaterial(Base):
    __tablename__ = "sample_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"))
    material_name: Mapped[str] = mapped_column(String(128))
    spec: Mapped[str] = mapped_column(String(128), default="")
    unit: Mapped[str] = mapped_column(String(32), default="")
    qty_per_unit: Mapped[float] = mapped_column(Numeric(12, 3), default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
