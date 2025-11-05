from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from .database import get_db
from . import crud
from .schemas import RegisterIn, LoginIn, TokenOut, UserOut
from .utils import hash_password, needs_rehash, verify_password, create_access_token, REFRESH_EXPIRES_DAYS

router = APIRouter(prefix="/v1/auth", tags=["auth"])

@router.post("/register", status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    """Crea un usuario nuevo."""
    if crud.get_user_by_email(db, payload.email):
        raise HTTPException(status_code=409, detail="email already registered")
    user = crud.create_user(
        db,
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or ""
    )
    return {"id": user.id}

@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    """Login: devuelve accessToken + user + refreshToken (texto)."""
    user = crud.get_user_by_email(db, payload.email)
    if verify_password(payload.password, user.password_hash):
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(payload.password)
        db.add(user); db.commit()


    access = create_access_token(user.id)
    raw_refresh, _ = crud.issue_refresh(db, user.id, REFRESH_EXPIRES_DAYS)

    # Devolvemos refreshToken en el body (simple para desarrollo).
    # En producción: considera HttpOnly cookie.
    return {
        "accessToken": access,
        "user": UserOut.model_validate(user).model_dump(),
        "refreshToken": raw_refresh
    }

class RefreshIn(BaseModel):
    userId: str
    refreshToken: str

@router.post("/refresh2")
def refresh2(payload: RefreshIn, db: Session = Depends(get_db)):
    """
    Rotación de refresh:
    - Verifica refresh válido no revocado/expirado.
    - Revoca el usado.
    - Emite access nuevo + refresh nuevo.
    """
    rec = crud.find_valid_refresh(db, payload.userId, payload.refreshToken)
    if not rec:
        raise HTTPException(status_code=401, detail="invalid refresh")

    # Revocamos el usado
    crud.revoke_refresh(db, rec)

    # Emitimos nuevo refresh y access
    new_raw, _ = crud.issue_refresh(db, payload.userId, REFRESH_EXPIRES_DAYS)
    access = create_access_token(payload.userId)
    return {"accessToken": access, "refreshToken": new_raw}
