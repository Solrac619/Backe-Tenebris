from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# =========================
# AUTH / USERS
# =========================

class UserOut(BaseModel):
    # Permite construir desde objetos ORM (SQLAlchemy)
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    display_name: str = ""
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: Optional[str] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


# Tu /login devuelve accessToken + user + refreshToken
class TokenOut(BaseModel):
    accessToken: str
    user: UserOut
    refreshToken: str


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


# (Opcional) Si mueves RefreshIn aquí en vez de definirlo en auth.py
class RefreshIn(BaseModel):
    userId: str
    refreshToken: str


# =========================
# MEDIA / GALLERY
# =========================

class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    thumb_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class PageMedia(BaseModel):
    page: int
    pageSize: int
    total: int
    items: List[MediaOut]


class AvatarIconOut(BaseModel):
    id: str
    url: str
    label: str

class SelectAvatarIn(BaseModel):
    iconId: str