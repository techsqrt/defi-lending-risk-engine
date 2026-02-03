import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    """Find .env file, preferring .env.local for local development."""
    # Check for .env.local first (local overrides)
    for env_file in [".env.local", ".env"]:
        # Check in current directory and project root
        for base in [".", os.environ.get("REPO_ROOT", "")]:
            if base:
                path = Path(base) / env_file
                if path.exists():
                    return str(path)
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # DATABASE_URL from environment (production/CI)
    # Falls back to SQLite for local development if not set
    database_url: str = "sqlite:///./local.db"


settings = Settings()
