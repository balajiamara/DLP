"""
AI Content Generation Service (Step 40)

Implements AI quiz generation and personalized study-plan generation
under the mandatory review-before-save gate:
1. LLM output is strictly validated against Pydantic schemas before save.
2. Malformed outputs fail cleanly and never write partial drafts.
3. Content is written to Django's GeneratedDraft holding model (never directly to Quiz/Assignment).
4. Quizzes are strictly grounded in uploaded classroom material chunks (via Step 33 retrieve_relevant_chunks).
5. Study plans are grounded in student progress and weak topics.
"""

import logging
import time
import httpx
from typing import Dict, Any, Optional, List
from google import genai
from google.genai import types
from sqlalchemy import text

from app.core.config import settings
from app.db.session import async_session_maker
from app.schemas.content_generation import (
    QuizDraftSchema,
    StudyPlanDraftSchema,
)
from app.services.rag_retrieval import (
    retrieve_relevant_chunks,
    is_authorized_for_classroom,
    NotAuthorizedError,
)
from app.services.mcp_resource_service import is_teacher_for_classroom
from app.services.mcp_tool_service import (
    get_student_progress_data,
    get_weak_topics_data,
)
from app.services.evaluation_logging import log_ai_interaction

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3.6-flash"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0


class ContentGenerationError(Exception):
    """Raised when LLM generation fails or produces malformed output."""
    pass


async def _get_topic_title(topic_id: int) -> str:
    """Fetches topic title for grounding query."""
    async with async_session_maker() as session:
        res = await session.execute(
            text("SELECT title FROM syllabus_topic WHERE id = :tid"),
            {"tid": topic_id}
        )
        row = res.first()
        return row[0] if row else "Course Material"


