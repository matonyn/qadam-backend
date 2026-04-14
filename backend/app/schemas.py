from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, EmailStr, Field
from pydantic.generics import GenericModel


T = TypeVar("T")


class ApiResponse(GenericModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None


class User(BaseModel):
    id: str
    email: EmailStr
    firstName: str
    lastName: str
    studentId: str
    avatar: Optional[str] = None
    createdAt: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    firstName: str
    lastName: str
    studentId: str


class AuthPayload(BaseModel):
    accessToken: str
    refreshToken: str
    expiresIn: int = 3600
    user: User


class ThemeUpdateRequest(BaseModel):
    theme: Literal["light", "dark", "system"]


class LanguageUpdateRequest(BaseModel):
    language: Literal["en", "ru", "kz"]


class ReadAllNotificationsResponse(BaseModel):
    updated: int


class IdResponse(BaseModel):
    id: str


class ReviewCreateRequest(BaseModel):
    targetType: Literal["building", "room", "event"]
    targetId: str
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=1, max_length=2000)


class RoutingRequest(BaseModel):
    fromBuildingId: str
    toBuildingId: str


class SimpleOk(BaseModel):
    ok: bool = True
