"""
Course Chat Service (Course-Grounded Retrieval-Augmented Generation)

Orchestrates classroom-gated vector retrieval, empirical cosine distance thresholding,
grounded system prompt construction, and Gemini 3.6 Flash LLM answer generation.
"""

import asyncio
import time
import json
import logging
from typing import AsyncGenerator
from app.services.rag_retrieval import retrieve_relevant_chunks, NotAuthorizedError
from app.services.chat_client import generate_answer, generate_answer_stream, GeminiChatError
from app.services.evaluation_logging import log_ai_interaction

logger = logging.getLogger(__name__)

# Empirically validated cosine distance threshold from production testing (Material ID 8).
# Distances < 0.40 represent strong semantic overlap; distances >= 0.40 indicate unrelated content.
MAX_RELEVANCE_DISTANCE = 0.40

UNGROUNDED_FALLBACK_ANSWER = "I couldn't find this in your classroom materials."


async def answer_course_question(
    user_id: int,
    classroom_id: int,
    topic_id: int | None,
    query: str,
    socratic_mode: bool = False,
) -> dict:
    start_time = time.time()

    """
    Answers a student/teacher question grounded strictly in their classroom materials.

    Args:
        user_id: ID of the user asking the question.
        classroom_id: ID of the classroom scope.
        topic_id: Optional topic ID filter.
        query: Question string.
        socratic_mode: If True, guides the student with questions/hints rather than direct answers.

    Returns:
        Dict with keys:
            - answer (str): Generated text answer or ungrounded fallback string.
            - grounded (bool): True if answered from retrieved context; False if short-circuited.
            - sources (list[dict]): List of material title, ID, and chunk index provided to the model.

    Raises:
        NotAuthorizedError: If user is not an active member of the classroom (propagated from retrieval).
    """
    # Step 1: Pre-search authorized vector retrieval (propagates NotAuthorizedError if user unauthorized)
    retrieved_chunks = await retrieve_relevant_chunks(
        user_id=user_id,
        classroom_id=classroom_id,
        query_text=query,
        topic_id=topic_id,
    )

    # Step 2: Relevance threshold filtering
    filtered_chunks = [
        chunk for chunk in retrieved_chunks if chunk["distance"] <= MAX_RELEVANCE_DISTANCE
    ]

    # Step 3: Short-circuit if no relevant chunks remain
    if not filtered_chunks:
        logger.info(
            f"User {user_id} in classroom {classroom_id}: 0 chunks passed distance threshold {MAX_RELEVANCE_DISTANCE}. Returning fallback."
        )
        latency_ms = int((time.time() - start_time) * 1000)
        try:
            await log_ai_interaction(
                interaction_type="COURSE_CHAT",
                user_id=user_id,
                classroom_id=classroom_id,
                model="gemini-3.6-flash",
                latency_ms=latency_ms,
                grounded=False,
                retrieved_chunk_ids=[],
                socratic_mode=socratic_mode,
                query_text=query,
                answer_text=UNGROUNDED_FALLBACK_ANSWER,
            )
        except Exception as log_exc:
            logger.warning("Failed to log AI interaction telemetry: %s", log_exc)
        return {
            "answer": UNGROUNDED_FALLBACK_ANSWER,
            "grounded": False,
            "sources": [],
        }

    # Step 4: Construct strict grounding system prompt (Direct vs Socratic variant)
    context_blocks = []
    for c in filtered_chunks:
        block = (
            f"[Source: {c['material_title']} (Material ID: {c['material_id']}, Chunk {c['chunk_index']})]\n"
            f"{c['chunk_text']}"
        )
        context_blocks.append(block)

    formatted_context = "\n\n".join(context_blocks)

    if socratic_mode:
        system_prompt = (
            "You are a supportive, Socratic course tutor for the Daily Learning Planner.\n"
            "Your goal is to guide the student toward understanding rather than giving the direct answer immediately, "
            "using ONLY the provided classroom context materials below.\n\n"
            "SOCRATIC GROUNDING RULES:\n"
            "1. Base your guidance and hints EXCLUSIVELY on the information present in the context materials.\n"
            "2. Do NOT reveal the full, direct answer right away. Instead, ask a thoughtful guiding question or provide a targeted hint that helps the student reason through the concept themselves.\n"
            "3. Do NOT use outside knowledge, assumptions, or unmentioned facts.\n"
            "4. If the provided context materials do not contain relevant information to guide the student, state honestly: "
            f"\"{UNGROUNDED_FALLBACK_ANSWER}\"\n"
            "5. Keep your guiding response concise, encouraging, and focused on one reasoning step at a time.\n\n"
            "Classroom Context Materials:\n"
            f"{formatted_context}"
        )
    else:
        system_prompt = (
            "You are an expert, precise course assistant for the Daily Learning Planner.\n"
            "Your task is to answer the student's question ONLY using the provided classroom context materials below.\n\n"
            "STRICT GROUNDING RULES:\n"
            "1. Base your answer EXCLUSIVELY on the information present in the context materials.\n"
            "2. Do NOT use outside knowledge, assumptions, or unmentioned facts.\n"
            "3. If the provided context materials do not contain the answer, state honestly: "
            f"\"{UNGROUNDED_FALLBACK_ANSWER}\"\n"
            "4. Keep the answer clear, structured, and directly responsive to the query.\n\n"
            "Classroom Context Materials:\n"
            f"{formatted_context}"
        )

    # Step 5: Generate answer via non-blocking offload to Gemini Chat API
    answer_text = await asyncio.to_thread(generate_answer, system_prompt, query)

    # Step 6: Assemble sources attribution
    sources = [
        {
            "material_title": c["material_title"],
            "material_id": c["material_id"],
            "chunk_index": c["chunk_index"],
        }
        for c in filtered_chunks
    ]

    # Step 7: Log AI Interaction telemetry (non-blocking)
    latency_ms = int((time.time() - start_time) * 1000)
    chunk_ids = [
        str(c["id"]) if "id" in c and c["id"] is not None else str(c["material_id"])
        for c in filtered_chunks
        if c.get("id") is not None or c.get("material_id") is not None
    ]
    try:
        await log_ai_interaction(
            interaction_type="COURSE_CHAT",
            user_id=user_id,
            classroom_id=classroom_id,
            model="gemini-3.6-flash",
            latency_ms=latency_ms,
            grounded=True,
            retrieved_chunk_ids=chunk_ids,
            socratic_mode=socratic_mode,
            query_text=query,
            answer_text=answer_text,
        )
    except Exception as log_exc:
        logger.warning("Failed to log AI interaction telemetry: %s", log_exc)

    return {
        "answer": answer_text,
        "grounded": True,
        "sources": sources,
    }


