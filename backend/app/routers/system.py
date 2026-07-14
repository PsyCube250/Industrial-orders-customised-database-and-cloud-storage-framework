from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, hash_password, require_role
from app.database import get_db
from app.deps import ensure_exists
from app.models.system import (
    User,
    ProductCategory,
    MaterialCategory,
    ProcessLibraryItem,
    OperationLog,
    StepOwner,
)
from app.models.notification import Notification
from app.models.order import OrderChangeLog
from app.models.prep import PrepTask
from app.models.sample import Sample
from app.schemas.auth import UserOut, UserCreate, UserUpdate

router = APIRouter(prefix="/api/system", tags=["system"])

ALLOWED_ROLES = {"admin", "supervisor", "director", "staff"}


def _other_active_admins(db: Session, user_id: int) -> int:
    return (
        db.query(User)
        .filter(User.role == "admin", User.is_active.is_(True), User.id != user_id)
        .count()
    )


# ---- Users ----
@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(User).order_by(User.id).all()


@router.post("/users", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    if payload.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(ALLOWED_ROLES)}")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        email=payload.email,
        phone=payload.phone,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # concurrent request created the same username between our check and the commit
        db.rollback()
        raise HTTPException(status_code=400, detail="Username already exists")
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = payload.model_dump(exclude_unset=True)
    if "role" in data and data["role"] not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(ALLOWED_ROLES)}")
    loses_admin = user.role == "admin" and user.is_active and (
        data.get("role", user.role) != "admin" or data.get("is_active", user.is_active) is False
    )
    if loses_admin and _other_active_admins(db, user_id) == 0:
        raise HTTPException(status_code=400, detail="Cannot demote or deactivate the last active admin")
    if "password" in data and data["password"]:
        user.hashed_password = hash_password(data.pop("password"))
    else:
        data.pop("password", None)
    for field, value in data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role("admin"))
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if user.role == "admin" and user.is_active and _other_active_admins(db, user_id) == 0:
        raise HTTPException(status_code=400, detail="Cannot delete the last active admin")
    # Null out references first so the delete doesn't violate FK constraints (Postgres enforces them)
    db.query(OperationLog).filter(OperationLog.user_id == user_id).update({"user_id": None})
    db.query(StepOwner).filter(StepOwner.user_id == user_id).update({"user_id": None})
    db.query(Notification).filter(Notification.user_id == user_id).update({"user_id": None})
    db.query(OrderChangeLog).filter(OrderChangeLog.changed_by == user_id).update({"changed_by": None})
    db.query(Sample).filter(Sample.assigned_to == user_id).update({"assigned_to": None})
    db.query(PrepTask).filter(PrepTask.assigned_worker_id == user_id).update({"assigned_worker_id": None})
    db.delete(user)
    db.commit()
    return {"ok": True}


# ---- Base data: product/material categories, process library ----
class NamedItemIn(BaseModel):
    name: str
    notes: str = ""


class NamedItemOut(NamedItemIn):
    id: int

    class Config:
        from_attributes = True


def _named_item_crud(router: APIRouter, path: str, model):
    slug = path.replace("-", "_")

    def list_items(db: Session = Depends(get_db), _=Depends(get_current_user)):
        return db.query(model).order_by(model.id).all()

    def create_item(payload: NamedItemIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
        item = model(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def delete_item(item_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
        item = db.get(model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Not found")
        db.delete(item)
        db.commit()
        return {"ok": True}

    # unique function names keep the OpenAPI operation ids from colliding between models
    list_items.__name__ = f"list_{slug}"
    create_item.__name__ = f"create_{slug}"
    delete_item.__name__ = f"delete_{slug}"
    router.get(f"/{path}", response_model=list[NamedItemOut])(list_items)
    router.post(f"/{path}", response_model=NamedItemOut)(create_item)
    router.delete(f"/{path}/{{item_id}}")(delete_item)


_named_item_crud(router, "product-categories", ProductCategory)
_named_item_crud(router, "material-categories", MaterialCategory)


class ProcessLibraryOut(BaseModel):
    id: int
    name: str
    description: str

    class Config:
        from_attributes = True


class ProcessLibraryIn(BaseModel):
    name: str
    description: str = ""


@router.get("/process-library", response_model=list[ProcessLibraryOut])
def list_process_library(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(ProcessLibraryItem).order_by(ProcessLibraryItem.id).all()


@router.post("/process-library", response_model=ProcessLibraryOut)
def create_process_library_item(
    payload: ProcessLibraryIn, db: Session = Depends(get_db), _=Depends(get_current_user)
):
    item = ProcessLibraryItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ---- Operation logs (read-only) ----
class OperationLogOut(BaseModel):
    id: int
    user_id: int | None
    action: str
    target: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/operation-logs", response_model=list[OperationLogOut])
def list_operation_logs(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(OperationLog).order_by(OperationLog.created_at.desc()).limit(500).all()


# ---- Notifications / message center ----
class NotificationOut(BaseModel):
    id: int
    message: str
    level: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Notification)
        .filter((Notification.user_id == current_user.id) | (Notification.user_id.is_(None)))
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    n = db.get(Notification, notification_id)
    # 404 (not 403) for someone else's notification, to avoid confirming it exists
    if not n or (n.user_id is not None and n.user_id != current_user.id):
        raise HTTPException(status_code=404, detail="Not found")
    n.is_read = True
    db.commit()
    return {"ok": True}


# ---- Step owners (responsible person per workflow step) ----
class StepOwnerIn(BaseModel):
    step_name: str
    user_id: int | None = None
    contact_name: str = ""
    contact_phone: str = ""


class StepOwnerOut(StepOwnerIn):
    id: int

    class Config:
        from_attributes = True


@router.get("/step-owners", response_model=list[StepOwnerOut])
def list_step_owners(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(StepOwner).order_by(StepOwner.id).all()


@router.post("/step-owners", response_model=StepOwnerOut)
def create_step_owner(payload: StepOwnerIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    ensure_exists(db, User, payload.user_id, "User")
    item = StepOwner(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
