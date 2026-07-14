import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import get_user_from_token
from app.config import settings
from app.database import Base, engine, get_db
from app import models  # noqa: F401  (ensures all models are registered on Base.metadata)
from app.routers import auth, orders, samples, procurement, prep, production, packaging, notifications, system

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if settings.secret_key == "dev-secret-change-me":
        logging.getLogger("uvicorn.error").warning(
            "SECRET_KEY is the built-in dev default — set a real secret before exposing this instance."
        )
    yield


app = FastAPI(title="ProdFlow — Manufacturing Order & Production Management", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.upload_dir, exist_ok=True)


@app.get("/uploads/{file_path:path}")
def serve_upload(
    file_path: str,
    token: str | None = Query(None, description="access token, for plain <a>/<img> links"),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Serves uploaded files to authenticated users only (attachments and sample
    photos may be commercially sensitive, so they are not public static files)."""
    bearer = token
    if not bearer and authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:]
    if not bearer:
        raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    get_user_from_token(bearer, db)

    base = os.path.realpath(settings.upload_dir)
    full = os.path.realpath(os.path.join(base, file_path))
    if not full.startswith(base + os.sep) or not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(full)


app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(samples.router)
app.include_router(procurement.router)
app.include_router(prep.router)
app.include_router(production.router)
app.include_router(packaging.router)
app.include_router(notifications.router)
app.include_router(system.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
