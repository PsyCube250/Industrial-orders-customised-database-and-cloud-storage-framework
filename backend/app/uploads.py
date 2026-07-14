import os
import shutil
import uuid

from fastapi import HTTPException, UploadFile

from app.config import settings


def save_upload(file: UploadFile, *subdirs: str) -> tuple[str, str]:
    """Store an uploaded file under the upload dir; returns (display_name, stored_path).

    The stored name gets a random prefix so two uploads with the same name
    can't silently overwrite each other.
    """
    name = os.path.basename(file.filename or "").strip()
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid file name")
    target_dir = os.path.join(settings.upload_dir, *subdirs)
    os.makedirs(target_dir, exist_ok=True)
    dest_path = os.path.join(target_dir, f"{uuid.uuid4().hex[:8]}_{name}")
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return name, dest_path
