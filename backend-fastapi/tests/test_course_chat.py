"""
Unit tests for Course Chat Orchestration Service (app.services.course_chat)
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.services.course_chat import answer_course_question, UNGROUNDED_FALLBACK_ANSWER, MAX_RELEVANCE_DISTANCE
from app.services.rag_retrieval import NotAuthorizedError


@pytest.mark.asyncio
@patch("app.services.course_chat.retrieve_relevant_chunks")
@patch("app.services.course_chat.generate_answer")
async def test_course_chat_unauthorized_propagation(mock_generate_answer, mock_retrieve_chunks):
    """Confirms NotAuthorizedError propagates and short-circuits LLM generation."""
    mock_retrieve_chunks.side_effect = NotAuthorizedError("User 99 is not an active member of classroom 1")

    with pytest.raises(NotAuthorizedError, match="not an active member"):
        await answer_course_question(
            user_id=99,
            classroom_id=1,
            topic_id=None,
            query="What is the exam schedule?",
        )

    mock_retrieve_chunks.assert_called_once_with(
        user_id=99,
        classroom_id=1,
        query_text="What is the exam schedule?",
        topic_id=None,
    )
    # CRITICAL: Verify LLM generation is NEVER called when unauthorized!
    mock_generate_answer.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.course_chat.retrieve_relevant_chunks")
@patch("app.services.course_chat.generate_answer")
async def test_course_chat_short_circuit_empty_chunks(mock_generate_answer, mock_retrieve_chunks):
    """Confirms empty retrieval short-circuits to fallback WITHOUT calling LLM API."""
    mock_retrieve_chunks.return_value = []

    result = await answer_course_question(
        user_id=1,
        classroom_id=1,
        topic_id=None,
        query="Unreferenced topic question?",
    )

    assert result["answer"] == UNGROUNDED_FALLBACK_ANSWER
    assert result["grounded"] is False
    assert result["sources"] == []

    # CRITICAL: Verify LLM generation is NEVER called when 0 chunks retrieved!
    mock_generate_answer.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.course_chat.retrieve_relevant_chunks")
@patch("app.services.course_chat.generate_answer")
async def test_course_chat_short_circuit_high_distance(mock_generate_answer, mock_retrieve_chunks):
    """Confirms chunks with distance >= 0.40 short-circuit to fallback WITHOUT calling LLM API."""
    mock_retrieve_chunks.return_value = [
        {
            "material_id": 5,
            "material_title": "Unrelated Syllabus PDF",
            "chunk_index": 0,
            "chunk_text": "Random text about sports...",
            "distance": 0.58,  # > MAX_RELEVANCE_DISTANCE (0.40)
        }
    ]

    result = await answer_course_question(
        user_id=1,
        classroom_id=1,
        topic_id=None,
        query="What is the pizza recipe?",
    )

    assert result["answer"] == UNGROUNDED_FALLBACK_ANSWER
    assert result["grounded"] is False
    assert result["sources"] == []

    # CRITICAL: Verify LLM generation is NEVER called when distance >= 0.40!
    mock_generate_answer.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.course_chat.retrieve_relevant_chunks")
@patch("app.services.course_chat.generate_answer")
async def test_course_chat_grounded_answer_success(mock_generate_answer, mock_retrieve_chunks):
    """Confirms relevant chunks (< 0.40 distance) invoke LLM and return grounded answer with sources."""
    mock_retrieve_chunks.return_value = [
        {
            "material_id": 8,
            "material_title": "DLP Architecture Overview",
            "chunk_index": 0,
            "chunk_text": "The DLP service uses FastAPI and pgvector for document processing.",
            "distance": 0.23,  # < MAX_RELEVANCE_DISTANCE (0.40)
        }
    ]
    mock_generate_answer.return_value = "The DLP service uses FastAPI and pgvector."

    result = await answer_course_question(
        user_id=1,
        classroom_id=1,
        topic_id=None,
        query="What database does DLP use?",
    )

    assert result["answer"] == "The DLP service uses FastAPI and pgvector."
    assert result["grounded"] is True
    assert len(result["sources"]) == 1
    assert result["sources"][0] == {
        "material_title": "DLP Architecture Overview",
        "material_id": 8,
        "chunk_index": 0,
    }

    mock_generate_answer.assert_called_once()
    system_prompt_arg, query_arg = mock_generate_answer.call_args[0]
    assert "DLP Architecture Overview" in system_prompt_arg
    assert "FastAPI and pgvector" in system_prompt_arg
    assert query_arg == "What database does DLP use?"


@pytest.mark.asyncio
@patch("app.services.course_chat.retrieve_relevant_chunks")
@patch("app.services.course_chat.generate_answer")
async def test_course_chat_socratic_mode_prompt_variation(mock_generate_answer, mock_retrieve_chunks):
    """Confirms socratic_mode=True produces a distinct Socratic prompt with guiding/hint instructions."""
    mock_retrieve_chunks.return_value = [
        {
            "material_id": 8,
            "material_title": "DLP Architecture Overview",
            "chunk_index": 0,
            "chunk_text": "The DLP service uses FastAPI and pgvector.",
            "distance": 0.20,
        }
    ]
    mock_generate_answer.return_value = "What kind of database do you think handles vector similarity searches best?"

    # 1. Non-Socratic call
    await answer_course_question(
        user_id=1,
        classroom_id=1,
        topic_id=None,
        query="What database does DLP use?",
        socratic_mode=False,
    )
    direct_prompt = mock_generate_answer.call_args[0][0]

    mock_generate_answer.reset_mock()

    # 2. Socratic call
    result = await answer_course_question(
        user_id=1,
        classroom_id=1,
        topic_id=None,
        query="What database does DLP use?",
        socratic_mode=True,
    )
    socratic_prompt = mock_generate_answer.call_args[0][0]

    # Verify response metadata
    assert result["grounded"] is True
    assert len(result["sources"]) == 1

    # Verify prompts differ
    assert direct_prompt != socratic_prompt

    # Verify Socratic framing instructions
    assert "Socratic course tutor" in socratic_prompt
    assert "Do NOT reveal the full, direct answer right away" in socratic_prompt
    assert "guiding question or provide a targeted hint" in socratic_prompt
    assert "DLP Architecture Overview" in socratic_prompt


@pytest.mark.asyncio
@patch("app.services.course_chat.retrieve_relevant_chunks")
@patch("app.services.course_chat.generate_answer")
async def test_course_chat_socratic_mode_no_grounded_context_fallback(mock_generate_answer, mock_retrieve_chunks):
    """Confirms socratic_mode=True still returns standard fallback when no grounded context is found without calling LLM."""
    mock_retrieve_chunks.return_value = []

    result = await answer_course_question(
        user_id=1,
        classroom_id=1,
        topic_id=None,
        query="Unrelated question",
        socratic_mode=True,
    )

    assert result["answer"] == UNGROUNDED_FALLBACK_ANSWER
    assert result["grounded"] is False
    assert result["sources"] == []
    mock_generate_answer.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.course_chat.retrieve_relevant_chunks")
@patch("app.services.course_chat.generate_answer")
async def test_course_chat_socratic_mode_isolation(mock_generate_answer, mock_retrieve_chunks):
    """Confirms Socratic Course Mode prompt isolates from both General Mode and direct Course Mode framing."""
    mock_retrieve_chunks.return_value = [
        {
            "material_id": 8,
            "material_title": "Physics Notes",
            "chunk_index": 0,
            "chunk_text": "Newton's second law states that F = ma.",
            "distance": 0.15,
        }
    ]
    mock_generate_answer.return_value = "What happens to acceleration if force increases?"

    await answer_course_question(
        user_id=1,
        classroom_id=1,
        topic_id=None,
        query="What is Newton's second law?",
        socratic_mode=True,
    )

    socratic_course_prompt = mock_generate_answer.call_args[0][0]

    # Does NOT contain General Mode's broad-knowledge directives
    assert "broad knowledge" not in socratic_course_prompt
    assert "general-purpose learning assistant" not in socratic_course_prompt
    assert "full general knowledge base" not in socratic_course_prompt

    # Does NOT contain normal direct Course Mode's direct-answer framing
    assert "Your task is to answer the student's question ONLY" not in socratic_course_prompt
    assert "directly responsive to the query" not in socratic_course_prompt

    # DOES contain grounded materials and Socratic guidance
    assert "Classroom Context Materials" in socratic_course_prompt
    assert "Do NOT reveal the full, direct answer right away" in socratic_course_prompt

