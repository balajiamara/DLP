"""
Automated Unit Tests for Step 38: MCP Server — Tools

Validates:
1. Tool discovery and schema generation for all 5 MCP tools:
   - get_student_progress
   - get_pending_tasks
   - search_course_material
   - get_weak_topics
   - recommend_next_topic
2. Strict authorization & generic non-leaking error messages ("Access denied or classroom not found").
3. Spy-based short-circuit tests proving unauthorized calls never reach the database or vector retrieval.
4. Cross-student privacy enforcement (self-or-teacher only).
5. Delegation of search_course_material to Step 33's retrieve_relevant_chunks.
6. Mastery threshold (WEAK_TOPIC_QUIZ_THRESHOLD = 70) and explainable recommendation reasoning.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from app.mcp.server import mcp_server
from app.services.mcp_tool_service import (
    WEAK_TOPIC_QUIZ_THRESHOLD,
    ERR_ACCESS_DENIED_CLASSROOM,
    ERR_ACCESS_DENIED_STUDENT,
    get_student_progress_data,
    get_pending_tasks_data,
    search_course_material_data,
    get_weak_topics_data,
    recommend_next_topic_data,
)
from app.services.mcp_resource_service import MCPAuthorizationError


# ============================================================================
# 1. TOOL DISCOVERY & SCHEMA TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_mcp_tools_registered():
    """Confirms all 5 MCP tools are registered and public schemas exclude Context."""
    tools = await mcp_server.list_tools()
    tool_map = {t.name: t for t in tools}

    expected_tools = [
        "get_student_progress",
        "get_pending_tasks",
        "search_course_material",
        "get_weak_topics",
        "recommend_next_topic",
    ]
    for expected in expected_tools:
        assert expected in tool_map, f"Expected tool '{expected}' not found in registered tools"
        props = tool_map[expected].input_schema.get("properties", {})
        # Context must never be exposed as an input parameter in the schema
        assert "ctx" not in props, f"ctx parameter leaked in input schema for tool '{expected}'"


# ============================================================================
# 2. GET_STUDENT_PROGRESS TESTS
# ============================================================================

@pytest.mark.asyncio
@patch("app.services.mcp_tool_service.is_authorized_for_classroom", new_callable=AsyncMock)
async def test_get_student_progress_unauthorized_short_circuit(mock_is_auth):
    """Verifies unauthorized student short-circuits with generic non-leaking error."""
    mock_is_auth.return_value = False

    with pytest.raises(MCPAuthorizationError, match=ERR_ACCESS_DENIED_CLASSROOM):
        await get_student_progress_data(caller_user_id=99, classroom_id=1)

    mock_is_auth.assert_awaited_once_with(user_id=99, classroom_id=1)


@pytest.mark.asyncio
@patch("app.services.mcp_tool_service.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.services.mcp_tool_service.is_teacher_for_classroom", new_callable=AsyncMock)
async def test_get_student_progress_cross_student_forbidden(mock_is_teacher, mock_is_auth):
    """Verifies student querying peer progress is rejected with generic error."""
    mock_is_auth.return_value = True
    mock_is_teacher.return_value = False

    with pytest.raises(MCPAuthorizationError, match=ERR_ACCESS_DENIED_STUDENT):
        await get_student_progress_data(caller_user_id=3, classroom_id=1, target_user_id=4)

    mock_is_auth.assert_awaited_once_with(user_id=3, classroom_id=1)
    mock_is_teacher.assert_awaited_once_with(user_id=3, classroom_id=1)


@pytest.mark.asyncio
@patch("app.services.mcp_tool_service.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.services.mcp_tool_service.is_teacher_for_classroom", new_callable=AsyncMock)
@patch("app.services.mcp_tool_service.get_student_progress_resource", new_callable=AsyncMock)
async def test_get_student_progress_teacher_allowed(mock_get_prog, mock_is_teacher, mock_is_auth):
    """Verifies teacher querying student progress succeeds by delegating to resource service."""
    mock_is_auth.return_value = True
    mock_is_teacher.return_value = True
    mock_get_prog.return_value = {
        "classroom_id": 1,
        "student_id": 3,
        "summary_stats": {"completion_percentage": 50.0},
    }

    res = await get_student_progress_data(caller_user_id=2, classroom_id=1, target_user_id=3)
    assert res["student_id"] == 3
    assert res["summary_stats"]["completion_percentage"] == 50.0
    mock_get_prog.assert_awaited_once_with(
        requesting_user_id=2,
        classroom_id=1,
        target_user_id=3,
    )


# ============================================================================
# 3. GET_PENDING_TASKS TESTS
# ============================================================================

@pytest.mark.asyncio
@patch("app.services.mcp_tool_service.is_authorized_for_classroom", new_callable=AsyncMock)
async def test_get_pending_tasks_unauthorized_short_circuits(mock_is_auth):
    """Verifies unauthorized user never hits database when calling get_pending_tasks."""
    mock_is_auth.return_value = False

    with patch("app.services.mcp_tool_service.async_session_maker") as mock_session_maker:
        with pytest.raises(MCPAuthorizationError, match=ERR_ACCESS_DENIED_CLASSROOM):
            await get_pending_tasks_data(caller_user_id=10, classroom_id=1)
        mock_session_maker.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.mcp_tool_service.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.services.mcp_tool_service.async_session_maker")
async def test_get_pending_tasks_success(mock_session_maker, mock_is_auth):
    """Verifies querying pending unsubmitted assignments and unattempted quizzes."""
    mock_is_auth.return_value = True

    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session

    now = datetime.now(timezone.utc)
    overdue_date = now - timedelta(days=2)
    future_date = now + timedelta(days=5)

    mock_assignments = [
        {
            "id": 10,
            "title": "Overdue Homework",
            "description": "Solve problem set",
            "topic_id": 1,
            "topic_title": "Limits",
            "due_date": overdue_date,
            "created_at": now - timedelta(days=7),
        },
        {
            "id": 11,
            "title": "Upcoming Project",
            "description": "Build graph",
            "topic_id": 2,
            "topic_title": "Derivatives",
            "due_date": future_date,
            "created_at": now - timedelta(days=1),
        },
    ]

    mock_quizzes = [
        {
            "id": 20,
            "title": "Calculus Quiz 1",
            "topic_id": 1,
            "topic_title": "Limits",
            "created_at": now - timedelta(days=3),
        }
    ]

    mock_assign_res = MagicMock()
    mock_assign_res.mappings.return_value = mock_assignments
    mock_quiz_res = MagicMock()
    mock_quiz_res.mappings.return_value = mock_quizzes

    mock_session.execute.side_effect = [mock_assign_res, mock_quiz_res]

    res = await get_pending_tasks_data(caller_user_id=3, classroom_id=1)
    assert res["classroom_id"] == 1
    assert res["student_id"] == 3
    assert res["total_pending_tasks"] == 3
    assert len(res["pending_assignments"]) == 2
    assert len(res["pending_quizzes"]) == 1

    # Overdue check
    assert res["pending_assignments"][0]["is_overdue"] is True
    assert res["pending_assignments"][1]["is_overdue"] is False


# ============================================================================
# 4. SEARCH_COURSE_MATERIAL TESTS
# ============================================================================

@pytest.mark.asyncio
@patch("app.services.mcp_tool_service.is_authorized_for_classroom", new_callable=AsyncMock)
async def test_search_course_material_unauthorized_short_circuit(mock_is_auth):
    """Verifies unauthorized user short-circuits and never delegates to vector search."""
    mock_is_auth.return_value = False

    with patch("app.services.mcp_tool_service.retrieve_relevant_chunks", new_callable=AsyncMock) as mock_retrieve:
        with pytest.raises(MCPAuthorizationError, match=ERR_ACCESS_DENIED_CLASSROOM):
            await search_course_material_data(caller_user_id=99, classroom_id=1, query="calculus")
        mock_retrieve.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.mcp_tool_service.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.services.mcp_tool_service.async_session_maker")
@patch("app.services.mcp_tool_service.retrieve_relevant_chunks", new_callable=AsyncMock)
async def test_search_course_material_delegation(mock_retrieve, mock_session_maker, mock_is_auth):
    """Verifies search_course_material delegates directly to Step 33's retrieve_relevant_chunks."""
    mock_is_auth.return_value = True

    mock_chunk = {
        "id": "101",
        "material_id": 5,
        "material_title": "Calculus Textbook",
        "chunk_text": "Limit definition of derivative.",
        "score": 0.8842,
        "distance": 0.1158,
    }
    mock_retrieve.return_value = [mock_chunk]

    res = await search_course_material_data(caller_user_id=3, classroom_id=1, query="derivative")

    assert res["classroom_id"] == 1
    assert res["query"] == "derivative"
    assert res["total_results"] == 1
    assert res["chunks"][0]["material_title"] == "Calculus Textbook"
    assert res["chunks"][0]["similarity_score"] == 0.8842

    # Verify delegation call
    mock_retrieve.assert_awaited_once()


