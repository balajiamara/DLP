"""
AI Evaluation Logging Service (Step 42)

Observability and evaluation telemetry for all AI interactions:
- Course Chat
- General Chat
- Quiz Generation
- Study Plan Generation
- Personalized Assistant

Design Rules:
1. NON-BLOCKING / RESILIENT: Logging failures must NEVER fail or delay the caller.
2. CITATION COVERAGE PROXY: Measures presence of retrieved chunks in grounded answers,
   not semantic per-claim verification (per step 34 scope).
3. INTERACTION_ID: Single-turn correlation UUID (will evolve to conversation_id with multi-turn history).
4. DATA RETENTION / PRIVACY: Query and answer texts are truncated to 500 characters.
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, func, text

from app.db.session import async_session_maker
from app.db.models import AIInteractionLog

logger = logging.getLogger(__name__)

MAX_TEXT_LOG_LENGTH = 500

CITATION_COVERAGE_NOTE = (
    "Citation coverage is defined as the percentage of grounded answers (grounded=true) "
    "that have at least one retrieved source chunk associated with them. "
    "This is an availability proxy and does not measure true per-claim semantic citation accuracy."
)


def _truncate_text(val: Optional[str], limit: int = MAX_TEXT_LOG_LENGTH) -> Optional[str]:
    if not val:
        return None
    val_str = str(val).strip()
    return val_str[:limit] if len(val_str) > limit else val_str


async def log_ai_interaction(
    interaction_type: str,
    user_id: int,
    classroom_id: Optional[int],
    model: str,
    latency_ms: int,
    grounded: Optional[bool] = None,
    retrieved_chunk_ids: Optional[List[Any]] = None,
    socratic_mode: Optional[bool] = None,
    query_text: Optional[str] = None,
    answer_text: Optional[str] = None,
    error_occurred: bool = False,
    error_message: Optional[str] = None,
) -> Optional[uuid.UUID]:
    """
    Safely records an AI interaction telemetry log in PostgreSQL.
    Guaranteed NEVER to raise an exception or fail the caller's operation.
    """
    try:
        chunk_ids = list(retrieved_chunk_ids or [])
        chunk_count = len(chunk_ids)

        log_record = AIInteractionLog(
            interaction_id=uuid.uuid4(),
            interaction_type=interaction_type,
            user_id=int(user_id),
            classroom_id=int(classroom_id) if classroom_id is not None else None,
            model=str(model),
            grounded=grounded,
            retrieved_chunk_ids=chunk_ids,
            retrieved_chunk_count=chunk_count,
            socratic_mode=socratic_mode,
            latency_ms=int(latency_ms),
            query_text=_truncate_text(query_text),
            answer_text=_truncate_text(answer_text),
            error_occurred=bool(error_occurred),
            error_message=_truncate_text(error_message, 250),
        )

        async with async_session_maker() as session:
            session.add(log_record)
            await session.commit()
            await session.refresh(log_record)
            return log_record.id

    except Exception as exc:
        # NON-BLOCKING ISOLATION: Log as warning, never propagate error to caller!
        logger.warning("Failed to record AI interaction log (non-blocking fallback): %s", exc)
        return None


async def record_feedback(
    log_id: uuid.UUID,
    rating: str,
    reason: Optional[str] = None,
) -> bool:
    """
    Records user feedback ('up' or 'down') for an existing AI interaction log row.
    Returns True if row existed and was updated, False if not found.
    """
    async with async_session_maker() as session:
        stmt = (
            update(AIInteractionLog)
            .where(AIInteractionLog.id == log_id)
            .values(
                feedback_rating=rating.lower(),
                feedback_reason=_truncate_text(reason, 1000),
            )
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def get_evaluation_summary(
    classroom_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Aggregates AI interaction metrics:
    - Interaction counts total and by type
    - Grounded answer rate vs fallback rate (Course Chat)
    - Citation coverage proxy
    - Average latency overall and per type
    - Feedback breakdown
    - Error rate
    """
    async with async_session_maker() as session:
        query = select(AIInteractionLog)

        if classroom_id is not None:
            query = query.where(AIInteractionLog.classroom_id == classroom_id)
        if start_date is not None:
            query = query.where(AIInteractionLog.created_at >= start_date)
        if end_date is not None:
            query = query.where(AIInteractionLog.created_at <= end_date)

        result = await session.execute(query)
        logs: List[AIInteractionLog] = list(result.scalars().all())

    total_count = len(logs)
    if total_count == 0:
        return {
            "total_interactions": 0,
            "interaction_counts": {},
            "course_chat_metrics": {
                "total_course_chats": 0,
                "grounded_answer_rate": 0.0,
                "fallback_rate": 0.0,
                "citation_coverage": 0.0,
                "citation_coverage_note": CITATION_COVERAGE_NOTE,
            },
            "latency_metrics": {
                "overall_average_latency_ms": 0.0,
                "latency_by_type": {},
            },
            "feedback_metrics": {
                "total_feedback_count": 0,
                "feedback_rate": 0.0,
                "up_count": 0,
                "down_count": 0,
            },
            "error_rate": 0.0,
        }

    # 1. Counts by type
    counts_by_type: Dict[str, int] = {}
    latencies_by_type: Dict[str, List[int]] = {}
    error_count = 0
    feedback_up = 0
    feedback_down = 0

    course_chat_total = 0
    course_chat_grounded = 0
    course_chat_fallback = 0
    course_chat_with_citations = 0

    total_latency = 0

    for l in logs:
        t = l.interaction_type
        counts_by_type[t] = counts_by_type.get(t, 0) + 1
        latencies_by_type.setdefault(t, []).append(l.latency_ms)
        total_latency += l.latency_ms

        if l.error_occurred:
            error_count += 1

        if l.feedback_rating == "up":
            feedback_up += 1
        elif l.feedback_rating == "down":
            feedback_down += 1

        if t == "COURSE_CHAT":
            course_chat_total += 1
            if l.grounded is True:
                course_chat_grounded += 1
                if l.retrieved_chunk_count > 0:
                    course_chat_with_citations += 1
            elif l.grounded is False:
                course_chat_fallback += 1

    # Compute rates
    grounded_rate = round(course_chat_grounded / course_chat_total, 4) if course_chat_total > 0 else 0.0
    fallback_rate = round(course_chat_fallback / course_chat_total, 4) if course_chat_total > 0 else 0.0
    citation_coverage = (
        round(course_chat_with_citations / course_chat_grounded, 4)
        if course_chat_grounded > 0
        else 0.0
    )

    avg_latency = round(total_latency / total_count, 2)
    avg_latency_by_type = {
        t: round(sum(lats) / len(lats), 2)
        for t, lats in latencies_by_type.items()
    }

    feedback_total = feedback_up + feedback_down
    feedback_pct = round(feedback_total / total_count, 4)
    error_rate = round(error_count / total_count, 4)

    return {
        "total_interactions": total_count,
        "interaction_counts": counts_by_type,
        "course_chat_metrics": {
            "total_course_chats": course_chat_total,
            "grounded_answer_rate": grounded_rate,
            "fallback_rate": fallback_rate,
            "citation_coverage": citation_coverage,
            "citation_coverage_note": CITATION_COVERAGE_NOTE,
        },
        "latency_metrics": {
            "overall_average_latency_ms": avg_latency,
            "latency_by_type": avg_latency_by_type,
        },
        "feedback_metrics": {
            "total_feedback_count": feedback_total,
            "feedback_rate": feedback_pct,
            "up_count": feedback_up,
            "down_count": feedback_down,
        },
        "error_rate": error_rate,
    }
