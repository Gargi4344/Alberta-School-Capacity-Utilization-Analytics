"""Application settings, read from environment variables (see .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://abcap:abcap@localhost:5432/abcap"
    data_dir: Path = REPO_ROOT / "data"
    log_level: str = "INFO"

    # Open data endpoints
    ckan_base_url: str = "https://open.alberta.ca/api/3/action"
    http_timeout_seconds: float = 120.0

    # Business rules
    utilization_threshold_pct: float = 85.0  # province's optimal utilization rate
    over_capacity_pct: float = 100.0

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"


@lru_cache
def get_settings() -> Settings:
    return Settings()
