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
    default_llm_model: str = "gpt-5.5"
    default_llm_provider: str = "openai"  # openai | deepseek | gemini

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

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

    # Citation validator
    citation_title_match_threshold: float = 90.0
    citation_year_tolerance: int = 1
    citation_search_top_k: int = 5

    # Critic agent — empty critic_llm_model uses default_llm_model
    critic_llm_model: str = ""
    critic_temperature: float = 0.3
    critic_max_tokens: int = 2048
    critic_max_critiques: int = 8

    # Planner / Writer (pipeline)
    planner_llm_model: str = ""
    planner_temperature: float = 0.2
    planner_max_tokens: int = 1024
    writer_llm_model: str = ""
    writer_temperature: float = 0.3
    writer_max_tokens: int = 2048

    # LangGraph checkpoints
    athena_checkpoint_db: Path = Field(default=Path("./data/athena_checkpoints.db"))

    # Evaluation judges — should differ from DEFAULT_LLM_MODEL / provider
    judge_llm_model: str = ""
    judge_llm_provider: str = "gemini"  # openai | deepseek | gemini
    eval_random_seed: int = 42
    eval_default_repeats: int = 3

    # Streamlit demo — empty = no password gate (local dev only)
    athena_ui_password: str = ""

    @property
    def semantic_scholar_uses_anonymous(self) -> bool:
        return not bool(self.semantic_scholar_api_key.strip())

    def ensure_dirs(self) -> None:
        self.athena_data_dir.mkdir(parents=True, exist_ok=True)
        self.athena_cache_dir.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
