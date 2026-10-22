from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RepoSage"
    environment: str = "development"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    github_token: SecretStr | None = None
    github_api_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    max_repository_files: int = Field(default=1000, gt=0, le=10000)
    max_file_size_bytes: int = Field(default=1_000_000, gt=0)
    max_total_source_bytes: int = Field(default=10_000_000, gt=0)

    model_config = SettingsConfigDict(
        env_prefix="REPOSAGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
