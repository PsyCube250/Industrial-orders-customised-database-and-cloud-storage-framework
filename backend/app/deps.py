from fastapi import HTTPException
from sqlalchemy.orm import Session


def ensure_exists(db: Session, model, obj_id: int | None, label: str) -> None:
    """400 when an optional foreign-key id points at a missing row.

    SQLite (dev) doesn't enforce foreign keys by default, but Postgres (Docker)
    does — without this check the insert fails there with an opaque 500.
    """
    if obj_id is not None and db.get(model, obj_id) is None:
        raise HTTPException(status_code=400, detail=f"{label} {obj_id} does not exist")
