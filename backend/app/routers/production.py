from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.deps import ensure_exists
from app.models.order import Order
from app.models.production import ProductionRecord, ProductionProgress, ProductionMaterialIssue

router = APIRouter(prefix="/api/production", tags=["production"])


# ---- Key dates ----
class ProductionRecordIn(BaseModel):
    order_id: int | None = None
    launch_time: datetime | None = None
    pre_production_sample_time: datetime | None = None
    estimated_ship_time: datetime | None = None
    completed_time: datetime | None = None


class ProductionRecordOut(ProductionRecordIn):
    id: int

    class Config:
        from_attributes = True


@router.get("/records", response_model=list[ProductionRecordOut])
def list_production_records(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(ProductionRecord).order_by(ProductionRecord.id.desc()).all()


@router.post("/records", response_model=ProductionRecordOut)
def create_production_record(payload: ProductionRecordIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    ensure_exists(db, Order, payload.order_id, "Order")
    record = ProductionRecord(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/records/{record_id}", response_model=ProductionRecordOut)
def update_production_record(
    record_id: int, payload: ProductionRecordIn, db: Session = Depends(get_db), _=Depends(get_current_user)
):
    record = db.get(ProductionRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Production record not found")
    if "order_id" in payload.model_fields_set:
        ensure_exists(db, Order, payload.order_id, "Order")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


# ---- Daily progress ----
class ProductionProgressIn(BaseModel):
    order_id: int | None = None
    process_step: str
    record_date: date = Field(default_factory=date.today)
    status: str = "in_progress"


class ProductionProgressOut(ProductionProgressIn):
    id: int

    class Config:
        from_attributes = True


@router.get("/progress", response_model=list[ProductionProgressOut])
def list_production_progress(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(ProductionProgress).order_by(ProductionProgress.record_date.desc()).all()


@router.post("/progress", response_model=ProductionProgressOut)
def add_production_progress(payload: ProductionProgressIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    ensure_exists(db, Order, payload.order_id, "Order")
    entry = ProductionProgress(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ---- Material issues ----
class MaterialIssueIn(BaseModel):
    order_id: int | None = None
    description: str


class MaterialIssueOut(MaterialIssueIn):
    id: int
    reported_at: datetime
    resolved: bool

    class Config:
        from_attributes = True


@router.get("/material-issues", response_model=list[MaterialIssueOut])
def list_material_issues(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(ProductionMaterialIssue).order_by(ProductionMaterialIssue.reported_at.desc()).all()


@router.post("/material-issues", response_model=MaterialIssueOut)
def report_material_issue(payload: MaterialIssueIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    ensure_exists(db, Order, payload.order_id, "Order")
    issue = ProductionMaterialIssue(**payload.model_dump())
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


@router.post("/material-issues/{issue_id}/resolve", response_model=MaterialIssueOut)
def resolve_material_issue(issue_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    issue = db.get(ProductionMaterialIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    issue.resolved = True
    db.commit()
    db.refresh(issue)
    return issue
