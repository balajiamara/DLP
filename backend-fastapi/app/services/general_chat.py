"""
General Chat Service (General Learning Mode)

Provides ungrounded AI chat capabilities using Gemini 3.6 Flash's broad knowledge
for questions outside classroom material, while remaining gated by classroom authorization.
"""

import asyncio
import time
import json
import logging
from typing import AsyncGenerator
from app.services.rag_retrieval import is_authorized_for_classroom, NotAuthorizedError
from app.services.chat_client import generate_answer, generate_answer_stream, GeminiChatError
from app.services.evaluation_logging import log_ai_interaction

logger = logging.getLogger(__name__)


async def answer_general_question(
    user_id: int,
    classroom_id: int,
    query: str,
    socratic_mode: bool = False,
) -> dict:
    start_time = time.time()

    """
    Answers a general-knowledge learning question using Gemini 3.6 Flash.

    Security & Scope:
    - Verifies user is an active member of classroom_id before making any LLM calls.
    - Does NOT perform vector retrieval or classroom grounding.
    - Always returns grounded=False and sources=[].

    Args:
        user_id: ID of the user asking the question.
        classroom_id: ID of the classroom scope for authorization.
        query: Question string.
        socratic_mode: If True, guides the student with questions/hints rather than direct answers.

    Returns:
        Dict with keys:
            - answer (str): LLM generated answer string.
            - grounded (bool): Always False for General Learning Mode.
            - sources (list): Always [] for General Learning Mode.

    Raises:
        NotAuthorizedError: If user is not an active member of the classroom.
    """
    # Step 1: Pre-search classroom authorization check
    authorized = await is_authorized_for_classroom(user_id, classroom_id)
    if not authorized:
        logger.warning(
            f"Unauthorized General Mode attempt: user {user_id} requested classroom {classroom_id}."
        )
        raise NotAuthorizedError(f"User {user_id} is not an active member of classroom {classroom_id}.")

    if not query or not query.strip():
        return {
            "answer": "Please provide a valid question.",
            "grounded": False,
            "sources": [],
        }

    # Step 2: Construct General Mode system prompt (Direct vs Socratic variant)
    # Note: Keeping General Mode's system prompt textually separate from Course Mode
    # ensures that Course Mode's grounding constraints ("answer ONLY from provided context")
    # can never accidentally leak into General Mode's prompt or vice-versa.
    if socratic_mode:
        system_prompt = (
            "You are an expert, Socratic academic coach for the Daily Learning Planner.\n"
            "Your goal is to help the user discover the answer for themselves using your broad general knowledge across educational topics.\n\n"
            "SOCRATIC GUIDELINES:\n"
            "1. Do NOT provide the complete solution or full direct answer immediately.\n"
            "2. Offer a targeted hint, intuitive analogy, or thought-provoking question that prompts the student to take the next logical step.\n"
            "3. Maintain an encouraging, interactive, and pedagogically sound tone.\n"
            "4. Keep your guiding hint concise so the student has space to reflect and respond."
        )
    else:
        system_prompt = (
            "You are an expert, supportive general-purpose learning assistant for the Daily Learning Planner.\n"
            "Your goal is to answer the user's question clearly, accurately, and conceptually using your broad knowledge "
            "across science, mathematics, literature, history, and general educational topics.\n\n"
            "GUIDELINES:\n"
            "1. Provide a helpful, well-structured, and encouraging explanation.\n"
            "2. Feel free to use your full general knowledge base to explain concepts thoroughly.\n"
            "3. Maintain a tone suitable for students and teachers seeking clarity."
        )

    # Step 3: Generate answer via non-blocking offload to Gemini Chat API
    answer_text = await asyncio.to_thread(generate_answer, system_prompt, query)

    # Step 4: Log AI Interaction telemetry (non-blocking)
    latency_ms = int((time.time() - start_time) * 1000)
    try:
        await log_ai_interaction(
            interaction_type="GENERAL_CHAT",
            user_id=user_id,
            classroom_id=classroom_id,
            model="gemini-3.6-flash",
            latency_ms=latency_ms,
            grounded=False,
            retrieved_chunk_ids=[],
            socratic_mode=socratic_mode,
            query_text=query,
            answer_text=answer_text,
        )
    except Exception as log_exc:
        logger.warning("Failed to log AI interaction telemetry: %s", log_exc)

    # Step 5: Return response structure with grounded=False and sources=[]
    return {
        "answer": answer_text,
        "grounded": False,
        "sources": [],
    }