# ============================================================================
# 5. GET_WEAK_TOPICS TESTS
# ============================================================================

@pytest.mark.asyncio
@patch("app.services.mcp_tool_service.is_authorized_for_classroom", new_callable=AsyncMock)
async def test_get_weak_topics_unauthorized_short_circuits(mock_is_auth):
    """Verifies unauthorized user short-circuits for weak topics."""
    mock_is_auth.return_value = False

    with patch("app.services.mcp_tool_service.async_session_maker") as mock_session_maker:
        with pytest.raises(MCPAuthorizationError, match=ERR_ACCESS_DENIED_CLASSROOM):
            await get_weak_topics_data(caller_user_id=99, classroom_id=1)
        mock_session_maker.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.mcp_tool_service.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.services.mcp_tool_service.async_session_maker")
async def test_get_weak_topics_detection(mock_session_maker, mock_is_auth):
    """Verifies detection of REVIEW_REQUIRED state and quiz score < 70% threshold."""
    mock_is_auth.return_value = True

    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session

    mock_rows = [
        # Topic 1: REVIEW_REQUIRED with no quiz score -> WEAK
        {
            "topic_id": 1,
            "topic_title": "Arithmetic Progressions",
            "topic_order": 1,
            "module_id": 10,
            "module_title": "Sequences",
            "module_order": 1,
            "course_id": 100,
            "course_title": "Algebra",
            "course_order": 1,
            "learning_state": "REVIEW_REQUIRED",
            "latest_quiz_score": None,
        },
        # Topic 2: LEARNING with low score 65 (< 70) -> WEAK
        {
            "topic_id": 2,
            "topic_title": "Geometric Progressions",
            "topic_order": 2,
            "module_id": 10,
            "module_title": "Sequences",
            "module_order": 1,
            "course_id": 100,
            "course_title": "Algebra",
            "course_order": 1,
            "learning_state": "LEARNING",
            "latest_quiz_score": 65,
        },
        # Topic 3: COMPLETED with passing score 85 (>= 70) -> NOT WEAK
        {
            "topic_id": 3,
            "topic_title": "Harmonic Progressions",
            "topic_order": 3,
            "module_id": 10,
            "module_title": "Sequences",
            "module_order": 1,
            "course_id": 100,
            "course_title": "Algebra",
            "course_order": 1,
            "learning_state": "COMPLETED",
            "latest_quiz_score": 85,
        },
    ]

    mock_res = MagicMock()
    mock_res.mappings.return_value = mock_rows
    mock_session.execute.return_value = mock_res

    res = await get_weak_topics_data(caller_user_id=3, classroom_id=1)
    assert res["classroom_id"] == 1
    assert res["threshold"] == WEAK_TOPIC_QUIZ_THRESHOLD
    assert res["total_weak_topics"] == 2

    weak_topic_ids = [t["topic_id"] for t in res["weak_topics"]]
    assert weak_topic_ids == [1, 2]
    assert "REVIEW_REQUIRED" in res["weak_topics"][0]["reason"]
    assert "below mastery threshold of 70%" in res["weak_topics"][1]["reason"]


