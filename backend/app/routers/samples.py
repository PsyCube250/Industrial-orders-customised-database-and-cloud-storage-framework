from datetime import datetime, date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.deps import ensure_exists
from app.models.order import Order
from app.models.sample import Sample, SamplePhoto, SampleShipment, SampleConfirmation, SampleMaterial
from app.models.system import User
from app.uploads import save_upload

router = APIRouter(prefix="/api/samples", tags=["samples"])


class SampleCreate(BaseModel):
    order_id: int | None = None
    assigned_to: int | None = None
    deadline: date | None = None


class SampleMaterialIn(BaseModel):
    material_name: str
    spec: str = ""
    unit: str = ""
    qty_per_unit: float = 0
    notes: str = ""


class SampleMaterialOut(SampleMaterialIn):
    id: int

    class Config:
        from_attributes = True


class SamplePhotoOut(BaseModel):
    id: int
    photo_path: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class SampleShipmentIn(BaseModel):
    tracking_no: str


class SampleShipmentOut(SampleShipmentIn):
    id: int
    shipped_at: datetime

    class Config:
        from_attributes = True


class SampleConfirmationIn(BaseModel):
    result: Literal["pass", "fail"]
    proof_path: str = ""


class SampleConfirmationOut(SampleConfirmationIn):
    id: int
    confirmed_at: datetime

    class Config:
        from_attributes = True


class SampleOut(BaseModel):
    id: int
    order_id: int | None
    assigned_to: int | None
    deadline: date | None
    status: str

    class Config:
        from_attributes = True


class SampleDetailOut(SampleOut):
    photos: list[SamplePhotoOut] = []
    shipments: list[SampleShipmentOut] = []
    confirmations: list[SampleConfirmationOut] = []
    materials: list[SampleMaterialOut] = []


@router.get("", response_model=list[SampleOut])
def list_samples(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Sample).order_by(Sample.id.desc()).all()


@router.post("", response_model=SampleOut)
def create_sample(payload: SampleCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    ensure_exists(db, Order, payload.order_id, "Order")
    ensure_exists(db, User, payload.assigned_to, "User")
    sample = Sample(**payload.model_dump(), status="assigned")
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


@router.get("/{sample_id}", response_model=SampleDetailOut)
def get_sample(sample_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    sample = (
        db.query(Sample)
        .options(
            # selectin, not joined: four joined collections would multiply into a
            # cartesian product of their row counts
            selectinload(Sample.photos),
            selectinload(Sample.shipments),
            selectinload(Sample.confirmations),
            selectinload(Sample.materials),
        )
        .filter(Sample.id == sample_id)
        .first()
    )
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    return sample


@router.post("/{sample_id}/photos", response_model=SampleDetailOut)
def upload_sample_photo(
    sample_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), _=Depends(get_current_user)
):
    sample = db.get(Sample, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    _, dest_path = save_upload(file, "samples", str(sample_id))
    db.add(SamplePhoto(sample_id=sample_id, photo_path=dest_path))
    if sample.status == "assigned":
        # photos can also arrive after shipping/confirmation; don't regress the status then
        sample.status = "produced"
    db.commit()
    db.refresh(sample)
    return sample


@router.post("/{sample_id}/shipments", response_model=SampleDetailOut)
def add_sample_shipment(
    sample_id: int, payload: SampleShipmentIn, db: Session = Depends(get_db), _=Depends(get_current_user)
):
    sample = db.get(Sample, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    db.add(SampleShipment(sample_id=sample_id, tracking_no=payload.tracking_no))
    sample.status = "shipped"
    db.commit()
    db.refresh(sample)
    return sample


@router.post("/{sample_id}/confirmation", response_model=SampleDetailOut)
def confirm_sample(
    sample_id: int, payload: SampleConfirmationIn, db: Session = Depends(get_db), _=Depends(get_current_user)
):
    sample = db.get(Sample, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    db.add(SampleConfirmation(sample_id=sample_id, result=payload.result, proof_path=payload.proof_path))
    sample.status = "confirmed" if payload.result == "pass" else "returned"
    db.commit()
    db.refresh(sample)
    return sample


@router.post("/{sample_id}/materials", response_model=SampleDetailOut)
def add_sample_material(
    sample_id: int, payload: SampleMaterialIn, db: Session = Depends(get_db), _=Depends(get_current_user)
):
    sample = db.get(Sample, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    db.add(SampleMaterial(sample_id=sample_id, **payload.model_dump()))
    db.commit()
    db.refresh(sample)
    return sample
