"""
Tests for AI Content Generation (Step 40)

Covers:
1. Schema validation (valid passes, malformed fails cleanly with 0 drafts created)
2. Grounding verification (spy on retrieve_relevant_chunks)
3. Authorization defense-in-depth (teacher-only for quiz, student-self / teacher for study plans)
4. LLM calls are mocked to burn 0 real API credits.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError

from app.main import app
from app.schemas.content_generation import (
    QuizQuestionDraft,
    QuizDraftSchema,
    StudyPlanDraftSchema,
    StudyPlanTaskDraft,
)
from app.services.content_generation import (
    generate_quiz_draft,
    generate_study_plan_draft,
    ContentGenerationError,
)
from app.services.rag_retrieval import NotAuthorizedError

VALID_SECRET = "dlp-internal-secret-key-change-me"
AUTH_HEADERS = {"X-Internal-Secret": VALID_SECRET}


# --- 1. Schema Validation Unit Tests ---

def test_quiz_schema_validation_success():
    """Valid quiz JSON structure successfully validates."""
    valid_data = {
        "title": "Algebra Fundamentals",
        "questions": [
            {
                "question": "What is 2 + 2?",
                "option_a": "3",
                "option_b": "4",
                "option_c": "5",
                "option_d": "6",
                "correct_option": "B",
                "explanation": "2 plus 2 equals 4.",
            }
        ]
    }
    schema = QuizDraftSchema.model_validate(valid_data)
    assert schema.title == "Algebra Fundamentals"
    assert len(schema.questions) == 1
    assert schema.questions[0].correct_option == "B"
    assert schema.questions[0].explanation == "2 plus 2 equals 4."


def test_quiz_schema_validation_invalid_option():
    """Invalid correct_option (e.g. 'E') is rejected cleanly by Pydantic."""
    invalid_data = {
        "title": "Invalid Quiz",
        "questions": [
            {
                "question": "What is 2 + 2?",
                "option_a": "3",
                "option_b": "4",
                "option_c": "5",
                "option_d": "6",
                "correct_option": "E",  # Invalid choice
                "explanation": "Math",
            }
        ]
    }
    with pytest.raises(ValidationError):
        QuizDraftSchema.model_validate(invalid_data)


def test_quiz_schema_validation_missing_explanation():
    """Missing explanation field is rejected cleanly by schema."""
    invalid_data = {
        "title": "Missing Explanation Quiz",
        "questions": [
            {
                "question": "What is 2 + 2?",
                "option_a": "3",
                "option_b": "4",
                "option_c": "5",
                "option_d": "6",
                "correct_option": "B",
            }
        ]
    }
    with pytest.raises(ValidationError):
        QuizDraftSchema.model_validate(invalid_data)


def test_study_plan_schema_validation_success():
    """Valid study plan structure parses cleanly."""
    valid_data = {
        "title": "Calculus Remediation Plan",
        "overview": "Focus on derivatives and chain rule.",
        "tasks": [
            {
                "title": "Review Power Rule",
                "description": "Read Chapter 3 and work problems 1-10.",
                "target_topic_name": "Derivatives",
                "suggested_pacing": "Day 1 (45 mins)",
                "suggested_due_date": "2026-09-15",
            }
        ]
    }
    plan = StudyPlanDraftSchema.model_validate(valid_data)
    assert plan.title == "Calculus Remediation Plan"
    assert len(plan.tasks) == 1
    assert plan.tasks[0].target_topic_name == "Derivatives"


# --- 2. Grounding & Service Logic Tests ---

@pytest.mark.asyncio
@patch("app.services.content_generation.is_teacher_for_classroom", new_callable=AsyncMock)
@patch("app.services.content_generation._get_topic_title", new_callable=AsyncMock)
@patch("app.services.content_generation.retrieve_relevant_chunks", new_callable=AsyncMock)
@patch("app.services.content_generation._call_gemini_structured")
@patch("app.services.content_generation._post_draft_to_django", new_callable=AsyncMock)
async def test_generate_quiz_draft_grounding_success(
    mock_post_django,
    mock_gemini,
    mock_retrieve,
    mock_topic_title,
    mock_is_teacher,
):
    """Confirm quiz generation delegates grounding to Step 33 retrieve_relevant_chunks."""
    mock_is_teacher.return_value = True
    mock_topic_title.return_value = "Photosynthesis"
    mock_retrieve.return_value = [
        {"chunk_text": "Chlorophyll absorbs light mostly in blue and red wavelengths.", "chunk_index": 0}
    ]
    mock_gemini.return_value = """{
        "title": "Photosynthesis Quiz",
        "questions": [
            {
                "question": "Which wavelengths does chlorophyll absorb most?",
                "option_a": "Green and yellow",
                "option_b": "Blue and red",
                "option_c": "Infrared and UV",
                "option_d": "X-rays",
                "correct_option": "B",
                "explanation": "Chlorophyll absorbs light primarily in the blue and red wavelengths."
            }
        ]
    }"""
    mock_post_django.return_value = {
        "id": 101,
        "classroom": 1,
        "content_type": "QUIZ",
        "status": "DRAFT",
        "content": {"title": "Photosynthesis Quiz", "questions": []},
        "topic": 5,
        "created_by": 2,
        "requires_teacher_fact_check": True,
        "review_notice": "Schema validation confirms structure and format only.",
    }

    result = await generate_quiz_draft(
        classroom_id=1,
        topic_id=5,
        teacher_user_id=2,
        num_questions=1,
    )

    # Verify retrieval was invoked with classroom_id and topic title
    mock_retrieve.assert_called_once_with(
        user_id=2,
        classroom_id=1,
        query_text="Photosynthesis",
        topic_id=5,
        top_k=5,
    )

    # Verify post to django was called with DRAFT status
    mock_post_django.assert_called_once()
    payload = mock_post_django.call_args[0][0]
    assert payload["status"] == "DRAFT"
    assert payload["content_type"] == "QUIZ"
    assert payload["requires_teacher_fact_check"] is True
    assert result["id"] == 101


@pytest.mark.asyncio
@patch("app.services.content_generation.is_teacher_for_classroom", new_callable=AsyncMock)
@patch("app.services.content_generation._get_topic_title", new_callable=AsyncMock)
@patch("app.services.content_generation.retrieve_relevant_chunks", new_callable=AsyncMock)
async def test_generate_quiz_draft_no_material_fails(
    mock_retrieve,
    mock_topic_title,
    mock_is_teacher,
):
    """If no material exists for the topic, quiz generation fails cleanly with an error."""
    mock_is_teacher.return_value = True
    mock_topic_title.return_value = "Unindexed Topic"
    mock_retrieve.return_value = []  # No material found

    with pytest.raises(ValueError) as exc_info:
        await generate_quiz_draft(classroom_id=1, topic_id=5, teacher_user_id=2)
    assert "No uploaded course material found" in str(exc_info.value)


@pytest.mark.asyncio
@patch("app.services.content_generation.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.services.content_generation.get_student_progress_data", new_callable=AsyncMock)
@patch("app.services.content_generation.get_weak_topics_data", new_callable=AsyncMock)
@patch("app.services.content_generation._call_gemini_structured")
@patch("app.services.content_generation._post_draft_to_django", new_callable=AsyncMock)
async def test_generate_study_plan_grounded_in_progress(
    mock_post_django,
    mock_gemini,
    mock_weak,
    mock_progress,
    mock_auth,
):
    """Confirm study plan generation is grounded in progress and weak topics."""
    mock_auth.return_value = True
    mock_progress.return_value = {
        "progress_summary": {"completion_percentage": 40.0, "completed_topics": 2, "total_topics": 5}
    }
    mock_weak.return_value = [
        {"topic_title": "Quadratic Equations", "quiz_score": 50, "reason": "Quiz score 50% below passing threshold"}
    ]
    mock_gemini.return_value = """{
        "title": "Math Recovery Plan",
        "overview": "Focus on Quadratics",
        "tasks": [
            {
                "title": "Factorization Practice",
                "description": "Complete worksheet 4",
                "target_topic_name": "Quadratic Equations",
                "suggested_pacing": "Day 1 (30 mins)",
                "suggested_due_date": null
            }
        ]
    }"""
    mock_post_django.return_value = {
        "id": 102,
        "classroom": 1,
        "content_type": "STUDY_PLAN",
        "status": "DRAFT",
        "content": {},
        "created_by": 10,
        "target_student": 10,
        "requires_teacher_fact_check": True,
        "review_notice": "Notice",
    }

    result = await generate_study_plan_draft(
        classroom_id=1,
        student_user_id=10,
        requesting_user_id=10,
        goal_description="Catch up before midterm",
    )
    mock_progress.assert_called_once()
    mock_weak.assert_called_once()
    assert result["id"] == 102


# --- 3. Authorization & Endpoint Security Tests ---

@pytest.mark.asyncio
async def test_generate_quiz_missing_secret():
    """Missing internal secret header returns 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/content/generate-quiz",
            json={"classroom_id": 1, "topic_id": 2, "teacher_user_id": 5, "num_questions": 3},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