def _call_gemini_structured(
    system_instruction: str,
    user_prompt: str,
    response_schema: Any,
) -> str:
    """
    Calls Gemini 3.6 Flash using response_mime_type='application/json' and response_schema.
    Includes exponential backoff retry loop for API resilience.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise ContentGenerationError("GEMINI_API_KEY is not configured in settings.")

    client = genai.Client(api_key=api_key)
    delay = INITIAL_RETRY_DELAY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,  # Low temperature for strict factual adherence
                response_mime_type="application/json",
                response_schema=response_schema,
            )
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_prompt,
                config=config,
            )
            if not response.text:
                raise ContentGenerationError("Empty response returned by Gemini.")
            return response.text
        except Exception as exc:
            logger.warning("Gemini generation attempt %d failed: %s", attempt, exc)
            if attempt == MAX_RETRIES:
                raise ContentGenerationError(f"Gemini generation failed after {MAX_RETRIES} attempts: {exc}") from exc
            time.sleep(delay)
            delay *= 2.0


async def _post_draft_to_django(draft_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Posts the validated draft payload to Django's internal holding endpoint.
    Django owns the assessments_generateddraft table and foreign keys.
    """
    django_url = f"{settings.DJANGO_BASE_URL.rstrip('/')}/api/internal/drafts/"
    headers = {
        "X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(django_url, json=draft_payload, headers=headers)
            if resp.status_code != 201:
                logger.error("Django draft creation failed [%d]: %s", resp.status_code, resp.text)
                raise ContentGenerationError(f"Failed to persist draft in Django: {resp.text}")
            return resp.json()
        except httpx.RequestError as exc:
            logger.error("Network error communicating with Django internal draft API: %s", exc)
            raise ContentGenerationError(f"Network error connecting to Django draft holding service: {exc}") from exc


async def generate_quiz_draft(
    classroom_id: int,
    topic_id: int,
    teacher_user_id: int,
    num_questions: int = 5,
) -> Dict[str, Any]:
    """
    Generates a draft quiz strictly grounded in classroom material chunks retrieved from Step 33.
    Only the classroom teacher is authorized to generate quizzes.
    Validates output format against QuizDraftSchema before persisting.
    """
    start_time = time.perf_counter()
    chunks = []
    topic_title = "Unknown"

    try:
        # 1. Authorization: Only the teacher of this classroom can generate quizzes
        is_teacher = await is_teacher_for_classroom(user_id=teacher_user_id, classroom_id=classroom_id)
        if not is_teacher:
            raise NotAuthorizedError("Access denied or classroom not found.")

        # 2. Grounding: Fetch topic title and retrieve relevant course material chunks (Step 33)
        topic_title = await _get_topic_title(topic_id)
        chunks = await retrieve_relevant_chunks(
            user_id=teacher_user_id,
            classroom_id=classroom_id,
            query_text=topic_title,
            topic_id=topic_id,
            top_k=5,
        )

        if not chunks:
            raise ValueError(
                f"Cannot generate quiz: No uploaded course material found or indexed for topic '{topic_title}' in this classroom."
            )

        # 3. Construct prompt with retrieved material context
        context_blocks = []
        for i, chunk in enumerate(chunks, 1):
            context_blocks.append(f"[Excerpt {i}]:\n{chunk.get('chunk_text', '')}")
        retrieved_context = "\n\n".join(context_blocks)

        system_prompt = (
            "You are an expert educational assessment creator. Your task is to generate a high-quality "
            "multiple-choice quiz grounded EXCLUSIVELY in the provided course material excerpts.\n"
            "Rules:\n"
            "1. Every question must be directly answerable from the provided excerpts.\n"
            "2. Do NOT hallucinate or invent facts not present in the excerpts.\n"
            "3. Each question must have 4 distinct options (option_a, option_b, option_c, option_d).\n"
            "4. Exactly one option is correct (correct_option must be 'A', 'B', 'C', or 'D').\n"
            "5. Provide a thorough, pedagogically clear explanation for why the chosen option is correct.\n"
            "6. Output MUST strictly match the requested JSON schema."
        )

        user_prompt = (
            f"Topic: {topic_title}\n"
            f"Desired Question Count: {num_questions}\n\n"
            f"Grounded Excerpts:\n{retrieved_context}\n\n"
            f"Generate a {num_questions}-question quiz strictly adhering to the schema."
        )

        # 4. Invoke LLM with structured output schema
        raw_json = _call_gemini_structured(
            system_instruction=system_prompt,
            user_prompt=user_prompt,
            response_schema=QuizDraftSchema,
        )

        # 5. Strict Schema Validation
        try:
            validated_draft = QuizDraftSchema.model_validate_json(raw_json)
        except Exception as exc:
            logger.error("Generated quiz failed Pydantic schema validation: %s", exc)
            raise ContentGenerationError(f"LLM generated malformed quiz schema: {exc}") from exc

        # 6. Write draft holding record to Django
        draft_payload = {
            "classroom": classroom_id,
            "content_type": "QUIZ",
            "status": "DRAFT",
            "content": validated_draft.model_dump(),
            "topic": topic_id,
            "created_by": teacher_user_id,
            "target_student": None,
            "requires_teacher_fact_check": True,
        }

        result = await _post_draft_to_django(draft_payload)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        chunk_ids = [c.get("id") for c in chunks if c.get("id") is not None]
        try:
            await log_ai_interaction(
                interaction_type="QUIZ_GENERATION",
                user_id=teacher_user_id,
                classroom_id=classroom_id,
                model=GEMINI_MODEL,
                latency_ms=latency_ms,
                grounded=True,
                retrieved_chunk_ids=chunk_ids,
                query_text=f"Quiz Topic: {topic_title} (count={num_questions})",
                answer_text=str(draft_payload["content"])[:500],
                error_occurred=False,
            )
        except Exception as log_exc:
            logger.warning("Failed to log AI quiz interaction telemetry: %s", log_exc)

        return result
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        chunk_ids = [c.get("id") for c in chunks if isinstance(c, dict) and c.get("id") is not None]
        # Only log non-auth errors to AI evaluation log (or all failures during generation)
        if not isinstance(exc, NotAuthorizedError):
            try:
                await log_ai_interaction(
                    interaction_type="QUIZ_GENERATION",
                    user_id=teacher_user_id,
                    classroom_id=classroom_id,
                    model=GEMINI_MODEL,
                    latency_ms=latency_ms,
                    grounded=True if chunk_ids else False,
                    retrieved_chunk_ids=chunk_ids,
                    query_text=f"Quiz Topic: {topic_title} (count={num_questions})",
                    answer_text=None,
                    error_occurred=True,
                    error_message=str(exc)[:500],
                )
            except Exception as log_exc:
                logger.warning("Failed to log AI quiz error telemetry: %s", log_exc)
        raise


async def generate_study_plan_draft(
    classroom_id: int,
    student_user_id: int,
    requesting_user_id: int,
    goal_description: str,
    deadline: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generates an individualized study plan draft grounded in student progress and weak topics.
    Authorized for the student themselves or the classroom teacher.
    Validates output format against StudyPlanDraftSchema before persisting.
    """
    start_time = time.perf_counter()

    try:
        # 1. Authorization: Student must be an active member
        is_student = await is_authorized_for_classroom(user_id=student_user_id, classroom_id=classroom_id)
        if not is_student:
            raise NotAuthorizedError("Access denied or classroom not found.")

        # Requester must be either the student themselves or the classroom teacher
        if requesting_user_id != student_user_id:
            is_teacher = await is_teacher_for_classroom(user_id=requesting_user_id, classroom_id=classroom_id)
            if not is_teacher:
                raise NotAuthorizedError("Access denied or classroom not found.")

        # 2. Grounding: Fetch student progress and weak topics
        progress_data = await get_student_progress_data(
            caller_user_id=requesting_user_id,
            classroom_id=classroom_id,
            target_user_id=student_user_id,
        )
        weak_topics_res = await get_weak_topics_data(
            caller_user_id=requesting_user_id,
            classroom_id=classroom_id,
            target_user_id=student_user_id,
        )
        weak_topics = weak_topics_res.get("weak_topics", []) if isinstance(weak_topics_res, dict) else (weak_topics_res or [])

        # 3. Construct prompt with progress and weak topic grounding
        progress_summary = progress_data.get("progress_summary", {})
        comp_pct = progress_summary.get("completion_percentage", 0.0)
        completed_topics = progress_summary.get("completed_topics", 0)
        total_topics = progress_summary.get("total_topics", 0)

        weak_lines = []
        for wt in weak_topics:
            score_str = f" (Quiz Score: {wt.get('quiz_score')}%)" if wt.get("quiz_score") is not None else ""
            weak_lines.append(f"- '{wt.get('topic_title')}'{score_str} — {wt.get('reason')}")
        weak_text = "\n".join(weak_lines) if weak_lines else "None identified (student is on track)."

        system_prompt = (
            "You are an empathetic, highly structured academic coach. Your task is to design a realistic, "
            "personalized study plan based on a student's current learning progress, identified weak topics, "
            "and stated goal.\n"
            "Rules:\n"
            "1. Prioritize remediation for topics where the student has scored low or needs review.\n"
            "2. Break down study into clear, sequential, achievable tasks with specific pacing.\n"
            "3. Provide realistic pacing suggestions (e.g. 'Day 1-2', '45 minutes', 'Weekend review').\n"
            "4. Output MUST strictly match the requested JSON schema."
        )

        deadline_str = f"Target Deadline: {deadline}\n" if deadline else "Target Deadline: Flexible\n"
        user_prompt = (
            f"Student Goal: {goal_description}\n"
            f"{deadline_str}"
            f"Current Progress: {comp_pct}% complete ({completed_topics} of {total_topics} topics completed)\n\n"
            f"Identified Weak / Lagging Topics:\n{weak_text}\n\n"
            f"Generate a personalized study plan strictly adhering to the schema."
        )

        # 4. Invoke LLM with structured output schema
        raw_json = _call_gemini_structured(
            system_instruction=system_prompt,
            user_prompt=user_prompt,
            response_schema=StudyPlanDraftSchema,
        )

        # 5. Strict Schema Validation
        try:
            validated_draft = StudyPlanDraftSchema.model_validate_json(raw_json)
        except Exception as exc:
            logger.error("Generated study plan failed Pydantic schema validation: %s", exc)
            raise ContentGenerationError(f"LLM generated malformed study plan schema: {exc}") from exc

        # 6. Write draft holding record to Django
        draft_payload = {
            "classroom": classroom_id,
            "content_type": "STUDY_PLAN",
            "status": "DRAFT",
            "content": validated_draft.model_dump(),
            "topic": None,
            "created_by": requesting_user_id,
            "target_student": student_user_id,
            "requires_teacher_fact_check": True,
        }

        result = await _post_draft_to_django(draft_payload)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        try:
            await log_ai_interaction(
                interaction_type="STUDY_PLAN_GENERATION",
                user_id=requesting_user_id,
                classroom_id=classroom_id,
                model=GEMINI_MODEL,
                latency_ms=latency_ms,
                grounded=True,
                retrieved_chunk_ids=[],
                query_text=f"Goal: {goal_description}"[:500],
                answer_text=str(draft_payload["content"])[:500],
                error_occurred=False,
            )
        except Exception as log_exc:
            logger.warning("Failed to log AI study plan interaction telemetry: %s", log_exc)

        return result
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        if not isinstance(exc, NotAuthorizedError):
            try:
                await log_ai_interaction(
                    interaction_type="STUDY_PLAN_GENERATION",
                    user_id=requesting_user_id,
                    classroom_id=classroom_id,
                    model=GEMINI_MODEL,
                    latency_ms=latency_ms,
                    grounded=True,
                    retrieved_chunk_ids=[],
                    query_text=f"Goal: {goal_description}"[:500],
                    answer_text=None,
                    error_occurred=True,
                    error_message=str(exc)[:500],
                )
            except Exception as log_exc:
                logger.warning("Failed to log AI study plan error telemetry: %s", log_exc)
        raise
