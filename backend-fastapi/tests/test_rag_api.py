"""
Unit & Integration tests for internal RAG API endpoint (app/api/rag.py)
Tests X-Internal-Secret auth, 401 responses, 403 forbidden responses on unauthorized classroom access, and success payloads.
"""

from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.services.rag_retrieval import NotAuthorizedError

SECRET = settings.INTERNAL_SERVICE_SECRET


@pytest.mark.asyncio
async def test_rag_retrieve_endpoint_missing_header():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/rag/retrieve",
            json={
                "student_user_id": 10,
                "classroom_id": 1,
                "query": "What is machine learning?",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized: Missing or invalid X-Internal-Secret header."


@pytest.mark.asyncio
async def test_rag_retrieve_endpoint_wrong_secret():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/rag/retrieve",
            headers={"X-Internal-Secret": "invalid-secret-key"},
            json={
                "student_user_id": 10,
                "classroom_id": 1,
                "query": "What is machine learning?",
            },
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_rag_retrieve_endpoint_unauthorized_student_returns_403():
    with patch("app.api.rag.retrieve_relevant_chunks", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.side_effect = NotAuthorizedError("User 10 is not an active member of classroom 99")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/rag/retrieve",
                headers={"X-Internal-Secret": SECRET},
                json={
                    "student_user_id": 10,
                    "classroom_id": 99,
                    "query": "What is machine learning?",
                },
            )
            assert response.status_code == 403
            assert response.json()["detail"] == "Access denied or classroom not found."


@pytest.mark.asyncio
async def test_rag_retrieve_endpoint_success():
    fake_chunks = [
        {
            "id": "uuid-1",
            "material_id": 101,
            "material_title": "AI Lecture Notes",
            "topic_id": 5,
            "classroom_id": 1,
            "chunk_text": "Machine learning is a subset of artificial intelligence.",
            "chunk_index": 0,
            "score": 0.92,
            "distance": 0.08,
        }
    ]

    with patch("app.api.rag.retrieve_relevant_chunks", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.return_value = fake_chunks

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/rag/retrieve",
                headers={"X-Internal-Secret": SECRET},
                json={
                    "student_user_id": 10,
                    "classroom_id": 1,
                    "query": "What is machine learning?",
                    "top_k": 3,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert "chunks" in data
            assert len(data["chunks"]) == 1
            assert data["chunks"][0]["material_title"] == "AI Lecture Notes"
            assert data["chunks"][0]["score"] == 0.92
