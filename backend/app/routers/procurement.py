from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.deps import ensure_exists
from app.models.procurement import (
    Supplier,
    PurchaseRequirement,
    PurchaseOrder,
    PurchaseOrderItem,
    MaterialInbound,
)
from app.models.sample import SampleMaterial

router = APIRouter(prefix="/api/procurement", tags=["procurement"])


# ---- Suppliers ----
class SupplierIn(BaseModel):
    name: str
    contact_name: str = ""
    phone: str = ""
    address: str = ""
    notes: str = ""


class SupplierOut(SupplierIn):
    id: int

    class Config:
        from_attributes = True


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Supplier).order_by(Supplier.id).all()


@router.post("/suppliers", response_model=SupplierOut)
def create_supplier(payload: SupplierIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: int, payload: SupplierIn, db: Session = Depends(get_db), _=Depends(get_current_user)
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for field, value in payload.model_dump().items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.delete("/suppliers/{supplier_id}")
def delete_supplier(supplier_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    # Detach purchase orders first so the delete doesn't violate the FK (Postgres enforces it)
    db.query(PurchaseOrder).filter(PurchaseOrder.supplier_id == supplier_id).update({"supplier_id": None})
    db.delete(supplier)
    db.commit()
    return {"ok": True}


# ---- Purchase requirements (auto-generated from sample material list) ----
class PurchaseRequirementOut(BaseModel):
    id: int
    order_id: int | None
    material_name: str
    required_qty: float
    unit: str
    fulfilled: bool

    class Config:
        from_attributes = True


@router.post("/requirements/generate/{order_id}", response_model=list[PurchaseRequirementOut])
def generate_purchase_requirements(order_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Reads the order's sample material list and computes required purchase quantities,
    per spec item 3.1 (采购需求生成: 读取材料清单，自动计算采购量)."""
    from app.models.sample import Sample
    from app.models.order import Order

    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order_qty = order.quantity or 1

    rows = (
        db.query(SampleMaterial)
        .join(Sample, Sample.id == SampleMaterial.sample_id)
        .filter(Sample.order_id == order_id)
        .all()
    )

    # Regenerating replaces any unfulfilled requirements for this order instead of duplicating
    # them; materials already fulfilled are kept as-is and not re-added
    db.query(PurchaseRequirement).filter(
        PurchaseRequirement.order_id == order_id, PurchaseRequirement.fulfilled.is_(False)
    ).delete()
    fulfilled_names = {
        r.material_name
        for r in db.query(PurchaseRequirement)
        .filter(PurchaseRequirement.order_id == order_id, PurchaseRequirement.fulfilled.is_(True))
        .all()
    }

    created = []
    for m in rows:
        if m.material_name in fulfilled_names:
            continue
        req = PurchaseRequirement(
            order_id=order_id,
            material_name=m.material_name,
            required_qty=float(m.qty_per_unit) * order_qty,
            unit=m.unit,
        )
        db.add(req)
        created.append(req)
    db.commit()
    for req in created:
        db.refresh(req)
    return created


@router.get("/requirements", response_model=list[PurchaseRequirementOut])
def list_purchase_requirements(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(PurchaseRequirement).order_by(PurchaseRequirement.id.desc()).all()


# ---- Purchase orders ----
class PurchaseOrderItemIn(BaseModel):
    material_name: str
    qty: float = Field(gt=0)
    unit_price: float = Field(0, ge=0)


class PurchaseOrderItemOut(PurchaseOrderItemIn):
    id: int

    class Config:
        from_attributes = True


class PurchaseOrderCreate(BaseModel):
    supplier_id: int | None = None
    planned_arrival_date: date | None = None
    items: list[PurchaseOrderItemIn] = []


class PurchaseOrderOut(BaseModel):
    id: int
    po_no: str
    supplier_id: int | None
    planned_arrival_date: date | None
    status: str
    items: list[PurchaseOrderItemOut] = []

    class Config:
        from_attributes = True


def _next_po_no(db: Session) -> str:
    today_prefix = f"PO{datetime.utcnow():%Y%m%d}"
    last = (
        db.query(PurchaseOrder.po_no)
        .filter(PurchaseOrder.po_no.like(f"{today_prefix}%"))
        # length before value: once the sequence outgrows its 4-digit padding,
        # plain string ordering would put e.g. 9999 above 10000
        .order_by(func.length(PurchaseOrder.po_no).desc(), PurchaseOrder.po_no.desc())
        .first()
    )
    seq = int(last[0][len(today_prefix):]) + 1 if last else 1
    return f"{today_prefix}{seq:04d}"


@router.get("/purchase-orders", response_model=list[PurchaseOrderOut])
def list_purchase_orders(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items)).order_by(PurchaseOrder.id.desc()).all()


@router.post("/purchase-orders", response_model=PurchaseOrderOut)
def create_purchase_order(payload: PurchaseOrderCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    ensure_exists(db, Supplier, payload.supplier_id, "Supplier")
    # savepoint + retry: a concurrent request may grab the same po_no (unique constraint)
    last_exc = None
    for _ in range(3):
        try:
            with db.begin_nested():
                po = PurchaseOrder(
                    po_no=_next_po_no(db),
                    supplier_id=payload.supplier_id,
                    planned_arrival_date=payload.planned_arrival_date,
                )
                db.add(po)
                db.flush()
                for item in payload.items:
                    db.add(PurchaseOrderItem(purchase_order_id=po.id, **item.model_dump()))
            db.commit()
            db.refresh(po)
            return po
        except IntegrityError as exc:
            last_exc = exc
    raise HTTPException(status_code=409, detail="Could not allocate a PO number, please retry") from last_exc


# ---- Material inbound (registers qty + QC result) ----
class MaterialInboundIn(BaseModel):
    purchase_order_item_id: int
    qty_received: float = Field(gt=0)
    qc_result: Literal["pass", "fail", "pending"] = "pending"


class MaterialInboundOut(MaterialInboundIn):
    id: int
    received_at: datetime

    class Config:
        from_attributes = True


def _passed_qty(db: Session, material_name: str) -> float:
    """Total quantity received with QC pass for a material, across all PO items."""
    total = (
        db.query(func.coalesce(func.sum(MaterialInbound.qty_received), 0))
        .join(PurchaseOrderItem, PurchaseOrderItem.id == MaterialInbound.purchase_order_item_id)
        .filter(PurchaseOrderItem.material_name == material_name, MaterialInbound.qc_result == "pass")
        .scalar()
    )
    return float(total or 0)


def _apply_fulfillment(db: Session, material_name: str) -> None:
    """Marks purchase requirements fulfilled once enough QC-passed material has arrived.
    Received quantity is allocated to requirements oldest-first."""
    available = _passed_qty(db, material_name)
    already_allocated = (
        db.query(func.coalesce(func.sum(PurchaseRequirement.required_qty), 0))
        .filter(PurchaseRequirement.material_name == material_name, PurchaseRequirement.fulfilled.is_(True))
        .scalar()
    )
    available -= float(already_allocated or 0)
    pending = (
        db.query(PurchaseRequirement)
        .filter(PurchaseRequirement.material_name == material_name, PurchaseRequirement.fulfilled.is_(False))
        .order_by(PurchaseRequirement.id)
        .all()
    )
    for req in pending:
        needed = float(req.required_qty)
        if available < needed:
            break
        req.fulfilled = True
        available -= needed


def _refresh_po_status(db: Session, purchase_order_id: int) -> None:
    """Closes a PO as received/late once every item is fully received with QC pass."""
    po = db.get(PurchaseOrder, purchase_order_id)
    if not po:
        return
    for item in po.items:
        received = (
            db.query(func.coalesce(func.sum(MaterialInbound.qty_received), 0))
            .filter(MaterialInbound.purchase_order_item_id == item.id, MaterialInbound.qc_result == "pass")
            .scalar()
        )
        if float(received or 0) < float(item.qty):
            return
    on_time = po.planned_arrival_date is None or datetime.utcnow().date() <= po.planned_arrival_date
    po.status = "received" if on_time else "late"


@router.post("/inbound", response_model=MaterialInboundOut)
def register_inbound(payload: MaterialInboundIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    item = db.get(PurchaseOrderItem, payload.purchase_order_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Purchase order item not found")
    inbound = MaterialInbound(**payload.model_dump())
    db.add(inbound)
    db.flush()
    _apply_fulfillment(db, item.material_name)
    _refresh_po_status(db, item.purchase_order_id)
    db.commit()
    db.refresh(inbound)
    return inbound


# ---- Shortage alerts: requirements not yet fulfilled ----
@router.get("/shortages", response_model=list[PurchaseRequirementOut])
def list_shortages(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(PurchaseRequirement).filter(PurchaseRequirement.fulfilled.is_(False)).all()


# ---- Purchase report: on-time rate ----
@router.get("/report/on-time-rate")
def purchase_on_time_rate(db: Session = Depends(get_db), _=Depends(get_current_user)):
    # "received" = closed on time, "late" = closed after the planned arrival date
    closed = db.query(PurchaseOrder).filter(PurchaseOrder.status.in_(("received", "late"))).all()
    if not closed:
        return {"on_time_rate": 0.0, "sample_size": 0}
    on_time = sum(1 for po in closed if po.status == "received")
    return {"on_time_rate": round(on_time / len(closed) * 100, 1), "sample_size": len(closed)}