async def stream_general_question(
    user_id: int,
    classroom_id: int,
    query: str,
    socratic_mode: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Streams a general-knowledge learning response using Gemini 3.6 Flash via Server-Sent Events (SSE).

    Yields SSE events formatted as:
        data: {"type": "chunk", "delta": "..."}\n\n
        data: {"type": "done", "grounded": false, "sources": [], "interaction_id": "..."}\n\n
        data: {"type": "error", "detail": "..."}\n\n
    """
    start_time = time.perf_counter()

    # Step 1: Pre-search classroom authorization check
    authorized = await is_authorized_for_classroom(user_id, classroom_id)
    if not authorized:
        logger.warning(
            f"Unauthorized General Mode attempt: user {user_id} requested classroom {classroom_id}."
        )
        raise NotAuthorizedError(f"User {user_id} is not an active member of classroom {classroom_id}.")

    if not query or not query.strip():
        chunk_event = {"type": "chunk", "delta": "Please provide a valid question."}
        yield f"data: {json.dumps(chunk_event)}\n\n"
        done_event = {"type": "done", "grounded": False, "sources": [], "interaction_id": None}
        yield f"data: {json.dumps(done_event)}\n\n"
        return

    # Step 2: Construct General Mode system prompt (Direct vs Socratic variant)
    if socratic_mode:
        system_prompt = (
            "You are an expert, Socratic academic coach for the Daily Learning Planner.\n"
            "Your goal is to help the user discover the answer for themselves using your broad general knowledge across educational topics.\n\n"
            "SOCRATIC GUIDELINES:\n"
            "1. Do NOT provide the complete solution or full direct answer immediately.\n"
            "2. Offer a targeted hint, intuitive analogy, or thought-provoking question that prompts the student to take the next logical step.\n"
            "3. Maintain an encouraging, interactive, and pedagogically sound tone.\n"
            "4. Keep your guiding hint concise so the student has space to reflect and respond."
        )
    else:
        system_prompt = (
            "You are an expert, supportive general-purpose learning assistant for the Daily Learning Planner.\n"
            "Your goal is to answer the user's question clearly, accurately, and conceptually using your broad knowledge "
            "across science, mathematics, literature, history, and general educational topics.\n\n"
            "GUIDELINES:\n"
            "1. Provide a helpful, well-structured, and encouraging explanation.\n"
            "2. Feel free to use your full general knowledge base to explain concepts thoroughly.\n"
            "3. Maintain a tone suitable for students and teachers seeking clarity."
        )

    accumulated_chunks = []
    stream_failed = False
    error_msg = None

    try:
        async for delta in generate_answer_stream(system_prompt, query):
            accumulated_chunks.append(delta)
            chunk_event = {"type": "chunk", "delta": delta}
            yield f"data: {json.dumps(chunk_event)}\n\n"
    except Exception as e:
        stream_failed = True
        error_msg = str(e)
        logger.error(f"Error during general chat stream for user {user_id}: {e}")
        error_event = {"type": "error", "detail": f"Stream error: {e}"}
        yield f"data: {json.dumps(error_event)}\n\n"
    finally:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        full_answer = "".join(accumulated_chunks)
        interaction_id = None
        try:
            interaction_id = await log_ai_interaction(
                interaction_type="GENERAL_CHAT",
                user_id=user_id,
                classroom_id=classroom_id,
                model="gemini-3.6-flash",
                latency_ms=latency_ms,
                grounded=False,
                retrieved_chunk_ids=[],
                socratic_mode=socratic_mode,
                query_text=query,
                answer_text=full_answer,
                error_occurred=stream_failed,
                error_message=error_msg,
            )
        except Exception as log_exc:
            logger.warning("Failed to log AI interaction telemetry: %s", log_exc)

        if not stream_failed:
            done_event = {
                "type": "done",
                "grounded": False,
                "sources": [],
                "interaction_id": str(interaction_id) if interaction_id else None,
            }
            yield f"data: {json.dumps(done_event)}\n\n"



