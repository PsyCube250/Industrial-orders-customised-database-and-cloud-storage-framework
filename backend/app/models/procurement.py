from datetime import datetime, date

from sqlalchemy import String, Integer, Numeric, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    contact_name: Mapped[str] = mapped_column(String(128), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    address: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class PurchaseRequirement(Base, TimestampMixin):
    """Auto-calculated from an order's sample material list."""

    __tablename__ = "purchase_requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    material_name: Mapped[str] = mapped_column(String(128))
    required_qty: Mapped[float] = mapped_column(Numeric(12, 3), default=0)
    unit: Mapped[str] = mapped_column(String(32), default="")
    fulfilled: Mapped[bool] = mapped_column(default=False)

    order = relationship("Order")


class PurchaseOrder(Base, TimestampMixin):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    po_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    planned_arrival_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open")  # open/received/late

    supplier = relationship("Supplier")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"))
    material_name: Mapped[str] = mapped_column(String(128))
    qty: Mapped[float] = mapped_column(Numeric(12, 3), default=0)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)


class MaterialInbound(Base):
    __tablename__ = "material_inbound"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_item_id: Mapped[int] = mapped_column(ForeignKey("purchase_order_items.id"))
    qty_received: Mapped[float] = mapped_column(Numeric(12, 3), default=0)
    qc_result: Mapped[str] = mapped_column(String(16), default="pending")  # pass/fail/pending
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
