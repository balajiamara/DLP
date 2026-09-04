import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_config_settings_loads_correctly_when_database_url_is_set():
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/testdb",
        ALLOWED_ORIGINS="http://localhost:5173,https://myfrontend.com",
        ENVIRONMENT="testing",
    )
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost:5432/testdb"
    assert settings.ALLOWED_ORIGINS == ["http://localhost:5173", "https://myfrontend.com"]
    assert settings.ENVIRONMENT == "testing"


def test_config_scheme_normalization_preserves_query_parameters():
    raw_url = "postgresql://user:secretpass@db.supabase.co:5432/postgres?sslmode=require&connect_timeout=10"
    settings = Settings(
        DATABASE_URL=raw_url,
        ALLOWED_ORIGINS="http://localhost:5173",
    )
    # Assert scheme is normalized to postgresql+asyncpg while preserving parameters
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")
    assert "sslmode=require" in settings.DATABASE_URL
    assert "connect_timeout=10" in settings.DATABASE_URL
    assert "user:secretpass@db.supabase.co:5432/postgres" in settings.DATABASE_URL


def test_config_fails_when_database_url_is_missing():
    with pytest.raises(ValidationError) as exc_info:
        Settings(DATABASE_URL="")

    errors_str = str(exc_info.value)
    assert "DATABASE_URL environment variable is missing or empty" in errors_str
