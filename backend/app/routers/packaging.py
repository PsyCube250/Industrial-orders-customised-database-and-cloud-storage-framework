from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.deps import ensure_exists
from app.models.order import Order
from app.models.packaging import PackagingTask, PackagingQC

router = APIRouter(prefix="/api/packaging", tags=["packaging"])


class PackagingTaskCreate(BaseModel):
    order_id: int | None = None


class PackagingQCOut(BaseModel):
    id: int
    quantity_checked: int
    result: str
    checked_at: datetime

    class Config:
        from_attributes = True


class PackagingTaskOut(BaseModel):
    id: int
    order_id: int | None
    status: str

    class Config:
        from_attributes = True


class PackagingTaskDetailOut(PackagingTaskOut):
    qc_records: list[PackagingQCOut] = []


@router.get("", response_model=list[PackagingTaskOut])
def list_packaging_tasks(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(PackagingTask).order_by(PackagingTask.id.desc()).all()


@router.post("", response_model=PackagingTaskOut)
def create_packaging_task(payload: PackagingTaskCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    ensure_exists(db, Order, payload.order_id, "Order")
    task = PackagingTask(order_id=payload.order_id, status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/pack", response_model=PackagingTaskOut)
def mark_packed(task_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    task = db.get(PackagingTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Packaging task not found")
    if task.status != "pending":
        raise HTTPException(status_code=400, detail=f"Task is already {task.status}")
    task.status = "packed"
    db.commit()
    db.refresh(task)
    return task


class PackagingQCIn(BaseModel):
    quantity_checked: int = Field(ge=0)
    result: Literal["pass", "fail"]


@router.post("/{task_id}/qc", response_model=PackagingTaskDetailOut)
def register_qc(task_id: int, payload: PackagingQCIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    task = db.get(PackagingTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Packaging task not found")
    if task.status not in ("packed", "qc_done"):
        raise HTTPException(status_code=400, detail="QC can only be registered after packing")
    db.add(PackagingQC(packaging_task_id=task_id, **payload.model_dump()))
    task.status = "qc_done"
    db.commit()
    db.refresh(task)
    return task
