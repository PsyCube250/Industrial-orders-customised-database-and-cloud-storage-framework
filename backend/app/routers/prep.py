from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.deps import ensure_exists
from app.models.order import Order
from app.models.prep import PrepTask, PrepSubtask
from app.models.system import User

router = APIRouter(prefix="/api/prep", tags=["prep"])


class PrepSubtaskIn(BaseModel):
    name: str
    percent_complete: int = Field(0, ge=0, le=100)


class PrepSubtaskUpdate(BaseModel):
    name: str | None = None
    percent_complete: int | None = Field(None, ge=0, le=100)


class PrepSubtaskOut(PrepSubtaskIn):
    id: int

    class Config:
        from_attributes = True


class PrepTaskCreate(BaseModel):
    order_id: int | None = None
    process_name: str
    assigned_worker_id: int | None = None
    due_date: date | None = None


class PrepTaskOut(BaseModel):
    id: int
    order_id: int | None
    process_name: str
    assigned_worker_id: int | None
    due_date: date | None
    status: str

    class Config:
        from_attributes = True


class PrepTaskDetailOut(PrepTaskOut):
    subtasks: list[PrepSubtaskOut] = []


@router.get("", response_model=list[PrepTaskOut])
def list_prep_tasks(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(PrepTask).order_by(PrepTask.id.desc()).all()


@router.post("", response_model=PrepTaskOut)
def create_prep_task(payload: PrepTaskCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    ensure_exists(db, Order, payload.order_id, "Order")
    ensure_exists(db, User, payload.assigned_worker_id, "User")
    task = PrepTask(**payload.model_dump(), status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=PrepTaskDetailOut)
def get_prep_task(task_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    task = (
        db.query(PrepTask).options(joinedload(PrepTask.subtasks)).filter(PrepTask.id == task_id).first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Prep task not found")
    return task


@router.post("/{task_id}/subtasks", response_model=PrepTaskDetailOut)
def add_subtask(task_id: int, payload: PrepSubtaskIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    task = db.get(PrepTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Prep task not found")
    db.add(PrepSubtask(prep_task_id=task_id, **payload.model_dump()))
    db.flush()
    _refresh_task_status(task)
    db.commit()
    db.refresh(task)
    return task


def _refresh_task_status(task: PrepTask) -> None:
    if task.subtasks and all(s.percent_complete >= 100 for s in task.subtasks):
        task.status = "done"
    else:
        task.status = "in_progress"


@router.patch("/{task_id}/subtasks/{subtask_id}", response_model=PrepTaskDetailOut)
def update_subtask(
    task_id: int,
    subtask_id: int,
    payload: PrepSubtaskUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    task = db.get(PrepTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Prep task not found")
    subtask = db.get(PrepSubtask, subtask_id)
    if not subtask or subtask.prep_task_id != task_id:
        raise HTTPException(status_code=404, detail="Subtask not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(subtask, field, value)
    db.flush()
    _refresh_task_status(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}/completion")
def completion_dashboard(task_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Subtask completion percentage, per spec item 4.3."""
    task = (
        db.query(PrepTask).options(joinedload(PrepTask.subtasks)).filter(PrepTask.id == task_id).first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Prep task not found")
    if not task.subtasks:
        return {"percent_complete": 0, "is_overdue": False}
    avg = sum(s.percent_complete for s in task.subtasks) / len(task.subtasks)
    is_overdue = bool(task.due_date and date.today() > task.due_date and avg < 100)
    return {"percent_complete": round(avg, 1), "is_overdue": is_overdue}
