from sqlalchemy.orm import Session
from sqlalchemy import select, func
from datetime import datetime, timedelta
from . import models
from .utils import hash_refresh_token, create_refresh_string

def get_user_by_email(db: Session, email: str) -> models.User | None:
    return db.scalar(select(models.User).where(models.User.email == email))

def create_user(db: Session, email: str, password_hash: str, display_name: str = "") -> models.User:
    u = models.User(email=email, password_hash=password_hash, display_name=display_name)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

def issue_refresh(db: Session, user_id: str, days: int):
    raw = create_refresh_string()
    rec = models.RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(raw),
        expires_at=datetime.utcnow() + timedelta(days=days)
    )
    db.add(rec); db.commit(); db.refresh(rec)
    return raw, rec

def find_valid_refresh(db: Session, user_id: str, raw_token: str):
    hashed = hash_refresh_token(raw_token)
    q = select(models.RefreshToken).where(
        models.RefreshToken.user_id == user_id,
        models.RefreshToken.token_hash == hashed,
        models.RefreshToken.revoked_at.is_(None),
        models.RefreshToken.expires_at > datetime.utcnow(),
    )
    return db.scalar(q)

def revoke_refresh(db: Session, rec: models.RefreshToken):
    rec.revoked_at = datetime.utcnow()
    db.commit()

def create_media(db: Session, **data) -> models.Media:
    m = models.Media(**data)
    db.add(m); db.commit(); db.refresh(m)
    return m

def list_media_page(db: Session, user_id: str, page: int, size: int):
    total = db.scalar(select(func.count()).select_from(models.Media).where(models.Media.user_id == user_id)) or 0
    items = db.scalars(
        select(models.Media)
        .where(models.Media.user_id == user_id)
        .order_by(models.Media.created_at.desc())
        .offset((page-1)*size).limit(size)
    ).all()
    return total, items
