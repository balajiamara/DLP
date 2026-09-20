"""
Unit tests for Chat Streaming API endpoints (POST /chat/course/stream and POST /chat/general/stream)
and underlying streaming services.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.services.course_chat import stream_course_question, UNGROUNDED_FALLBACK_ANSWER
from app.services.general_chat import stream_general_question
from app.services.chat_client import generate_answer_stream, GeminiChatError

client = TestClient(app)
HEADERS = {"X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET}


def parse_sse_events(response_text: str):
    """Helper to parse SSE lines into a list of parsed JSON objects."""
    events = []
    for line in response_text.strip().split("\n\n"):
        line = line.strip()
        if line.startswith("data: "):
            json_str = line[len("data: "):]
            events.append(json.loads(json_str))
    return events


# =====================================================================
# ENDPOINT SECURITY & PRE-STREAM AUTHORIZATION TESTS
# =====================================================================

def test_course_chat_stream_unauthorized_secret():
    """Confirms 401 Unauthorized when X-Internal-Secret is missing or invalid."""
    payload = {
        "student_user_id": 1,
        "classroom_id": 1,
        "query": "What is Python?",
    }
    res1 = client.post("/chat/course/stream", json=payload)
    assert res1.status_code == 401

    res2 = client.post("/chat/course/stream", json=payload, headers={"X-Internal-Secret": "invalid"})
    assert res2.status_code == 401


@patch("app.api.chat.is_authorized_for_classroom", new_callable=AsyncMock)
def test_course_chat_stream_forbidden_pre_stream(mock_auth):
    """Confirms 403 Forbidden is returned IMMEDIATELY before opening stream if unauthorized."""
    mock_auth.return_value = False

    payload = {
        "student_user_id": 99,
        "classroom_id": 1,
        "query": "What is Python?",
    }
    response = client.post("/chat/course/stream", json=payload, headers=HEADERS)
    assert response.status_code == 403
    assert "Access denied or classroom not found" in response.json()["detail"]


def test_general_chat_stream_unauthorized_secret():
    """Confirms 401 Unauthorized when X-Internal-Secret is missing or invalid."""
    payload = {
        "student_user_id": 1,
        "classroom_id": 1,
        "query": "What is Python?",
    }
    res = client.post("/chat/general/stream", json=payload)
    assert res.status_code == 401


@patch("app.api.chat.is_authorized_for_classroom", new_callable=AsyncMock)
def test_general_chat_stream_forbidden_pre_stream(mock_auth):
    """Confirms 403 Forbidden is returned IMMEDIATELY before opening stream if unauthorized."""
    mock_auth.return_value = False

    payload = {
        "student_user_id": 99,
        "classroom_id": 1,
        "query": "What is Python?",
    }
    response = client.post("/chat/general/stream", json=payload, headers=HEADERS)
    assert response.status_code == 403
    assert "Access denied or classroom not found" in response.json()["detail"]


# =====================================================================
# COURSE CHAT STREAMING TESTS (GROUNDED & FALLBACK)
# =====================================================================

@patch("app.api.chat.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.api.chat.stream_course_question")
def test_course_chat_stream_endpoint_success(mock_stream_func, mock_auth):
    """Confirms POST /chat/course/stream returns 200 with text/event-stream content."""
    mock_auth.return_value = True

    async def fake_generator(*args, **kwargs):
        yield 'data: {"type": "chunk", "delta": "Hello"}\n\n'
        yield 'data: {"type": "chunk", "delta": " world"}\n\n'
        yield 'data: {"type": "done", "grounded": true, "sources": [], "interaction_id": "test-uuid"}\n\n'

    mock_stream_func.side_effect = fake_generator

    payload = {
        "student_user_id": 1,
        "classroom_id": 1,
        "query": "Hello",
    }
    response = client.post("/chat/course/stream", json=payload, headers=HEADERS)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = parse_sse_events(response.text)
    assert len(events) == 3
    assert events[0] == {"type": "chunk", "delta": "Hello"}
    assert events[1] == {"type": "chunk", "delta": " world"}
    assert events[2]["type"] == "done"
    assert events[2]["grounded"] is True


@pytest.mark.asyncio
@patch("app.services.course_chat.log_ai_interaction", new_callable=AsyncMock)
@patch("app.services.course_chat.generate_answer_stream")
@patch("app.services.course_chat.retrieve_relevant_chunks", new_callable=AsyncMock)
async def test_stream_course_question_grounded_service(mock_retrieval, mock_llm_stream, mock_log):
    """Verifies stream_course_question yields chunks and done event with telemetry logging."""
    mock_retrieval.return_value = [
        {
            "id": 101,
            "material_title": "Biology 101",
            "material_id": 5,
            "chunk_index": 0,
            "chunk_text": "Mitochondria is the powerhouse of the cell.",
            "distance": 0.15,
        }
    ]

    async def fake_llm(prompt, query):
        yield "Mitochondria produces "
        yield "cellular energy."

    mock_llm_stream.side_effect = fake_llm
    mock_log.return_value = "mock-uuid-1234"

    events = []
    async for event_str in stream_course_question(
        user_id=1, classroom_id=1, topic_id=None, query="What does mitochondria do?"
    ):
        events.append(event_str)

    combined_text = "".join(events)
    parsed = parse_sse_events(combined_text)

    assert len(parsed) == 3
    assert parsed[0] == {"type": "chunk", "delta": "Mitochondria produces "}
    assert parsed[1] == {"type": "chunk", "delta": "cellular energy."}
    assert parsed[2]["type"] == "done"
    assert parsed[2]["grounded"] is True
    assert len(parsed[2]["sources"]) == 1
    assert parsed[2]["sources"][0]["material_title"] == "Biology 101"

    # Confirm evaluation log was invoked
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["interaction_type"] == "COURSE_CHAT"
    assert call_kwargs["grounded"] is True
    assert call_kwargs["answer_text"] == "Mitochondria produces cellular energy."
    assert call_kwargs["retrieved_chunk_ids"] == ["101"]


@pytest.mark.asyncio
@patch("app.services.course_chat.log_ai_interaction", new_callable=AsyncMock)
@patch("app.services.course_chat.retrieve_relevant_chunks", new_callable=AsyncMock)
async def test_stream_course_question_fallback_service(mock_retrieval, mock_log):
    """Verifies stream_course_question fallback sends consistent SSE chunk + done event."""
    # Chunks above distance threshold 0.40 -> 0 relevant chunks
    mock_retrieval.return_value = [
        {
            "id": 202,
            "material_title": "Unrelated",
            "material_id": 9,
            "chunk_index": 0,
            "chunk_text": "Unrelated topic",
            "distance": 0.85,
        }
    ]
    mock_log.return_value = "mock-uuid-fallback"

    events = []
    async for event_str in stream_course_question(
        user_id=1, classroom_id=1, topic_id=None, query="What is rocket propulsion?"
    ):
        events.append(event_str)

    combined_text = "".join(events)
    parsed = parse_sse_events(combined_text)

    assert len(parsed) == 2
    assert parsed[0] == {"type": "chunk", "delta": UNGROUNDED_FALLBACK_ANSWER}
    assert parsed[1]["type"] == "done"
    assert parsed[1]["grounded"] is False
    assert parsed[1]["sources"] == []

    # Confirm evaluation log was invoked with grounded=False
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["grounded"] is False
    assert call_kwargs["answer_text"] == UNGROUNDED_FALLBACK_ANSWER


# =====================================================================
# GENERAL CHAT STREAMING TESTS
# =====================================================================

@patch("app.api.chat.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.api.chat.stream_general_question")
def test_general_chat_stream_endpoint_success(mock_stream_func, mock_auth):
    """Confirms POST /chat/general/stream returns 200 with text/event-stream content."""
    mock_auth.return_value = True

    async def fake_generator(*args, **kwargs):
        yield 'data: {"type": "chunk", "delta": "General"}\n\n'
        yield 'data: {"type": "chunk", "delta": " answer"}\n\n'
        yield 'data: {"type": "done", "grounded": false, "sources": [], "interaction_id": "test-uuid"}\n\n'

    mock_stream_func.side_effect = fake_generator

    payload = {
        "student_user_id": 1,
        "classroom_id": 1,
        "query": "Tell me a joke",
    }
    response = client.post("/chat/general/stream", json=payload, headers=HEADERS)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = parse_sse_events(response.text)
    assert len(events) == 3
    assert events[0] == {"type": "chunk", "delta": "General"}
    assert events[1] == {"type": "chunk", "delta": " answer"}
    assert events[2]["type"] == "done"
    assert events[2]["grounded"] is False


@pytest.mark.asyncio
@patch("app.services.general_chat.log_ai_interaction", new_callable=AsyncMock)
@patch("app.services.general_chat.generate_answer_stream")
@patch("app.services.general_chat.is_authorized_for_classroom", new_callable=AsyncMock)
async def test_stream_general_question_service(mock_auth, mock_llm_stream, mock_log):
    """Verifies stream_general_question yields chunks and done event with grounded=False."""
    mock_auth.return_value = True

    async def fake_llm(prompt, query):
        yield "Calculus is "
        yield "the study of continuous change."

    mock_llm_stream.side_effect = fake_llm
    mock_log.return_value = "mock-uuid-general"

    events = []
    async for event_str in stream_general_question(
        user_id=1, classroom_id=1, query="What is calculus?"
    ):
        events.append(event_str)

    combined_text = "".join(events)
    parsed = parse_sse_events(combined_text)

    assert len(parsed) == 3
    assert parsed[0] == {"type": "chunk", "delta": "Calculus is "}
    assert parsed[1] == {"type": "chunk", "delta": "the study of continuous change."}
    assert parsed[2]["type"] == "done"
    assert parsed[2]["grounded"] is False
    assert parsed[2]["sources"] == []

    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["interaction_type"] == "GENERAL_CHAT"
    assert call_kwargs["grounded"] is False


# =====================================================================
# MID-STREAM ERROR HANDLING & TELEMETRY RETENTION TESTS
# =====================================================================

@pytest.mark.asyncio
@patch("app.services.course_chat.log_ai_interaction", new_callable=AsyncMock)
@patch("app.services.course_chat.generate_answer_stream")
@patch("app.services.course_chat.retrieve_relevant_chunks", new_callable=AsyncMock)
async def test_stream_course_question_mid_stream_error(mock_retrieval, mock_llm_stream, mock_log):
    """Confirms that if LLM stream aborts mid-stream, partial text is logged with error_occurred=True."""
    mock_retrieval.return_value = [
        {
            "id": 105,
            "material_title": "Physics",
            "material_id": 2,
            "chunk_index": 0,
            "chunk_text": "Newton laws",
            "distance": 0.10,
        }
    ]

    async def failing_stream(prompt, query):
        yield "First chunk received before "
        raise GeminiChatError("Gemini connection terminated abruptly.")

    mock_llm_stream.side_effect = failing_stream

    events = []
    async for event_str in stream_course_question(
        user_id=1, classroom_id=1, topic_id=None, query="Physics laws"
    ):
        events.append(event_str)

    combined_text = "".join(events)
    parsed = parse_sse_events(combined_text)

    assert len(parsed) == 2
    assert parsed[0] == {"type": "chunk", "delta": "First chunk received before "}
    assert parsed[1]["type"] == "error"
    assert "Gemini connection terminated" in parsed[1]["detail"]

    # Verify telemetry was STILL recorded with partial answer and error details!
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["error_occurred"] is True
    assert "Gemini connection terminated" in call_kwargs["error_message"]
    assert call_kwargs["answer_text"] == "First chunk received before "
