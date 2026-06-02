"""Application settings loaded from environment / .env."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    default_llm_model: str = "gpt-4o-mini"
    default_llm_provider: str = "openai"  # openai | deepseek

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # Academic APIs
    semantic_scholar_api_key: str = ""
    crossref_mailto: str = ""

    # Paths
    athena_data_dir: Path = Field(default=Path("./data"))
    athena_cache_dir: Path = Field(default=Path("./athena_cache"))
    athena_db_path: Path = Field(default=Path("./data/athena.db"))

    # Rate limits (seconds)
    arxiv_min_interval_sec: float = 3.0
    semantic_scholar_min_interval_sec: float = 1.0

    @property
    def semantic_scholar_uses_anonymous(self) -> bool:
        return not bool(self.semantic_scholar_api_key.strip())

    def ensure_dirs(self) -> None:
        self.athena_data_dir.mkdir(parents=True, exist_ok=True)
        self.athena_cache_dir.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
