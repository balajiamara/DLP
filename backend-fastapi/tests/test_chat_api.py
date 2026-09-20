"""
Unit tests for Chat API Router (app.api.chat)
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.services.rag_retrieval import NotAuthorizedError

client = TestClient(app)

HEADERS = {"X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET}


# =====================================================================
# COURSE CHAT ENDPOINT TESTS
# =====================================================================

@patch("app.api.chat.answer_course_question")
def test_course_chat_endpoint_success(mock_answer_course_question):
    """Confirms POST /chat/course returns 200 OK with grounded response."""
    mock_answer_course_question.return_value = {
        "answer": "FastAPI bridges Django with pgvector.",
        "grounded": True,
        "sources": [
            {
                "material_title": "Architecture Doc",
                "material_id": 8,
                "chunk_index": 0,
            }
        ],
    }

    payload = {
        "student_user_id": 1,
        "classroom_id": 1,
        "topic_id": None,
        "query": "What bridges Django with pgvector?",
    }

    response = client.post("/chat/course", json=payload, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "FastAPI bridges Django with pgvector."
    assert data["grounded"] is True
    assert len(data["sources"]) == 1
    assert data["sources"][0]["material_title"] == "Architecture Doc"


@patch("app.api.chat.answer_course_question")
def test_course_chat_endpoint_forbidden(mock_answer_course_question):
    """Confirms POST /chat/course returns 403 Forbidden on NotAuthorizedError."""
    mock_answer_course_question.side_effect = NotAuthorizedError("User 99 not in classroom 1")

    payload = {
        "student_user_id": 99,
        "classroom_id": 1,
        "topic_id": None,
        "query": "Can I access this?",
    }

    response = client.post("/chat/course", json=payload, headers=HEADERS)

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied or classroom not found."


def test_course_chat_endpoint_unauthorized_secret():
    """Confirms POST /chat/course returns 401 Unauthorized if secret header is missing or wrong."""
    payload = {
        "student_user_id": 1,
        "classroom_id": 1,
        "topic_id": None,
        "query": "Unauthorized test",
    }

    # Missing header
    res1 = client.post("/chat/course", json=payload)
    assert res1.status_code == 401

    # Invalid header
    res2 = client.post("/chat/course", json=payload, headers={"X-Internal-Secret": "wrong-secret"})
    assert res2.status_code == 401


# =====================================================================
# GENERAL CHAT ENDPOINT TESTS
# =====================================================================

@patch("app.api.chat.answer_general_question")
def test_general_chat_endpoint_success(mock_answer_general_question):
    """Confirms POST /chat/general returns 200 OK with ungrounded response."""
    mock_answer_general_question.return_value = {
        "answer": "Photosynthesis is the process by which plants convert light into energy.",
        "grounded": False,
        "sources": [],
    }

    payload = {
        "student_user_id": 1,
        "classroom_id": 1,
        "query": "What is photosynthesis?",
    }

    response = client.post("/chat/general", json=payload, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Photosynthesis is the process by which plants convert light into energy."
    assert data["grounded"] is False
    assert data["sources"] == []


@patch("app.api.chat.answer_general_question")
def test_general_chat_endpoint_forbidden(mock_answer_general_question):
    """Confirms POST /chat/general returns 403 Forbidden on NotAuthorizedError."""
    mock_answer_general_question.side_effect = NotAuthorizedError("User 99 not in classroom 1")

    payload = {
        "student_user_id": 99,
        "classroom_id": 1,
        "query": "General question?",
    }

    response = client.post("/chat/general", json=payload, headers=HEADERS)

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied or classroom not found."


def test_general_chat_endpoint_unauthorized_secret():
    """Confirms POST /chat/general returns 401 Unauthorized if secret header is missing or wrong."""
    payload = {
        "student_user_id": 1,
        "classroom_id": 1,
        "query": "Unauthorized test",
    }

    # Missing header
    res1 = client.post("/chat/general", json=payload)
    assert res1.status_code == 401

    # Invalid header
    res2 = client.post("/chat/general", json=payload, headers={"X-Internal-Secret": "wrong-secret"})
    assert res2.status_code == 401


@patch("app.api.chat.answer_course_question")
def test_course_chat_endpoint_socratic_mode_flag(mock_answer_course_question):
    """Confirms socratic_mode=True is passed through to answer_course_question."""
    mock_answer_course_question.return_value = {
        "answer": "What do you think is the main function?",
        "grounded": True,
        "sources": [],
    }

    payload = {
        "student_user_id": 1,
        "classroom_id": 1,
        "query": "How does it work?",
        "socratic_mode": True,
    }

    response = client.post("/chat/course", json=payload, headers=HEADERS)
    assert response.status_code == 200
    mock_answer_course_question.assert_called_once_with(
        user_id=1,
        classroom_id=1,
        topic_id=None,
        query="How does it work?",
        socratic_mode=True,
    )


@patch("app.api.chat.answer_course_question")
def test_course_chat_endpoint_default_socratic_mode_false(mock_answer_course_question):
    """Confirms omitting socratic_mode defaults to False (no regression)."""
    mock_answer_course_question.return_value = {
        "answer": "Direct answer",
        "grounded": True,
        "sources": [],
    }

    payload = {
        "student_user_id": 1,
        "classroom_id": 1,
        "query": "How does it work?",
    }

    response = client.post("/chat/course", json=payload, headers=HEADERS)
    assert response.status_code == 200
    mock_answer_course_question.assert_called_once_with(
        user_id=1,
        classroom_id=1,
        topic_id=None,
        query="How does it work?",
        socratic_mode=False,
    )


@patch("app.api.chat.answer_general_question")
def test_general_chat_endpoint_socratic_mode_flag(mock_answer_general_question):
    """Confirms socratic_mode=True is passed through to answer_general_question."""
    mock_answer_general_question.return_value = {
        "answer": "Consider the law of conservation of energy.",
        "grounded": False,
        "sources": [],
    }

    payload = {
        "student_user_id": 1,
        "classroom_id": 1,
        "query": "Why does a ball bounce?",
        "socratic_mode": True,
    }

    response = client.post("/chat/general", json=payload, headers=HEADERS)
    assert response.status_code == 200
    mock_answer_general_question.assert_called_once_with(
        user_id=1,
        classroom_id=1,
        query="Why does a ball bounce?",
        socratic_mode=True,
    )


@patch("app.api.chat.answer_general_question")
def test_general_chat_endpoint_default_socratic_mode_false(mock_answer_general_question):
    """Confirms omitting socratic_mode defaults to False in General Mode (no regression)."""
    mock_answer_general_question.return_value = {
        "answer": "A ball bounces due to elastic collisions.",
        "grounded": False,
        "sources": [],
    }

    payload = {
        "student_user_id": 1,
        "classroom_id": 1,
        "query": "Why does a ball bounce?",
    }

    response = client.post("/chat/general", json=payload, headers=HEADERS)
    assert response.status_code == 200
    mock_answer_general_question.assert_called_once_with(
        user_id=1,
        classroom_id=1,
        query="Why does a ball bounce?",
        socratic_mode=False,
    )

