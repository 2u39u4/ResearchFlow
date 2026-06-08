"""Auth sync endpoint (called from Next.js after Google OAuth)."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status

from api.auth import create_access_token
from api.config import get_api_settings
from api.database import upsert_user
from api.schemas import AuthResponse, GoogleSyncRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/google", response_model=AuthResponse)
def sync_google_user(
    body: GoogleSyncRequest,
    x_api_sync_secret: str | None = Header(default=None, alias="X-API-Sync-Secret"),
) -> AuthResponse:
    settings = get_api_settings()
    if (
        not settings.dev_skip_auth
        and settings.api_sync_secret
        and x_api_sync_secret != settings.api_sync_secret
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid sync secret")
    user = upsert_user(
        google_sub=body.sub,
        email=body.email,
        display_name=body.display_name,
        avatar_url=body.avatar_url,
        locale=body.locale,
    )
    token = create_access_token(user["id"])
    return AuthResponse(access_token=token, user=_public_user(user))


def _public_user(user: dict) -> dict:
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
