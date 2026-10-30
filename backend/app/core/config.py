from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr, model_validator
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
    chunk_size_lines: int = Field(default=100, gt=0, le=1000)
    chunk_overlap_lines: int = Field(default=15, ge=0, le=999)
    max_repository_chunks: int = Field(default=10000, gt=0, le=100000)
    embedding_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        min_length=1,
        max_length=200,
    )
    retrieval_candidate_count: int = Field(default=50, gt=0, le=200)
    retrieval_rrf_k: int = Field(default=60, gt=0)
    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GEMINI_API_KEY",
            "REPOSAGE_GEMINI_API_KEY",
        ),
    )
    gemini_model: str = Field(
        default="gemini-3.5-flash-lite",
        min_length=1,
        max_length=100,
        validation_alias=AliasChoices(
            "GEMINI_MODEL",
            "REPOSAGE_GEMINI_MODEL",
        ),
    )
    gemini_timeout_seconds: float = Field(default=45.0, gt=0, le=180)
    rag_context_chunks: int = Field(default=6, gt=0, le=12)
    rag_context_max_characters: int = Field(default=24000, gt=0, le=100000)
    rag_max_output_tokens: int = Field(default=1200, gt=0, le=4000)

    @model_validator(mode="after")
    def validate_chunk_overlap(self) -> "Settings":
        if self.chunk_overlap_lines >= self.chunk_size_lines:
            raise ValueError(
                "chunk_overlap_lines must be less than chunk_size_lines"
            )
        return self

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
