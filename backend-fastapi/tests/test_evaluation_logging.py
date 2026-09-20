"""
Unit tests for AI Evaluation Logging (Step 42)

Tests:
1. Table schema & model definition.
2. CRITICAL: Logging failure (DB write error) does NOT propagate — the underlying feature
   returns its normal response without crashing or delay.
3. log_ai_interaction helper calls from all 4 integration points with correct parameters:
   - Course Chat (grounded and fallback branches)
   - General Chat
   - Content Generation (quiz and study plan)
   - Personalized Learning Assistant
4. Feedback endpoint (POST /evaluation/feedback):
   - Updates rating and reason
   - 404 on missing log ID
   - 401 on unauthorized
   - 422 on invalid rating value
5. Summary endpoint (GET /evaluation/summary):
   - Computes accurate grounded rate, fallback rate, citation coverage proxy,
     average latency, feedback breakdown, and returns the citation proxy disclaimer.
"""

import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.db.models import AIInteractionLog
from app.services.evaluation_logging import (
    log_ai_interaction,
    record_feedback,
    get_evaluation_summary,
)

client = TestClient(app)
HEADERS = {"X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET}


# =====================================================================
# 1. SCHEMA / MODEL VERIFICATION
# =====================================================================

def test_ai_interaction_log_model_fields():
    """Verifies that AIInteractionLog has all required columns per the spec."""
    columns = AIInteractionLog.__table__.columns.keys()
    required_fields = [
        "id",
        "interaction_id",
        "interaction_type",
        "user_id",
        "classroom_id",
        "model",
        "grounded",
        "retrieved_chunk_ids",
        "retrieved_chunk_count",
        "socratic_mode",
        "latency_ms",
        "query_text",
        "answer_text",
        "error_occurred",
        "error_message",
        "feedback_rating",
        "feedback_reason",
        "created_at",
    ]
    for field in required_fields:
        assert field in columns, f"Missing required column: {field}"


# =====================================================================
# 2. CRITICAL TEST: LOGGING FAILURE NEVER BREAKS THE FEATURE
# =====================================================================

@pytest.mark.asyncio
async def test_log_ai_interaction_catches_db_exception_and_returns_none(caplog):
    """
    Directly tests that log_ai_interaction catches any database failure,
    logs a warning, and returns None rather than raising an exception.
    """
    with patch("app.services.evaluation_logging.async_session_maker") as mock_session_maker:
        mock_session = AsyncMock()
        mock_session.__aenter__.side_effect = Exception("Simulated DB connection timeout")
        mock_session_maker.return_value = mock_session

        res = await log_ai_interaction(
            interaction_type="COURSE_CHAT",
            user_id=1,
            classroom_id=1,
            model="gemini-3.6-flash",
            latency_ms=120,
            grounded=True,
            query_text="Sample query",
            answer_text="Sample answer",
        )

        assert res is None
        assert "Failed to record AI interaction log" in caplog.text


@pytest.mark.asyncio
@patch("app.services.course_chat.retrieve_relevant_chunks")
@patch("app.services.course_chat.generate_answer")
@patch("app.services.course_chat.log_ai_interaction")
async def test_course_chat_succeeds_even_if_evaluation_logging_fails(
    mock_log, mock_gen_answer, mock_retrieve
):
    """
    MOST IMPORTANT TEST IN STEP 42:
    Even if log_ai_interaction raises an unexpected exception or fails,
    course_chat MUST return its normal successful grounded response.
    """
    from app.services.course_chat import answer_course_question

    mock_retrieve.return_value = [
        {
            "id": "101",
            "chunk_text": "Photosynthesis is the process by which plants make food.",
            "chunk_index": 0,
            "distance": 0.15,
            "material_title": "Biology Notes",
            "material_id": 5,
        }
    ]
    mock_gen_answer.return_value = "Photosynthesis creates glucose and oxygen."
    mock_log.side_effect = Exception("Fatal database crash during log write!")

    # The call should complete without raising any error
    result = await answer_course_question(
        user_id=10,
        classroom_id=1,
        topic_id=None,
        query="Explain photosynthesis",
    )

    assert result["grounded"] is True
    assert result["answer"] == "Photosynthesis creates glucose and oxygen."
    assert len(result["sources"]) == 1
    assert mock_log.called


@pytest.mark.asyncio
@patch("app.services.general_chat.is_authorized_for_classroom")
@patch("app.services.general_chat.generate_answer")
@patch("app.services.general_chat.log_ai_interaction")
async def test_general_chat_succeeds_even_if_evaluation_logging_fails(
    mock_log, mock_gen_answer, mock_is_authorized
):
    """General chat still succeeds even if log_ai_interaction fails."""
    from app.services.general_chat import answer_general_question

    mock_is_authorized.return_value = True
    mock_gen_answer.return_value = "Linear algebra is the branch of math concerning linear equations."
    mock_log.side_effect = RuntimeError("Logging DB dead")

    result = await answer_general_question(
        user_id=5,
        classroom_id=1,
        query="What is linear algebra?",
    )

    assert result["grounded"] is False
    assert result["answer"] == "Linear algebra is the branch of math concerning linear equations."
    assert mock_log.called


# =====================================================================
# 3. INSTRUMENTATION PARAMETER VERIFICATION (4 INTEGRATION POINTS)
# =====================================================================

@pytest.mark.asyncio
@patch("app.services.course_chat.retrieve_relevant_chunks")
@patch("app.services.course_chat.generate_answer")
@patch("app.services.course_chat.log_ai_interaction")
async def test_course_chat_logging_parameters_grounded(
    mock_log, mock_gen_answer, mock_retrieve
):
    """Verifies correct parameters logged for grounded course chat."""
    from app.services.course_chat import answer_course_question

    mock_retrieve.return_value = [
        {
            "id": "42",
            "chunk_text": "Sample text",
            "chunk_index": 1,
            "distance": 0.1,
            "material_title": "Guide",
            "material_id": 12,
        }
    ]
    mock_gen_answer.return_value = "A grounded answer."
    mock_log.return_value = uuid.uuid4()

    await answer_course_question(
        user_id=100,
        classroom_id=5,
        topic_id=None,
        query="Explain X",
        socratic_mode=True,
    )

    mock_log.assert_called_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs["interaction_type"] == "COURSE_CHAT"
    assert kwargs["user_id"] == 100
    assert kwargs["classroom_id"] == 5
    assert kwargs["grounded"] is True
    assert kwargs["retrieved_chunk_ids"] == ["42"]
    assert kwargs["socratic_mode"] is True
    assert kwargs["latency_ms"] >= 0
    assert kwargs["model"] == "gemini-3.6-flash"


@pytest.mark.asyncio
@patch("app.services.course_chat.retrieve_relevant_chunks")
@patch("app.services.course_chat.generate_answer")
@patch("app.services.course_chat.log_ai_interaction")
async def test_course_chat_logging_parameters_fallback(
    mock_log, mock_gen_answer, mock_retrieve
):
    """Verifies correct parameters logged for fallback course chat."""
    from app.services.course_chat import answer_course_question

    mock_retrieve.return_value = []
    mock_log.return_value = uuid.uuid4()

    await answer_course_question(
        user_id=100,
        classroom_id=5,
        topic_id=None,
        query="Explain unindexed topic",
        socratic_mode=False,
    )

    mock_log.assert_called_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs["interaction_type"] == "COURSE_CHAT"
    assert kwargs["grounded"] is False
    assert kwargs["retrieved_chunk_ids"] == []
    assert kwargs["socratic_mode"] is False


@pytest.mark.asyncio
@patch("app.services.general_chat.is_authorized_for_classroom")
@patch("app.services.general_chat.generate_answer")
@patch("app.services.general_chat.log_ai_interaction")
async def test_general_chat_logging_parameters(mock_log, mock_gen_answer, mock_is_authorized):
    """Verifies correct parameters logged for general chat."""
    from app.services.general_chat import answer_general_question

    mock_is_authorized.return_value = True
    mock_gen_answer.return_value = "General explanation."
    mock_log.return_value = uuid.uuid4()

    await answer_general_question(
        user_id=88,
        classroom_id=1,
        query="What is quantum mechanics?",
        socratic_mode=True,
    )

    mock_log.assert_called_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs["interaction_type"] == "GENERAL_CHAT"
    assert kwargs["user_id"] == 88
    assert kwargs["classroom_id"] == 1
    assert kwargs["grounded"] is False
    assert kwargs["socratic_mode"] is True
    assert kwargs["latency_ms"] >= 0


@pytest.mark.asyncio
@patch("app.services.content_generation.is_teacher_for_classroom")
@patch("app.services.content_generation._get_topic_title")
@patch("app.services.content_generation.retrieve_relevant_chunks")
@patch("app.services.content_generation._call_gemini_structured")
@patch("app.services.content_generation._post_draft_to_django")
@patch("app.services.content_generation.log_ai_interaction")
async def test_quiz_generation_logging_parameters(
    mock_log, mock_post, mock_gemini, mock_retrieve, mock_topic, mock_is_teacher
):
    """Verifies correct parameters logged for quiz generation."""
    from app.services.content_generation import generate_quiz_draft

    mock_is_teacher.return_value = True
    mock_topic.return_value = "Cell Division"
    mock_retrieve.return_value = [{"id": 301, "chunk_text": "Mitosis overview"}]
    mock_gemini.return_value = (
        '{"title": "Mitosis Quiz", "questions": ['
        '{"question": "What occurs in prophase?", "option_a": "DNA condenses", '
        '"option_b": "Cytokinesis", "option_c": "Resting", "option_d": "None", '
        '"correct_option": "A", "explanation": "Chromatin condenses into chromosomes."}'
        ']}'
    )
    mock_post.return_value = {"id": 1, "status": "DRAFT"}
    mock_log.return_value = uuid.uuid4()

    await generate_quiz_draft(classroom_id=10, topic_id=20, teacher_user_id=2, num_questions=1)

    mock_log.assert_called_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs["interaction_type"] == "QUIZ_GENERATION"
    assert kwargs["user_id"] == 2
    assert kwargs["classroom_id"] == 10
    assert kwargs["grounded"] is True
    assert kwargs["retrieved_chunk_ids"] == [301]
    assert kwargs["error_occurred"] is False


@pytest.mark.asyncio
@patch("app.services.content_generation.is_authorized_for_classroom")
@patch("app.services.content_generation.get_student_progress_data")
@patch("app.services.content_generation.get_weak_topics_data")
@patch("app.services.content_generation._call_gemini_structured")
@patch("app.services.content_generation._post_draft_to_django")
@patch("app.services.content_generation.log_ai_interaction")
async def test_study_plan_generation_logging_parameters(
    mock_log, mock_post, mock_gemini, mock_weak, mock_prog, mock_auth
):
    """Verifies correct parameters logged for study plan generation."""
    from app.services.content_generation import generate_study_plan_draft

    mock_auth.return_value = True
    mock_prog.return_value = {"progress_summary": {"completion_percentage": 40.0, "completed_topics": 2, "total_topics": 5}}
    mock_weak.return_value = []
    mock_gemini.return_value = (
        '{"title": "Personal Plan", "overview": "Focus on fundamentals", "tasks": ['
        '{"title": "Read Chapter 1", "description": "Review notes", "suggested_pacing": "Day 1", "target_topic_name": "Topic 1"}'
        ']}'
    )
    mock_post.return_value = {"id": 2, "status": "DRAFT"}
    mock_log.return_value = uuid.uuid4()

    await generate_study_plan_draft(
        classroom_id=5,
        student_user_id=8,
        requesting_user_id=8,
        goal_description="Prepare for midterm",
    )

    mock_log.assert_called_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs["interaction_type"] == "STUDY_PLAN_GENERATION"
    assert kwargs["user_id"] == 8
    assert kwargs["classroom_id"] == 5
    assert kwargs["grounded"] is True
    assert kwargs["retrieved_chunk_ids"] == []
    assert kwargs["error_occurred"] is False


@pytest.mark.asyncio
@patch("app.services.personalized_assistant.is_authorized_for_classroom")
@patch("app.services.personalized_assistant.get_pending_tasks_data")
@patch("app.services.personalized_assistant.get_weak_topics_data")
@patch("app.services.personalized_assistant.recommend_next_topic_data")
@patch("app.services.personalized_assistant.get_student_progress_data")
@patch("app.services.personalized_assistant.generate_answer")
@patch("app.services.personalized_assistant.log_ai_interaction")
async def test_personalized_assistant_logging_parameters(
    mock_log, mock_gen_answer, mock_prog, mock_rec, mock_weak, mock_tasks, mock_auth
):
    """Verifies correct parameters logged for personalized assistant."""
    from app.services.personalized_assistant import get_daily_recommendation

    mock_auth.return_value = True
    mock_tasks.return_value = {"total_pending_tasks": 0, "pending_assignments": [], "pending_quizzes": []}
    mock_weak.return_value = {"weak_topics": []}
    mock_rec.return_value = {"recommended_topic": {"title": "Topic 1", "course_title": "C1", "module_title": "M1"}}
    mock_prog.return_value = {"summary_stats": {"completion_percentage": 50.0, "completed_topics": 1, "total_topics": 2}}
    mock_gen_answer.return_value = "Here is your study plan for today."
    mock_log.return_value = uuid.uuid4()

    await get_daily_recommendation(user_id=7, classroom_id=1)

    mock_log.assert_called_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs["interaction_type"] == "PERSONALIZED_ASSISTANT"
    assert kwargs["user_id"] == 7
    assert kwargs["classroom_id"] == 1
    assert kwargs["grounded"] is True
    assert kwargs["error_occurred"] is False


# =====================================================================
# 4. FEEDBACK ENDPOINT TESTS
# =====================================================================

def test_feedback_endpoint_unauthorized():
    """POST /evaluation/feedback requires X-Internal-Secret."""
    res = client.post("/evaluation/feedback", json={"log_id": str(uuid.uuid4()), "rating": "up"})
    assert res.status_code == 401


@patch("app.api.evaluation.record_feedback")
def test_feedback_endpoint_success(mock_record_feedback):
    """POST /evaluation/feedback records rating and reason."""
    mock_log_id = uuid.uuid4()
    mock_record_feedback.return_value = {
        "status": "success",
        "log_id": str(mock_log_id),
        "feedback_rating": "up",
        "feedback_reason": "Very helpful explanation",
    }

    payload = {
        "log_id": str(mock_log_id),
        "rating": "up",
        "reason": "Very helpful explanation",
    }
    res = client.post("/evaluation/feedback", json=payload, headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["rating"] == "up"
    assert data["log_id"] == str(mock_log_id)


@patch("app.api.evaluation.record_feedback")
def test_feedback_endpoint_not_found(mock_record_feedback):
    """POST /evaluation/feedback returns 404 if log_id doesn't exist."""
    mock_record_feedback.return_value = None

    payload = {
        "log_id": str(uuid.uuid4()),
        "rating": "down",
        "reason": "Irrelevant answer",
    }
    res = client.post("/evaluation/feedback", json=payload, headers=HEADERS)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]


def test_feedback_endpoint_invalid_rating():
    """POST /evaluation/feedback rejects rating values other than 'up' or 'down'."""
    payload = {
        "log_id": str(uuid.uuid4()),
        "rating": "neutral",
    }
    res = client.post("/evaluation/feedback", json=payload, headers=HEADERS)
    assert res.status_code == 422


# =====================================================================
# 5. SUMMARY ENDPOINT & ARITHMETIC VERIFICATION
# =====================================================================

def test_summary_endpoint_unauthorized():
    """GET /evaluation/summary requires X-Internal-Secret."""
    res = client.get("/evaluation/summary")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_evaluation_summary_arithmetic():
    """
    Constructs a known dataset of mock AIInteractionLog objects and directly verifies:
    1. Grounded answer rate (grounded=True / total COURSE_CHAT)
    2. Fallback rate (grounded=False / total COURSE_CHAT)
    3. Citation coverage proxy (grounded with chunks / total grounded)
    4. Feedback breakdown
    5. Latency averages
    6. Citation coverage disclaimer note
    """
    # Create 4 COURSE_CHAT:
    # - 2 grounded with chunks
    # - 1 grounded without chunks (corner case)
    # - 1 fallback (grounded=False)
    # Total COURSE_CHAT = 4
    # Grounded rate = 3 / 4 = 0.75 (75.0%)
    # Fallback rate = 1 / 4 = 0.25 (25.0%)
    # Citation coverage = 2 / 3 = 0.6667 (66.67%)
    logs = [
        AIInteractionLog(
            id=uuid.uuid4(),
            interaction_id=uuid.uuid4(),
            interaction_type="COURSE_CHAT",
            user_id=1,
            classroom_id=1,
            model="gemini-3.6-flash",
            grounded=True,
            retrieved_chunk_count=2,
            retrieved_chunk_ids=[1, 2],
            latency_ms=100,
            feedback_rating="up",
            feedback_reason="Good",
            error_occurred=False,
            created_at=datetime.now(timezone.utc),
        ),
        AIInteractionLog(
            id=uuid.uuid4(),
            interaction_id=uuid.uuid4(),
            interaction_type="COURSE_CHAT",
            user_id=2,
            classroom_id=1,
            model="gemini-3.6-flash",
            grounded=True,
            retrieved_chunk_count=1,
            retrieved_chunk_ids=[3],
            latency_ms=200,
            feedback_rating="down",
            feedback_reason="Too brief",
            error_occurred=False,
            created_at=datetime.now(timezone.utc),
        ),
        AIInteractionLog(
            id=uuid.uuid4(),
            interaction_id=uuid.uuid4(),
            interaction_type="COURSE_CHAT",
            user_id=3,
            classroom_id=1,
            model="gemini-3.6-flash",
            grounded=True,
            retrieved_chunk_count=0,
            retrieved_chunk_ids=[],
            latency_ms=150,
            feedback_rating=None,
            error_occurred=False,
            created_at=datetime.now(timezone.utc),
        ),
        AIInteractionLog(
            id=uuid.uuid4(),
            interaction_id=uuid.uuid4(),
            interaction_type="COURSE_CHAT",
            user_id=4,
            classroom_id=1,
            model="gemini-3.6-flash",
            grounded=False,
            retrieved_chunk_count=0,
            retrieved_chunk_ids=[],
            latency_ms=80,
            feedback_rating=None,
            error_occurred=False,
            created_at=datetime.now(timezone.utc),
        ),
        # 1 GENERAL_CHAT
        AIInteractionLog(
            id=uuid.uuid4(),
            interaction_id=uuid.uuid4(),
            interaction_type="GENERAL_CHAT",
            user_id=1,
            classroom_id=None,
            model="gemini-3.6-flash",
            grounded=False,
            retrieved_chunk_count=0,
            retrieved_chunk_ids=[],
            latency_ms=120,
            feedback_rating=None,
            error_occurred=False,
            created_at=datetime.now(timezone.utc),
        ),
        # 1 QUIZ_GENERATION with error
        AIInteractionLog(
            id=uuid.uuid4(),
            interaction_id=uuid.uuid4(),
            interaction_type="QUIZ_GENERATION",
            user_id=1,
            classroom_id=1,
            model="gemini-3.6-flash",
            grounded=True,
            retrieved_chunk_count=3,
            retrieved_chunk_ids=[10, 11, 12],
            latency_ms=500,
            feedback_rating=None,
            error_occurred=True,
            error_message="Validation error",
            created_at=datetime.now(timezone.utc),
        ),
    ]

    with patch("app.services.evaluation_logging.async_session_maker") as mock_maker:
        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = logs
        mock_res = MagicMock()
        mock_res.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_res
        mock_maker.return_value.__aenter__.return_value = mock_session

        summary = await get_evaluation_summary()

        assert summary["total_interactions"] == 6
        assert summary["interaction_counts"]["COURSE_CHAT"] == 4
        assert summary["interaction_counts"]["GENERAL_CHAT"] == 1
        assert summary["interaction_counts"]["QUIZ_GENERATION"] == 1

        # Grounded rate and fallback rate
        cc = summary["course_chat_metrics"]
        assert cc["total_course_chats"] == 4
        assert cc["grounded_answer_rate"] == 0.75
        assert cc["fallback_rate"] == 0.25

        # Citation coverage proxy: 2 out of 3 grounded had chunks => 2/3 = 0.6667
        assert cc["citation_coverage"] == 0.6667

        # Average latency: (100 + 200 + 150 + 80 + 120 + 500) / 6 = 1150 / 6 = 191.67 ms
        lat = summary["latency_metrics"]
        assert lat["overall_average_latency_ms"] == 191.67
        assert lat["latency_by_type"]["COURSE_CHAT"] == 132.5

        # Feedback
        fb = summary["feedback_metrics"]
        assert fb["total_feedback_count"] == 2
        assert fb["up_count"] == 1
        assert fb["down_count"] == 1
        assert fb["feedback_rate"] == 0.3333

        # Error rate: 1 out of 6 => 0.1667
        assert summary["error_rate"] == 0.1667

        # Disclaimer note check
        assert "citation_coverage_note" in cc
        assert "proxy" in cc["citation_coverage_note"]


@pytest.mark.asyncio
async def test_citation_coverage_invariant_100_percent_when_all_grounded_have_chunks():
    """
    CRITICAL INVARIANT TEST:
    Per Course Mode design (Step 34), grounded=True is only ever set when at least
    one chunk passed the relevance threshold.
    Therefore, in any valid production Course Mode interaction where grounded=True,
    retrieved_chunk_count must be >= 1.
    If a dataset has N grounded interactions where all N have retrieved_chunk_count >= 1,
    citation coverage MUST compute to exactly 100% (1.0).
    """
    # Create N grounded COURSE_CHAT interactions all with chunks >= 1
    # Plus M fallback COURSE_CHAT interactions with chunk_count = 0
    N = 5
    M = 2
    logs = []

    for i in range(N):
        logs.append(
            AIInteractionLog(
                id=uuid.uuid4(),
                interaction_id=uuid.uuid4(),
                interaction_type="COURSE_CHAT",
                user_id=2,
                classroom_id=6,
                model="gemini-3.6-flash",
                grounded=True,
                retrieved_chunk_count=2,
                retrieved_chunk_ids=[f"chunk-{i}-1", f"chunk-{i}-2"],
                latency_ms=150,
                feedback_rating=None,
                error_occurred=False,
                created_at=datetime.now(timezone.utc),
            )
        )

    for j in range(M):
        logs.append(
            AIInteractionLog(
                id=uuid.uuid4(),
                interaction_id=uuid.uuid4(),
                interaction_type="COURSE_CHAT",
                user_id=2,
                classroom_id=6,
                model="gemini-3.6-flash",
                grounded=False,
                retrieved_chunk_count=0,
                retrieved_chunk_ids=[],
                latency_ms=80,
                feedback_rating=None,
                error_occurred=False,
                created_at=datetime.now(timezone.utc),
            )
        )

    with patch("app.services.evaluation_logging.async_session_maker") as mock_maker:
        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = logs
        mock_res = MagicMock()
        mock_res.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_res
        mock_maker.return_value.__aenter__.return_value = mock_session

        summary = await get_evaluation_summary(classroom_id=6)

        cc = summary["course_chat_metrics"]
        assert cc["total_course_chats"] == N + M  # 7
        assert cc["grounded_answer_rate"] == round(N / (N + M), 4)  # 5/7 = 0.7143

        # Invariant: citation coverage MUST be 1.0 (100.0%) because all grounded interactions had chunks
        assert cc["citation_coverage"] == 1.0, (
            f"Expected citation coverage 1.0 (100%), got {cc['citation_coverage']}"
        )