# ============================================================================
# 6. RECOMMEND_NEXT_TOPIC TESTS
# ============================================================================

@pytest.mark.asyncio
@patch("app.services.mcp_tool_service.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.services.mcp_tool_service.async_session_maker")
async def test_recommend_next_topic_prioritizes_weak_topic(mock_session_maker, mock_is_auth):
    """Verifies weak topics take priority over sequential unstarted topics."""
    mock_is_auth.return_value = True

    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session

    mock_rows = [
        # Topic 1: Completed passing
        {
            "topic_id": 1,
            "topic_title": "Topic 1",
            "topic_order": 1,
            "module_id": 1,
            "module_title": "Module A",
            "module_order": 1,
            "course_id": 1,
            "course_title": "Course 1",
            "course_order": 1,
            "learning_state": "COMPLETED",
            "latest_quiz_score": 90,
        },
        # Topic 2: Weak (score 55 < 70)
        {
            "topic_id": 2,
            "topic_title": "Topic 2",
            "topic_order": 2,
            "module_id": 1,
            "module_title": "Module A",
            "module_order": 1,
            "course_id": 1,
            "course_title": "Course 1",
            "course_order": 1,
            "learning_state": "LEARNING",
            "latest_quiz_score": 55,
        },
        # Topic 3: Unstarted
        {
            "topic_id": 3,
            "topic_title": "Topic 3",
            "topic_order": 3,
            "module_id": 1,
            "module_title": "Module A",
            "module_order": 1,
            "course_id": 1,
            "course_title": "Course 1",
            "course_order": 1,
            "learning_state": "NOT_STARTED",
            "latest_quiz_score": None,
        },
    ]
    mock_res = MagicMock()
    mock_res.mappings.return_value = mock_rows
    mock_session.execute.return_value = mock_res

    res = await recommend_next_topic_data(caller_user_id=3, classroom_id=1)
    assert res["recommended_topic"]["topic_id"] == 2
    assert "requires review due to low quiz score (55% < 70%)" in res["reason"]


