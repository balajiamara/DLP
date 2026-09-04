import asyncio
import pytest
import httpx
from sqlalchemy.exc import OperationalError
from app.main import app
from app.db.session import get_db


@pytest.mark.asyncio
async def test_health_live():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_root_sanity_check():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert response.json() == {
            "service": "daily-learning-planner-fastapi",
            "status": "running",
        }


@pytest.mark.asyncio
async def test_health_ready_success():
    class DummySession:
        async def execute(self, statement):
            return True

    async def override_get_db():
        yield DummySession()

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")
            assert response.status_code == 200
            assert response.json() == {"status": "ok", "database": "connected"}
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_ready_db_exception():
    class FailingSession:
        async def execute(self, statement):
            raise OperationalError("SELECT 1", {}, Exception("Raw DB error should not leak"))

    async def override_get_db_failing():
        yield FailingSession()

    app.dependency_overrides[get_db] = override_get_db_failing
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "error"
            assert data["database"] == "disconnected"
            assert data["detail"] == "Database connection unavailable"
            assert "Raw DB error" not in str(data)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_ready_db_timeout():
    class HangingSession:
        async def execute(self, statement):
            await asyncio.sleep(4.0)
            return True

    async def override_get_db_hanging():
        yield HangingSession()

    app.dependency_overrides[get_db] = override_get_db_hanging
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "error"
            assert data["database"] == "disconnected"
            assert data["detail"] == "Database ping operation timed out"
    finally:
        app.dependency_overrides.clear()
