"""
Unit & Integration tests for internal Materials API endpoints (app/api/materials.py)
Tests X-Internal-Secret authentication, 401 unauthorized responses, and route handling.
"""

import time
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.services.document_processor import process_material

SECRET = settings.INTERNAL_SERVICE_SECRET


@pytest.mark.asyncio
async def test_process_material_endpoint_missing_header():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/materials/101/process")
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized: Missing or invalid X-Internal-Secret header."


@pytest.mark.asyncio
async def test_process_material_endpoint_wrong_secret():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/materials/101/process",
            headers={"X-Internal-Secret": "wrong-invalid-secret-key"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_process_material_endpoint_success():
    with patch("app.api.materials.process_material") as mock_process:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/materials/101/process",
                headers={"X-Internal-Secret": SECRET},
            )
            assert response.status_code == 202
            data = response.json()
            assert data["material_id"] == 101
            assert data["status"] == "processing_started"


@pytest.mark.asyncio
async def test_get_material_status_endpoint_missing_header():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/materials/101/status")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_material_status_endpoint_wrong_secret():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/materials/101/status",
            headers={"X-Internal-Secret": "wrong-secret"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_material_status_endpoint_success():
    fake_record = {
        "material_id": 101,
        "status": "READY",
        "failure_reason": None,
    }
    with patch("app.api.materials.get_material_status_record", new_callable=AsyncMock) as mock_get_status:
        mock_get_status.return_value = fake_record

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/materials/101/status",
                headers={"X-Internal-Secret": SECRET},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["material_id"] == 101
            assert data["status"] == "READY"
            assert data["failure_reason"] is None


@pytest.mark.asyncio
async def test_get_material_status_endpoint_not_found():
    with patch("app.api.materials.get_material_status_record", new_callable=AsyncMock) as mock_get_status:
        mock_get_status.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/materials/9999/status",
                headers={"X-Internal-Secret": SECRET},
            )
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_health_live_responsive_during_slow_embedding():
    """
    Verifies that get_embeddings running inside asyncio.to_thread does NOT block the event loop,
    allowing /health/live to respond immediately (<0.15s) while embedding generation sleeps in a worker thread.
    """
    fake_record = (101, 10, "materials/test_doc.pdf", "pdf", "UPLOADED", 1)
    mock_db_result = MagicMock()
    mock_db_result.first.return_value = fake_record

    mock_session = AsyncMock()
    mock_session.add_all = MagicMock()
    mock_session.execute.return_value = mock_db_result

    def slow_get_embeddings(chunks):
        time.sleep(0.3)  # Simulate blocking sync API call / network delay in worker thread
        return [[0.1] * 768]

    with patch("app.services.document_processor.async_session_maker") as mock_maker_cls, \
         patch("app.services.document_processor.fetch_storage_file", new_callable=AsyncMock) as mock_fetch, \
         patch("app.services.document_processor.extract_text_from_pdf") as mock_extract, \
         patch("app.services.document_processor.chunk_text") as mock_chunk, \
         patch("app.services.document_processor.get_embeddings", side_effect=slow_get_embeddings):

        mock_maker_cls.return_value.__aenter__.return_value = mock_session
        mock_fetch.return_value = b"%PDF-1.4 test bytes"
        mock_extract.return_value = "Sample text"
        mock_chunk.return_value = ["Sample text"]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Trigger process_material in background task
            process_task = asyncio.create_task(process_material(101))

            # Concurrently request health check while process_material is executing get_embeddings thread
            t0 = time.monotonic()
            health_response = await client.get("/health/live")
            t1 = time.monotonic()

            await process_task

            # Health check must return 200 OK immediately (< 0.15s) while embedding takes 0.3s
            assert health_response.status_code == 200
            assert health_response.json()["status"] == "ok"
            assert (t1 - t0) < 0.2, f"Health check response was delayed ({t1 - t0:.3f}s), indicating event loop lockup!"
