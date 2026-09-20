"""
Automated Unit Tests for Step 39: Personalized Learning Assistant

Validates:
1. In-process direct aggregation across all four data sources (progress, pending tasks, weak topics, recommendation).
2. Spy-based authorization short-circuit: unauthorized user never calls any underlying service or the LLM.
3. System prompt verification: spies on prompt passed to generate_answer to prove weak topics, tasks, and recommendations are interpolated faithfully.
4. "All caught up" scenario: student with 100% completion, no weak topics, and no pending tasks receives positive guidance.
5. Endpoint security & status codes: X-Internal-Secret enforcement, 403 on unauthorized membership, 200 on success.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.personalized_assistant import (
    get_daily_recommendation,
    build_assistant_system_prompt,
)
from app.services.rag_retrieval import NotAuthorizedError
from app.core.config import settings

client = TestClient(app)


# ============================================================================
# 1. SERVICE LAYER TESTS
# ============================================================================

@pytest.mark.asyncio
@patch("app.services.personalized_assistant.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.get_pending_tasks_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.get_weak_topics_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.recommend_next_topic_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.get_student_progress_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.generate_answer")
async def test_daily_recommendation_aggregates_all_four_sources(
    mock_generate_answer,
    mock_get_prog,
    mock_get_rec,
    mock_get_weak,
    mock_get_tasks,
    mock_is_auth,
):
    """Verifies that an authorized call aggregates all four data sources correctly into one payload."""
    mock_is_auth.return_value = True

    mock_get_tasks.return_value = {
        "classroom_id": 1,
        "student_id": 3,
        "total_pending_tasks": 2,
        "pending_assignments": [
            {"id": 10, "title": "HW 1", "due_date": "2026-09-10T00:00:00Z", "is_overdue": False}
        ],
        "pending_quizzes": [
            {"id": 20, "title": "Quiz 1", "topic_title": "Limits"}
        ],
    }

    mock_get_weak.return_value = {
        "classroom_id": 1,
        "student_id": 3,
        "threshold": 70,
        "total_weak_topics": 1,
        "weak_topics": [
            {
                "topic_id": 1,
                "topic_title": "Arithmetic Progressions",
                "quiz_score": 60,
                "reason": "Quiz score (60%) is below mastery threshold of 70%",
            }
        ],
    }

    mock_get_rec.return_value = {
        "classroom_id": 1,
        "student_id": 3,
        "recommended_topic": {
            "topic_id": 1,
            "title": "Arithmetic Progressions",
            "course_title": "Algebra",
            "module_title": "Sequences",
        },
        "reason": "Topic requires review due to low quiz score (60% < 70%)",
    }

    mock_get_prog.return_value = {
        "classroom_id": 1,
        "student_id": 3,
        "summary_stats": {
            "total_topics": 10,
            "completed_topics": 5,
            "completion_percentage": 50.0,
        },
    }

    mock_generate_answer.return_value = "Today you should review Arithmetic Progressions and finish HW 1."

    res = await get_daily_recommendation(user_id=3, classroom_id=1)

    assert "recommendation" in res
    assert res["recommendation"] == "Today you should review Arithmetic Progressions and finish HW 1."

    supporting = res["supporting_data"]
    assert supporting["progress_summary"]["completion_percentage"] == 50.0
    assert supporting["pending_tasks"]["total_pending"] == 2
    assert len(supporting["weak_topics"]) == 1
    assert supporting["weak_topics"][0]["topic_title"] == "Arithmetic Progressions"
    assert supporting["recommended_topic"]["title"] == "Arithmetic Progressions"

    # Confirm all 4 service calls were invoked with the correct arguments
    mock_get_tasks.assert_awaited_once_with(caller_user_id=3, classroom_id=1)
    mock_get_weak.assert_awaited_once_with(caller_user_id=3, classroom_id=1)
    mock_get_rec.assert_awaited_once_with(caller_user_id=3, classroom_id=1)
    mock_get_prog.assert_awaited_once_with(caller_user_id=3, classroom_id=1)


@pytest.mark.asyncio
@patch("app.services.personalized_assistant.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.get_pending_tasks_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.get_weak_topics_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.recommend_next_topic_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.get_student_progress_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.generate_answer")
async def test_daily_recommendation_unauthorized_short_circuits(
    mock_generate_answer,
    mock_get_prog,
    mock_get_rec,
    mock_get_weak,
    mock_get_tasks,
    mock_is_auth,
):
    """Verifies that an unauthorized user raises NotAuthorizedError immediately without hitting any service or LLM."""
    mock_is_auth.return_value = False

    with pytest.raises(NotAuthorizedError, match="Access denied or classroom not found"):
        await get_daily_recommendation(user_id=99, classroom_id=1)

    mock_is_auth.assert_awaited_once_with(user_id=99, classroom_id=1)
    mock_get_tasks.assert_not_called()
    mock_get_weak.assert_not_called()
    mock_get_rec.assert_not_called()
    mock_get_prog.assert_not_called()
    mock_generate_answer.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.personalized_assistant.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.get_pending_tasks_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.get_weak_topics_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.recommend_next_topic_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.get_student_progress_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.generate_answer")
async def test_daily_recommendation_prompt_interpolation_spy(
    mock_generate_answer,
    mock_get_prog,
    mock_get_rec,
    mock_get_weak,
    mock_get_tasks,
    mock_is_auth,
):
    """Spies on the exact system prompt string passed to generate_answer to ensure data is interpolated faithfully."""
    mock_is_auth.return_value = True

    mock_get_tasks.return_value = {
        "classroom_id": 1,
        "student_id": 3,
        "total_pending_tasks": 1,
        "pending_assignments": [
            {"id": 101, "title": "Calculus Project A", "due_date": "2026-09-15", "is_overdue": False}
        ],
        "pending_quizzes": [],
    }
    mock_get_weak.return_value = {
        "classroom_id": 1,
        "student_id": 3,
        "threshold": 70,
        "total_weak_topics": 1,
        "weak_topics": [
            {
                "topic_id": 5,
                "topic_title": "Taylor Series",
                "quiz_score": 58,
                "reason": "Quiz score (58%) is below mastery threshold of 70%",
            }
        ],
    }
    mock_get_rec.return_value = {
        "classroom_id": 1,
        "student_id": 3,
        "recommended_topic": {
            "topic_id": 5,
            "title": "Taylor Series",
            "course_title": "Calculus II",
            "module_title": "Infinite Series",
        },
        "reason": "Topic requires review due to low quiz score (58% < 70%)",
    }
    mock_get_prog.return_value = {
        "classroom_id": 1,
        "student_id": 3,
        "summary_stats": {
            "total_topics": 20,
            "completed_topics": 12,
            "completion_percentage": 60.0,
        },
    }

    mock_generate_answer.return_value = "Mock response"

    await get_daily_recommendation(user_id=3, classroom_id=1)

    # Inspect prompt passed to generate_answer
    assert mock_generate_answer.call_count == 1
    passed_prompt = mock_generate_answer.call_args[0][0]
    passed_query = mock_generate_answer.call_args[0][1]

    assert passed_query == "What should I study today?"
    # Check that real topic names and scores are in prompt
    assert "Taylor Series" in passed_prompt
    assert "Calculus Project A" in passed_prompt
    assert "58%" in passed_prompt
    assert "60.0%" in passed_prompt
    assert "STRICT GROUNDING & ACCURACY RULES" in passed_prompt


@pytest.mark.asyncio
@patch("app.services.personalized_assistant.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.get_pending_tasks_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.get_weak_topics_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.recommend_next_topic_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.get_student_progress_data", new_callable=AsyncMock)
@patch("app.services.personalized_assistant.generate_answer")
async def test_daily_recommendation_all_caught_up_case(
    mock_generate_answer,
    mock_get_prog,
    mock_get_rec,
    mock_get_weak,
    mock_get_tasks,
    mock_is_auth,
):
    """Verifies that the prompt and response handle the 'all caught up' scenario gracefully and encouragingly."""
    mock_is_auth.return_value = True

    mock_get_tasks.return_value = {
        "classroom_id": 1,
        "student_id": 3,
        "total_pending_tasks": 0,
        "pending_assignments": [],
        "pending_quizzes": [],
    }
    mock_get_weak.return_value = {
        "classroom_id": 1,
        "student_id": 3,
        "threshold": 70,
        "total_weak_topics": 0,
        "weak_topics": [],
    }
    mock_get_rec.return_value = {
        "classroom_id": 1,
        "student_id": 3,
        "recommended_topic": None,
        "reason": "All syllabus topics completed! Recommend reviewing previous topics or exploring advanced material.",
    }
    mock_get_prog.return_value = {
        "classroom_id": 1,
        "student_id": 3,
        "summary_stats": {
            "total_topics": 8,
            "completed_topics": 8,
            "completion_percentage": 100.0,
        },
    }

    mock_generate_answer.return_value = (
        "Congratulations! You are completely caught up and have mastered all 8 topics in this course. "
        "Take a well-deserved rest today!"
    )

    res = await get_daily_recommendation(user_id=3, classroom_id=1)

    assert "completely caught up" in res["recommendation"]
    assert res["supporting_data"]["progress_summary"]["completion_percentage"] == 100.0
    assert res["supporting_data"]["pending_tasks"]["total_pending"] == 0
    assert len(res["supporting_data"]["weak_topics"]) == 0
    assert res["supporting_data"]["recommended_topic"] is None

    # Check prompt has celebratory instructions
    passed_prompt = mock_generate_answer.call_args[0][0]
    assert "SPECIAL GUIDANCE FOR ALL-CAUGHT-UP STUDENTS" in passed_prompt


# ============================================================================
# 2. API ENDPOINT TESTS (POST /assistant/daily-recommendation)
# ============================================================================

def test_daily_recommendation_endpoint_missing_secret():
    """Verifies 401 when X-Internal-Secret header is omitted."""
    payload = {"student_user_id": 3, "classroom_id": 1}
    response = client.post("/assistant/daily-recommendation", json=payload)
    assert response.status_code == 401
    assert "Missing or invalid X-Internal-Secret" in response.json()["detail"]


def test_daily_recommendation_endpoint_wrong_secret():
    """Verifies 401 when X-Internal-Secret header has wrong value."""
    payload = {"student_user_id": 3, "classroom_id": 1}
    response = client.post(
        "/assistant/daily-recommendation",
        json=payload,
        headers={"X-Internal-Secret": "wrong-secret-key"},
    )
    assert response.status_code == 401


@patch("app.api.assistant.get_daily_recommendation", new_callable=AsyncMock)
def test_daily_recommendation_endpoint_unauthorized_user_returns_403(mock_get_rec):
    """Verifies 403 Forbidden when user is not an active classroom member."""
    mock_get_rec.side_effect = NotAuthorizedError("Access denied or classroom not found")

    payload = {"student_user_id": 99, "classroom_id": 1}
    response = client.post(
        "/assistant/daily-recommendation",
        json=payload,
        headers={"X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied or classroom not found"


@patch("app.api.assistant.get_daily_recommendation", new_callable=AsyncMock)
def test_daily_recommendation_endpoint_success_returns_200(mock_get_rec):
    """Verifies 200 OK when recommendation is successfully synthesized."""
    mock_get_rec.return_value = {
        "recommendation": "Here is your study plan for today...",
        "supporting_data": {
            "progress_summary": {"completion_percentage": 75.0},
            "pending_tasks": {"total_pending": 1, "assignments": [], "quizzes": []},
            "weak_topics": [],
            "recommended_topic": {"title": "Linear Algebra"},
            "recommendation_reason": "Next sequential topic",
        },
    }

    payload = {"student_user_id": 3, "classroom_id": 1}
    response = client.post(
        "/assistant/daily-recommendation",
        json=payload,
        headers={"X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recommendation"] == "Here is your study plan for today..."
    assert data["supporting_data"]["progress_summary"]["completion_percentage"] == 75.0
