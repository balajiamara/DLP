import os
import pytest
from unittest.mock import patch, AsyncMock
from dotenv import load_dotenv

# Load .env from backend-fastapi directory so tests use the configured database
load_dotenv()

# Fallback environment variables for unit testing if .env is missing
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/test_db"
)
os.environ.setdefault(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
)


@pytest.fixture(autouse=True)
def mock_db_ai_interaction_logging(request):
    """
    Prevents unit tests from writing mock telemetry rows to the live Supabase database.
    Does not interfere with tests in test_evaluation_logging.py which manage their own mocks.
    """
    if "test_evaluation_logging" in str(request.node.fspath):
        yield
    else:
        with patch("app.services.evaluation_logging.async_session_maker") as mock_maker:
            mock_session = AsyncMock()
            mock_maker.return_value.__aenter__.return_value = mock_session
            yield mock_maker

