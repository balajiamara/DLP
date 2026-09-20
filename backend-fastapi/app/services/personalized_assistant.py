"""
Personalized Learning Assistant Service ("What Should I Study Today")

Orchestrates student progress, pending tasks, weak topics, and sequential syllabus
recommendations into a single, grounded context payload and synthesizes an actionable,
encouraging daily study recommendation using Gemini 3.6 Flash.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional

from app.services.rag_retrieval import is_authorized_for_classroom, NotAuthorizedError
from app.services.mcp_tool_service import (
    get_pending_tasks_data,
    get_weak_topics_data,
    recommend_next_topic_data,
    get_student_progress_data,
)
from app.services.chat_client import generate_answer, GeminiChatError
from app.services.evaluation_logging import log_ai_interaction

logger = logging.getLogger(__name__)


def build_assistant_system_prompt(
    progress_summary: Dict[str, Any],
    pending_tasks: Dict[str, Any],
    weak_topics: list,
    recommendation_data: Dict[str, Any],
) -> str:
    """
    Constructs the grounded system prompt for the Gemini LLM synthesis.
    Instructs the model to be warm, concise, and strictly faithful to provided facts.
    """
    # 1. Format Progress
    total_topics = progress_summary.get("total_topics", 0)
    completed_topics = progress_summary.get("completed_topics", 0)
    completion_pct = progress_summary.get("completion_percentage", 0.0)
    progress_text = (
        f"- Course Completion: {completion_pct}% ({completed_topics} of {total_topics} topics completed)"
    )

    # 2. Format Recommended Topic
    rec_topic = recommendation_data.get("recommended_topic")
    rec_reason = recommendation_data.get("reason", "Continue following your study plan.")
    if rec_topic:
        rec_text = (
            f"- Recommended Topic: '{rec_topic.get('title')}' "
            f"(Course: {rec_topic.get('course_title')}, Module: {rec_topic.get('module_title')})\n"
            f"- Recommendation Rationale: {rec_reason}"
        )
    else:
        rec_text = f"- Recommended Topic: None (Status: {rec_reason})"

    # 3. Format Weak Topics
    if weak_topics:
        weak_lines = []
        for wt in weak_topics:
            score_str = f" (Score: {wt.get('quiz_score')}%)" if wt.get("quiz_score") is not None else ""
            weak_lines.append(f"  * '{wt.get('topic_title')}'{score_str} — {wt.get('reason')}")
        weak_text = "\n".join(weak_lines)
    else:
        weak_text = "  * None! All attempted topics meet the mastery threshold."

    # 4. Format Pending Tasks
    assignments = pending_tasks.get("pending_assignments", [])
    quizzes = pending_tasks.get("pending_quizzes", [])
    task_lines = []

    if assignments:
        task_lines.append("  Assignments:")
        for a in assignments:
            overdue_tag = " [OVERDUE]" if a.get("is_overdue") else ""
            due_str = f" (Due: {a.get('due_date')})" if a.get("due_date") else " (No due date)"
            task_lines.append(f"    * Assignment: '{a.get('title')}'{due_str}{overdue_tag}")

    if quizzes:
        task_lines.append("  Quizzes:")
        for q in quizzes:
            task_lines.append(f"    * Quiz: '{q.get('title')}' (Topic: {q.get('topic_title')})")

    if not task_lines:
        pending_text = "  * No pending assignments or quizzes. You are completely caught up!"
    else:
        pending_text = "\n".join(task_lines)

    # 5. Assemble Grounded System Instruction
    is_caught_up = (
        not weak_topics
        and not assignments
        and not quizzes
        and (rec_topic is None or completion_pct >= 100.0)
    )

    guidance_section = (
        "SPECIAL GUIDANCE FOR ALL-CAUGHT-UP STUDENTS:\n"
        "- The student has completed all current material, has no weak topics, and has no pending tasks.\n"
        "- Give a warm, celebratory, and genuinely positive message congratulating them on their mastery.\n"
        "- Suggest reviewing past favorite concepts or taking a well-deserved break.\n"
        if is_caught_up
        else "STUDY PLAN PRIORITIZATION GUIDANCE:\n"
        "1. If there are overdue assignments, prioritize them first with a supportive tone.\n"
        "2. If there are weak topics needing review, highlight them and explain why reviewing will strengthen their foundation.\n"
        "3. Emphasize the recommended next topic as their primary learning focus for today.\n"
        "4. Mention upcoming unattempted quizzes or pending assignments.\n"
    )

    prompt = (
        "You are the Daily Learning Planner's intelligent, supportive Personal Learning Assistant.\n"
        "Your goal is to answer the student's question: 'What should I study today?' with a warm, encouraging, "
        "and clear daily recommendation.\n\n"
        "STRICT GROUNDING & ACCURACY RULES:\n"
        "1. Rely EXCLUSIVELY on the student's real data provided below.\n"
        "2. Do NOT invent or hallucinate topics, due dates, scores, or assignments not listed in the context.\n"
        "3. Reference actual topic names, assignment titles, or quiz scores directly from the data.\n"
        "4. Keep your recommendation concise (2 to 3 short paragraphs max).\n\n"
        f"{guidance_section}\n"
        "STUDENT'S REAL-TIME LEARNING STATUS:\n"
        f"{progress_text}\n\n"
        f"RECOMMENDED FOCUS:\n{rec_text}\n\n"
        f"AREAS NEEDING REVIEW (WEAK TOPICS):\n{weak_text}\n\n"
        f"PENDING TASKS:\n{pending_text}\n"
    )
    return prompt


async def get_daily_recommendation(user_id: int, classroom_id: int) -> Dict[str, Any]:
    """
    Directly orchestrates the student's learning state and produces a personalized
    daily study recommendation using Gemini 3.6 Flash.

    Args:
        user_id: Authenticated student ID.
        classroom_id: Target classroom ID.

    Returns:
        dict: {
            "recommendation": <LLM synthesized text>,
            "supporting_data": {
                "progress_summary": ...,
                "pending_tasks": ...,
                "weak_topics": ...,
                "recommended_topic": ...,
                "recommendation_reason": ...
            }
        }

    Raises:
        NotAuthorizedError: If user is not an active member of the classroom.
        GeminiChatError: If LLM generation fails.
    """
    user_id = int(user_id)
    classroom_id = int(classroom_id)
    start_time = time.perf_counter()

    # 1. Authorization check FIRST - short circuits before any service or LLM calls
    if not await is_authorized_for_classroom(user_id=user_id, classroom_id=classroom_id):
        logger.warning(
            f"Unauthorized daily recommendation attempt: user {user_id} requested classroom {classroom_id}."
        )
        raise NotAuthorizedError("Access denied or classroom not found")

    try:
        # 2. Direct in-process orchestration of underlying services (no live MCP protocol round trip)
        # Run data gathering concurrently for minimum latency
        pending_tasks_coro = get_pending_tasks_data(caller_user_id=user_id, classroom_id=classroom_id)
        weak_topics_coro = get_weak_topics_data(caller_user_id=user_id, classroom_id=classroom_id)
        recommendation_coro = recommend_next_topic_data(caller_user_id=user_id, classroom_id=classroom_id)
        progress_coro = get_student_progress_data(caller_user_id=user_id, classroom_id=classroom_id)

        pending_data, weak_data, rec_data, prog_data = await asyncio.gather(
            pending_tasks_coro,
            weak_topics_coro,
            recommendation_coro,
            progress_coro,
        )

        progress_summary = prog_data.get("summary_stats", {})
        weak_topics = weak_data.get("weak_topics", [])
        rec_topic = rec_data.get("recommended_topic")
        rec_reason = rec_data.get("reason", "")

        # 3. Assemble raw supporting data payload for auditing and UI facts display
        supporting_data = {
            "progress_summary": progress_summary,
            "pending_tasks": {
                "total_pending": pending_data.get("total_pending_tasks", 0),
                "assignments": pending_data.get("pending_assignments", []),
                "quizzes": pending_data.get("pending_quizzes", []),
            },
            "weak_topics": weak_topics,
            "recommended_topic": rec_topic,
            "recommendation_reason": rec_reason,
        }

        # 4. Construct grounded system prompt
        system_prompt = build_assistant_system_prompt(
            progress_summary=progress_summary,
            pending_tasks=pending_data,
            weak_topics=weak_topics,
            recommendation_data=rec_data,
        )

        # 5. Call LLM (single call using gemini-3.6-flash via non-blocking thread offload)
        user_query = "What should I study today?"
        synthesized_recommendation = await asyncio.to_thread(
            generate_answer, system_prompt, user_query
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        try:
            await log_ai_interaction(
                interaction_type="PERSONALIZED_ASSISTANT",
                user_id=user_id,
                classroom_id=classroom_id,
                model="gemini-3.6-flash",
                latency_ms=latency_ms,
                grounded=True,
                retrieved_chunk_ids=[],
                query_text=user_query,
                answer_text=synthesized_recommendation[:500] if synthesized_recommendation else None,
                error_occurred=False,
            )
        except Exception as log_exc:
            logger.warning("Failed to log personalized assistant interaction telemetry: %s", log_exc)

        return {
            "recommendation": synthesized_recommendation,
            "supporting_data": supporting_data,
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        try:
            await log_ai_interaction(
                interaction_type="PERSONALIZED_ASSISTANT",
                user_id=user_id,
                classroom_id=classroom_id,
                model="gemini-3.6-flash",
                latency_ms=latency_ms,
                grounded=True,
                retrieved_chunk_ids=[],
                query_text="What should I study today?",
                answer_text=None,
                error_occurred=True,
                error_message=str(exc)[:500],
            )
        except Exception as log_exc:
            logger.warning("Failed to log personalized assistant error telemetry: %s", log_exc)
        raise