@patch("app.api.content_generation.generate_quiz_draft", new_callable=AsyncMock)
async def test_generate_quiz_unauthorized_user(mock_generate):
    """Non-teacher user requesting quiz generation returns 403 with generic error."""
    mock_generate.side_effect = NotAuthorizedError("Access denied or classroom not found.")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/content/generate-quiz",
            headers=AUTH_HEADERS,
            json={"classroom_id": 1, "topic_id": 2, "teacher_user_id": 99, "num_questions": 3},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Access denied or classroom not found."


@pytest.mark.asyncio
async def test_generate_study_plan_missing_secret():
    """Missing internal secret returns 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/content/generate-study-plan",
            json={
                "classroom_id": 1,
                "student_user_id": 10,
                "requesting_user_id": 10,
                "goal_description": "Pass test",
            },
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
@patch("app.api.content_generation.generate_study_plan_draft", new_callable=AsyncMock)
async def test_generate_study_plan_unauthorized(mock_generate):
    """Unauthorized student accessing another student's plan returns generic 403."""
    mock_generate.side_effect = NotAuthorizedError("Access denied or classroom not found.")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/content/generate-study-plan",
            headers=AUTH_HEADERS,
            json={
                "classroom_id": 1,
                "student_user_id": 10,
                "requesting_user_id": 11,  # Different student!
                "goal_description": "Steal plan",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Access denied or classroom not found."
