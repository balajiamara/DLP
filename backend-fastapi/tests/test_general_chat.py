"""
Unit tests for General Learning Mode Service (app.services.general_chat)
and Mode Isolation Safety Tests against Course Mode (app.services.course_chat).
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.services.general_chat import answer_general_question
from app.services.course_chat import answer_course_question
from app.services.rag_retrieval import NotAuthorizedError


@pytest.mark.asyncio
@patch("app.services.general_chat.is_authorized_for_classroom")
@patch("app.services.general_chat.generate_answer")
async def test_general_chat_success(mock_generate_answer, mock_is_authorized):
    """Confirms General Mode generates ungrounded LLM answer with grounded=False and sources=[]."""
    mock_is_authorized.return_value = True
    mock_generate_answer.return_value = "Calculus is the mathematical study of continuous change."

    result = await answer_general_question(
        user_id=1,
        classroom_id=1,
        query="What is calculus?",
    )

    assert result["answer"] == "Calculus is the mathematical study of continuous change."
    assert result["grounded"] is False
    assert result["sources"] == []

    mock_is_authorized.assert_called_once_with(1, 1)
    mock_generate_answer.assert_called_once()
    system_prompt_arg, query_arg = mock_generate_answer.call_args[0]
    assert "general-purpose learning assistant" in system_prompt_arg
    assert "broad knowledge" in system_prompt_arg
    assert query_arg == "What is calculus?"


@pytest.mark.asyncio
@patch("app.services.general_chat.is_authorized_for_classroom")
@patch("app.services.general_chat.generate_answer")
async def test_general_chat_unauthorized_propagation(mock_generate_answer, mock_is_authorized):
    """Confirms NotAuthorizedError propagates and short-circuits WITHOUT calling LLM API."""
    mock_is_authorized.return_value = False

    with pytest.raises(NotAuthorizedError, match="not an active member"):
        await answer_general_question(
            user_id=99,
            classroom_id=1,
            query="General question?",
        )

    mock_is_authorized.assert_called_once_with(99, 1)
    # CRITICAL: Verify LLM generation is NEVER called when unauthorized!
    mock_generate_answer.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.course_chat.retrieve_relevant_chunks")
@patch("app.services.general_chat.is_authorized_for_classroom")
@patch("app.services.course_chat.generate_answer")
@patch("app.services.general_chat.generate_answer")
async def test_mode_isolation_system_prompts(
    mock_general_llm,
    mock_course_llm,
    mock_general_auth,
    mock_course_retrieve,
):
    """
    SAFETY TEST: Empirically proves that Course Mode and General Mode system prompts
    never cross-contaminate or share grounding instructions.
    """
    same_user_id = 2
    same_classroom_id = 6
    same_query = "Explain the fundamentals of linear algebra."

    # 1. Mock Course Mode retrieval with relevant chunk
    mock_course_retrieve.return_value = [
        {
            "material_id": 8,
            "material_title": "Math Course PDF",
            "chunk_index": 0,
            "chunk_text": "Linear algebra is the branch of mathematics concerning linear equations.",
            "distance": 0.20,
        }
    ]
    mock_course_llm.return_value = "Course grounded answer."

    # 2. Mock General Mode authorization
    mock_general_auth.return_value = True
    mock_general_llm.return_value = "General knowledge answer."

    # Invoke both modes with identical query & parameters
    course_res = await answer_course_question(
        user_id=same_user_id,
        classroom_id=same_classroom_id,
        topic_id=None,
        query=same_query,
    )

    general_res = await answer_general_question(
        user_id=same_user_id,
        classroom_id=same_classroom_id,
        query=same_query,
    )

    # Verify response shapes differ
    assert course_res["grounded"] is True
    assert len(course_res["sources"]) == 1

    assert general_res["grounded"] is False
    assert general_res["sources"] == []

    # Extract actual system prompt arguments passed to generate_answer in each mode
    mock_course_llm.assert_called_once()
    course_system_prompt = mock_course_llm.call_args[0][0]

    mock_general_llm.assert_called_once()
    general_system_prompt = mock_general_llm.call_args[0][0]

    # PROOF 1: System prompts are distinct strings
    assert course_system_prompt != general_system_prompt

    # PROOF 2: General Mode prompt does NOT contain Course Mode grounding restrictions
    assert "EXCLUSIVELY" not in general_system_prompt
    assert "provided classroom context" not in general_system_prompt
    assert "STRICT GROUNDING RULES" not in general_system_prompt

    # PROOF 3: Course Mode prompt does NOT contain General Mode broad-knowledge directives
    assert "broad knowledge" not in course_system_prompt
    assert "general-purpose learning assistant" not in course_system_prompt

    print("\n[PASSED] Mode Isolation Proof: System prompts are strictly separated.")


@pytest.mark.asyncio
@patch("app.services.general_chat.is_authorized_for_classroom")
@patch("app.services.general_chat.generate_answer")
async def test_general_chat_socratic_mode_prompt_variation(mock_generate_answer, mock_is_authorized):
    """Confirms socratic_mode=True in General Mode creates a distinct prompt with coaching instructions."""
    mock_is_authorized.return_value = True
    mock_generate_answer.return_value = "What is the relationship between position and velocity?"

    # 1. Non-socratic call
    await answer_general_question(
        user_id=1,
        classroom_id=1,
        query="Explain derivatives in physics.",
        socratic_mode=False,
    )
    direct_prompt = mock_generate_answer.call_args[0][0]

    mock_generate_answer.reset_mock()

    # 2. Socratic call
    res = await answer_general_question(
        user_id=1,
        classroom_id=1,
        query="Explain derivatives in physics.",
        socratic_mode=True,
    )
    socratic_prompt = mock_generate_answer.call_args[0][0]

    assert res["grounded"] is False
    assert res["sources"] == []

    # Verify prompt variation
    assert direct_prompt != socratic_prompt
    assert "Socratic academic coach" in socratic_prompt
    assert "Do NOT provide the complete solution or full direct answer immediately" in socratic_prompt
    assert "targeted hint, intuitive analogy, or thought-provoking question" in socratic_prompt


@pytest.mark.asyncio
@patch("app.services.general_chat.is_authorized_for_classroom")
@patch("app.services.general_chat.generate_answer")
async def test_general_chat_socratic_mode_isolation(mock_generate_answer, mock_is_authorized):
    """Confirms Socratic General Mode prompt isolates from Course Mode grounding and direct General Mode framing."""
    mock_is_authorized.return_value = True
    mock_generate_answer.return_value = "Hint answer"

    await answer_general_question(
        user_id=1,
        classroom_id=1,
        query="How does gravity work?",
        socratic_mode=True,
    )

    socratic_general_prompt = mock_generate_answer.call_args[0][0]

    # Does NOT contain Course Mode grounding directives
    assert "Classroom Context Materials" not in socratic_general_prompt
    assert "STRICT GROUNDING RULES" not in socratic_general_prompt
    assert "UNGROUNDED_FALLBACK_ANSWER" not in socratic_general_prompt
    assert "provided classroom context" not in socratic_general_prompt

    # Does NOT contain direct General Mode full explanation directives
    assert "explain concepts thoroughly" not in socratic_general_prompt
    assert "answer the user's question clearly, accurately, and conceptually" not in socratic_general_prompt

    # DOES contain Socratic coaching instructions
    assert "Socratic academic coach" in socratic_general_prompt
    assert "Do NOT provide the complete solution" in socratic_general_prompt

