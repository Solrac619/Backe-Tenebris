from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime
import shutil, uuid, os

from .database import Base, engine, get_db
from .models import User
from .schemas import (
    UserOut, UserUpdate,
    MediaOut, PageMedia,
    AvatarIconOut, SelectAvatarIn
)
from .utils import hash_password, verify_password, create_access_token, REFRESH_EXPIRES_DAYS
from .deps import get_current_user
from . import crud
from typing import List
from urllib.parse import quote
import re

from .auth import router as auth_router

# Crear tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Gallery API", version="1.0.0")

# CORS (ajusta origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # cambia a tus dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Archivos estáticos: expone /uploads/*
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# Exponiendo /avatar

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
AVATAR_DIR = STATIC_DIR / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# --- AUTH ---
app.include_router(auth_router)

# Alternativa completa:
from pydantic import BaseModel
class RefreshIn(BaseModel):
    userId: str
    refreshToken: str

@app.post("/v1/auth/refresh2")
def refresh2(payload: RefreshIn, db: Session = Depends(get_db)):
    rec = crud.find_valid_refresh(db, payload.userId, payload.refreshToken)
    if not rec:
        raise HTTPException(401, "invalid refresh")
    # Rotación: revoca el usado y emite uno nuevo
    crud.revoke_refresh(db, rec)
    new_raw, _ = crud.issue_refresh(db, payload.userId, REFRESH_EXPIRES_DAYS)
    access = create_access_token(payload.userId)
    return {"accessToken": access, "refreshToken": new_raw}

# --- USER PROFILE ---
@app.get("/v1/users/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current

@app.patch("/v1/users/me", response_model=UserOut)
def update_me(data: UserUpdate, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if data.display_name is not None:
        current.display_name = data.display_name
    if data.avatar_url is not None:
        current.avatar_url = data.avatar_url
    current.updated_at = datetime.utcnow()
    db.add(current); db.commit(); db.refresh(current)
    return current

# --- GALLERY ---
@app.get("/v1/gallery", response_model=PageMedia)
def list_gallery(
    page: int = 1, pageSize: int = 20,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    total, items = crud.list_media_page(db, current.id, page, pageSize)
    return {"page": page, "pageSize": pageSize, "total": total, "items": items}

@app.post("/v1/gallery/upload", response_model=MediaOut, status_code=201)
async def upload_media(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # Guardar en /uploads/u/<userId>/<uuid>.<ext>
    user_dir = UPLOAD_DIR / "u" / current.id
    user_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix
    fname = f"{uuid.uuid4()}{ext}"
    dest = user_dir / fname

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    public_url = f"/uploads/u/{current.id}/{fname}"

    media = crud.create_media(
        db,
        user_id=current.id,
        url=public_url,
        thumb_url=None,
        title=title,
        description=description,
        width=None, height=None,
        size_bytes=None,
        mime_type=file.content_type,
    )
    return media

# Helpers para armar el catálogo
_ALLOWED_EXTS = {".svg", ".png", ".jpg", ".jpeg", ".webp"}

_slug_re = re.compile(r"[^a-z0-9-]")

def _slugify(name: str) -> str:
    s = name.strip().lower().replace(" ", "-")
    s = _slug_re.sub("", s)
    return s

def _prettify_label(stem: str) -> str:
    # "mala copa" -> "Mala Copa"
    return stem.replace("-", " ").replace("_", " ").title()

def _build_catalog() -> list[AvatarIconOut]:
    items: list[AvatarIconOut] = []
    if not AVATAR_DIR.exists():
        return items
    for p in sorted(AVATAR_DIR.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in _ALLOWED_EXTS:
            continue
        # id “seguro” (sin espacios/acentos raros)
        icon_id = _slugify(p.stem)
        # URL pública (ojo con nombres con espacios -> urlencode)
        url = f"/static/avatars/{quote(p.name)}"
        items.append(AvatarIconOut(id=icon_id, url=url, label=_prettify_label(p.stem)))
    return items

@app.get("/v1/avatars", response_model=List[AvatarIconOut])
def list_avatars():
    # Lee la carpeta en cada request (simple). Si quieres performance, cachea el resultado.
    return _build_catalog()

@app.post("/v1/avatars/select", response_model=UserOut)
def select_avatar(
    payload: SelectAvatarIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    catalog = _build_catalog()
    icon = next((i for i in catalog if i.id == payload.iconId), None)
    if not icon:
        raise HTTPException(status_code=404, detail="icon not found")

    current.avatar_url = icon.url
    current.updated_at = datetime.utcnow()
    db.add(current); db.commit(); db.refresh(current)
    return current