@pytest.mark.asyncio
@patch("app.services.mcp_tool_service.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.services.mcp_tool_service.async_session_maker")
async def test_recommend_next_topic_sequential_when_no_weak_topics(mock_session_maker, mock_is_auth):
    """Verifies next sequential uncompleted topic is recommended when no weak topics exist."""
    mock_is_auth.return_value = True

    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session

    mock_rows = [
        # Topic 1: Completed passing
        {
            "topic_id": 1,
            "topic_title": "Topic 1",
            "topic_order": 1,
            "module_id": 1,
            "module_title": "Module A",
            "module_order": 1,
            "course_id": 1,
            "course_title": "Course 1",
            "course_order": 1,
            "learning_state": "COMPLETED",
            "latest_quiz_score": 90,
        },
        # Topic 2: In-progress
        {
            "topic_id": 2,
            "topic_title": "Topic 2",
            "topic_order": 2,
            "module_id": 1,
            "module_title": "Module A",
            "module_order": 1,
            "course_id": 1,
            "course_title": "Course 1",
            "course_order": 1,
            "learning_state": "LEARNING",
            "latest_quiz_score": None,
        },
    ]
    mock_res = MagicMock()
    mock_res.mappings.return_value = mock_rows
    mock_session.execute.return_value = mock_res

    res = await recommend_next_topic_data(caller_user_id=3, classroom_id=1)
    assert res["recommended_topic"]["topic_id"] == 2
    assert "Continue in-progress topic: Topic 2" in res["reason"]


@pytest.mark.asyncio
@patch("app.services.mcp_tool_service.is_authorized_for_classroom", new_callable=AsyncMock)
@patch("app.services.mcp_tool_service.async_session_maker")
async def test_recommend_next_topic_all_completed(mock_session_maker, mock_is_auth):
    """Verifies congratulatory / review advice when all syllabus topics are completed."""
    mock_is_auth.return_value = True

    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session

    mock_rows = [
        {
            "topic_id": 1,
            "topic_title": "Topic 1",
            "topic_order": 1,
            "module_id": 1,
            "module_title": "Module A",
            "module_order": 1,
            "course_id": 1,
            "course_title": "Course 1",
            "course_order": 1,
            "learning_state": "COMPLETED",
            "latest_quiz_score": 95,
        }
    ]
    mock_res = MagicMock()
    mock_res.mappings.return_value = mock_rows
    mock_session.execute.return_value = mock_res

    res = await recommend_next_topic_data(caller_user_id=3, classroom_id=1)
    assert res["recommended_topic"] is None
    assert "All syllabus topics completed" in res["reason"]


# ============================================================================
# 7. TOOL ERROR PROPAGATION (SERVER LEVEL)
# ============================================================================

@pytest.mark.asyncio
@patch("app.mcp.server.extract_user_id_from_context")
@patch("app.mcp.server.get_pending_tasks_data", new_callable=AsyncMock)
async def test_tool_error_raised_on_authorization_failure(mock_get_pending, mock_extract_uid):
    """Verifies that an MCPAuthorizationError in a tool function raises ToolError."""
    from app.mcp.server import get_pending_tasks
    mock_extract_uid.return_value = 10
    mock_get_pending.side_effect = MCPAuthorizationError(ERR_ACCESS_DENIED_CLASSROOM)

    mock_ctx = MagicMock(spec=Context)
    with pytest.raises(ToolError, match=ERR_ACCESS_DENIED_CLASSROOM):
        await get_pending_tasks(classroom_id=1, ctx=mock_ctx)
