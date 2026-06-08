"""API gateway settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    jwt_secret: str = Field(default="change-me-in-production", alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 168

    api_sync_secret: str = Field(default="dev-sync-secret", alias="API_SYNC_SECRET")
    dev_skip_auth: bool = Field(default=False, alias="DEV_SKIP_AUTH")

    cors_origins: str = Field(
        default="http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    athena_data_dir: Path = Field(default=Path("./data"), alias="ATHENA_DATA_DIR")
    athena_db_path: Path = Field(
        default=Path("./data/athena_api.db"),
        alias="API_DB_PATH",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def get_api_settings() -> ApiSettings:
    return ApiSettings()
