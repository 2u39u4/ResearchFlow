"""User profile endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from api.database import soft_delete_user, update_user
from api.schemas import UserUpdateRequest

router = APIRouter(prefix="/users", tags=["users"])


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user.get("display_name"),
        "avatar_url": user.get("avatar_url"),
        "locale": user.get("locale") or "en",
        "default_year_min": user.get("default_year_min"),
        "default_year_max": user.get("default_year_max"),
        "default_domain": user.get("default_domain"),
    }


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    return _public_user(user)


@router.patch("/me")
async def patch_me(
    body: UserUpdateRequest,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    updated = update_user(user["id"], body.model_dump(exclude_none=True))
    return _public_user(updated or user)


@router.delete("/me")
async def delete_me(user: dict = Depends(get_current_user)) -> dict[str, str]:
    soft_delete_user(user["id"])
    return {"status": "deleted"}