async def stream_course_question(
    user_id: int,
    classroom_id: int,
    topic_id: int | None,
    query: str,
    socratic_mode: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Streams a grounded answer for a student/teacher question using Server-Sent Events (SSE).

    Yields SSE events formatted as:
        data: {"type": "chunk", "delta": "..."}\n\n
        data: {"type": "done", "grounded": bool, "sources": [...], "interaction_id": "..."}\n\n
        data: {"type": "error", "detail": "..."}\n\n

    Telemetries are persisted to the database via log_ai_interaction in all cases,
    including fallback responses and mid-stream errors.
    """
    start_time = time.perf_counter()

    # Step 1: Pre-search authorized vector retrieval (propagates NotAuthorizedError)
    retrieved_chunks = await retrieve_relevant_chunks(
        user_id=user_id,
        classroom_id=classroom_id,
        query_text=query,
        topic_id=topic_id,
    )

    # Step 2: Relevance threshold filtering
    filtered_chunks = [
        chunk for chunk in retrieved_chunks if chunk["distance"] <= MAX_RELEVANCE_DISTANCE
    ]

    # Step 3: Short-circuit fallback if no chunks meet the distance threshold
    if not filtered_chunks:
        logger.info(
            f"User {user_id} in classroom {classroom_id}: 0 chunks passed distance threshold {MAX_RELEVANCE_DISTANCE}. Returning fallback SSE stream."
        )
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        interaction_id = None
        try:
            interaction_id = await log_ai_interaction(
                interaction_type="COURSE_CHAT",
                user_id=user_id,
                classroom_id=classroom_id,
                model="gemini-3.6-flash",
                latency_ms=latency_ms,
                grounded=False,
                retrieved_chunk_ids=[],
                socratic_mode=socratic_mode,
                query_text=query,
                answer_text=UNGROUNDED_FALLBACK_ANSWER,
            )
        except Exception as log_exc:
            logger.warning("Failed to log AI interaction telemetry: %s", log_exc)

        # Consistent SSE format: single chunk event followed by done event
        chunk_event = {"type": "chunk", "delta": UNGROUNDED_FALLBACK_ANSWER}
        yield f"data: {json.dumps(chunk_event)}\n\n"

        done_event = {
            "type": "done",
            "grounded": False,
            "sources": [],
            "interaction_id": str(interaction_id) if interaction_id else None,
        }
        yield f"data: {json.dumps(done_event)}\n\n"
        return

    # Step 4: Construct grounding system prompt (Direct vs Socratic)
    context_blocks = []
    for c in filtered_chunks:
        block = (
            f"[Source: {c['material_title']} (Material ID: {c['material_id']}, Chunk {c['chunk_index']})]\n"
            f"{c['chunk_text']}"
        )
        context_blocks.append(block)

    formatted_context = "\n\n".join(context_blocks)

    if socratic_mode:
        system_prompt = (
            "You are a supportive, Socratic course tutor for the Daily Learning Planner.\n"
            "Your goal is to guide the student toward understanding rather than giving the direct answer immediately, "
            "using ONLY the provided classroom context materials below.\n\n"
            "SOCRATIC GROUNDING RULES:\n"
            "1. Base your guidance and hints EXCLUSIVELY on the information present in the context materials.\n"
            "2. Do NOT reveal the full, direct answer right away. Instead, ask a thoughtful guiding question or provide a targeted hint that helps the student reason through the concept themselves.\n"
            "3. Do NOT use outside knowledge, assumptions, or unmentioned facts.\n"
            "4. If the provided context materials do not contain relevant information to guide the student, state honestly: "
            f"\"{UNGROUNDED_FALLBACK_ANSWER}\"\n"
            "5. Keep your guiding response concise, encouraging, and focused on one reasoning step at a time.\n\n"
            "Classroom Context Materials:\n"
            f"{formatted_context}"
        )
    else:
        system_prompt = (
            "You are an expert, precise course assistant for the Daily Learning Planner.\n"
            "Your task is to answer the student's question ONLY using the provided classroom context materials below.\n\n"
            "STRICT GROUNDING RULES:\n"
            "1. Base your answer EXCLUSIVELY on the information present in the context materials.\n"
            "2. Do NOT use outside knowledge, assumptions, or unmentioned facts.\n"
            "3. If the provided context materials do not contain the answer, state honestly: "
            f"\"{UNGROUNDED_FALLBACK_ANSWER}\"\n"
            "4. Keep the answer clear, structured, and directly responsive to the query.\n\n"
            "Classroom Context Materials:\n"
            f"{formatted_context}"
        )

    sources = [
        {
            "material_title": c["material_title"],
            "material_id": c["material_id"],
            "chunk_index": c["chunk_index"],
        }
        for c in filtered_chunks
    ]
    chunk_ids = [
        str(c["id"]) if "id" in c and c["id"] is not None else str(c["material_id"])
        for c in filtered_chunks
        if c.get("id") is not None or c.get("material_id") is not None
    ]

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
        logger.error(f"Error during course chat stream for user {user_id}: {e}")
        error_event = {"type": "error", "detail": f"Stream error: {e}"}
        yield f"data: {json.dumps(error_event)}\n\n"
    finally:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        full_answer = "".join(accumulated_chunks)
        interaction_id = None
        try:
            interaction_id = await log_ai_interaction(
                interaction_type="COURSE_CHAT",
                user_id=user_id,
                classroom_id=classroom_id,
                model="gemini-3.6-flash",
                latency_ms=latency_ms,
                grounded=True,
                retrieved_chunk_ids=chunk_ids,
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
                "grounded": True,
                "sources": sources,
                "interaction_id": str(interaction_id) if interaction_id else None,
            }
            yield f"data: {json.dumps(done_event)}\n\n"



