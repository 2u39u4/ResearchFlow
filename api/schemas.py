"""Pydantic request/response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GoogleSyncRequest(BaseModel):
    sub: str
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    locale: str = "en"


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    locale: str | None = None
    default_year_min: int | None = None
    default_year_max: int | None = None
    default_domain: str | None = None


class RunCreateRequest(BaseModel):
    topic: str = Field(min_length=1)
    constraints: dict[str, Any] = Field(default_factory=dict)


class LibrarySearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
