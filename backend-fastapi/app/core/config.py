import os
from typing import List, Union
from urllib.parse import urlparse, urlunparse
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    ALLOWED_ORIGINS: Union[str, List[str]] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    ENVIRONMENT: str = "development"

    # Supabase free tier connection pool settings:
    # Keep pool size small (5 connections, max_overflow 2) to avoid exhausting Supabase's
    # connection limit alongside Django's connection pool.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 2
    DB_POOL_TIMEOUT: float = 10.0
    DB_POOL_PRE_PING: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_and_normalize_database_url(cls, v: str) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError(
                "CRITICAL: DATABASE_URL environment variable is missing or empty. "
                "The FastAPI service cannot start without a valid database connection string."
            )
        v = v.strip()
        parsed = urlparse(v)
        if parsed.scheme in ("postgres", "postgresql"):
            # Normalize scheme to postgresql+asyncpg while preserving path, query params, etc.
            new_parsed = parsed._replace(scheme="postgresql+asyncpg")
            return urlunparse(new_parsed)
        elif not parsed.scheme.startswith("postgresql+asyncpg"):
            raise ValueError(
                f"Unsupported database scheme '{parsed.scheme}'. "
                "DATABASE_URL must use postgresql+asyncpg:// or postgresql:// scheme."
            )
        return v

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


def get_settings() -> Settings:
    return Settings()
