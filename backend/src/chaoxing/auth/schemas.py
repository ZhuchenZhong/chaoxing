from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import UserRole


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserBase(BaseModel):
    email: str
    username: str = Field(..., min_length=3, max_length=50)
    display_name: str | None = Field(default=None, max_length=100)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    invite_code: str | None = None


class UserUpdate(BaseModel):
    email: str | None = None
    username: str | None = Field(default=None, min_length=3, max_length=50)
    display_name: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, min_length=8)


class UserLogin(BaseModel):
    username: str
    password: str


class UserPublic(UserBase):
    id: int
    role: UserRole
    is_active: bool
    must_change_password: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
