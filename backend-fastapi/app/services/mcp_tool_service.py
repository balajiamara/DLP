"""
MCP Tool Services for Daily Learning Planner

Implements business logic and queries for the 5 MCP tools:
1. get_student_progress: Student learning progress, quiz attempts, and completion percentage.
2. get_pending_tasks: Unsubmitted assignments and unattempted quizzes.
3. search_course_material: Vector search retrieval across classroom materials (delegates to Step 33).
4. get_weak_topics: Topics with REVIEW_REQUIRED or quiz scores below threshold (70%).
5. recommend_next_topic: Explainable topic recommendation based on weak topics and syllabus hierarchy.

All queries enforce strict authorization:
- Caller must be an active student or teacher in the classroom.
- Cross-student access is restricted to teachers only.
- Generic error messages ("Access denied or classroom not found") prevent user/classroom enumeration.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy import text

from app.db.session import async_session_maker
from app.services.rag_retrieval import (
    is_authorized_for_classroom,
    retrieve_relevant_chunks,
    NotAuthorizedError,
)
from app.services.mcp_resource_service import (
    is_teacher_for_classroom,
    get_student_progress_resource,
    MCPAuthorizationError,
    MCPNotFoundError,
)

# Standard passing/mastery threshold per Phase 2 assessments logic
WEAK_TOPIC_QUIZ_THRESHOLD: int = 70

# Non-leaking generic error messages
ERR_ACCESS_DENIED_CLASSROOM = "Access denied or classroom not found"
ERR_ACCESS_DENIED_STUDENT = "Access denied or student not found"


async def get_student_progress_data(
    caller_user_id: int,
    classroom_id: int,
    target_user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Returns student progress data for the given classroom.
    Reuses the proven logic from get_student_progress_resource.
    """
    caller_user_id = int(caller_user_id)
    classroom_id = int(classroom_id)
    target_uid = int(target_user_id) if target_user_id is not None else caller_user_id

    # 1. Base authorization check
    if not await is_authorized_for_classroom(user_id=caller_user_id, classroom_id=classroom_id):
        raise MCPAuthorizationError(ERR_ACCESS_DENIED_CLASSROOM)

    # 2. Cross-user privacy check
    if target_uid != caller_user_id:
        if not await is_teacher_for_classroom(user_id=caller_user_id, classroom_id=classroom_id):
            raise MCPAuthorizationError(ERR_ACCESS_DENIED_STUDENT)

    return await get_student_progress_resource(
        requesting_user_id=caller_user_id,
        classroom_id=classroom_id,
        target_user_id=target_uid,
    )


async def get_pending_tasks_data(
    caller_user_id: int,
    classroom_id: int,
) -> Dict[str, Any]:
    """
    Queries assignments and quizzes in the classroom that the calling student
    has not submitted or attempted yet.
    """
    caller_user_id = int(caller_user_id)
    classroom_id = int(classroom_id)

    if not await is_authorized_for_classroom(user_id=caller_user_id, classroom_id=classroom_id):
        raise MCPAuthorizationError(ERR_ACCESS_DENIED_CLASSROOM)

    now_utc = datetime.now(timezone.utc)

    async with async_session_maker() as session:
        # 1. Unsubmitted assignments
        assignments_res = await session.execute(
            text("""
                SELECT 
                    a.id, 
                    a.title, 
                    a.description, 
                    a.topic_id, 
                    a.due_date, 
                    a.created_at,
                    t.title as topic_title
                FROM assessments_assignment a
                LEFT JOIN syllabus_topic t ON a.topic_id = t.id
                LEFT JOIN assessments_submission s ON a.id = s.assignment_id AND s.student_id = :uid
                WHERE a.classroom_id = :cid AND s.id IS NULL
                ORDER BY a.due_date ASC NULLS LAST, a.created_at DESC
            """),
            {"cid": classroom_id, "uid": caller_user_id}
        )
        pending_assignments = []
        for row in assignments_res.mappings():
            due_date = row["due_date"]
            due_date_iso = due_date.isoformat() if due_date else None
            is_overdue = False
            if due_date:
                # Ensure timezone aware comparison
                due_aware = due_date if due_date.tzinfo else due_date.replace(tzinfo=timezone.utc)
                is_overdue = due_aware < now_utc

            created_at = row["created_at"]
            created_at_iso = created_at.isoformat() if created_at else None

            pending_assignments.append({
                "id": row["id"],
                "title": row["title"],
                "description": row["description"] or "",
                "topic_id": row["topic_id"],
                "topic_title": row["topic_title"] or "General",
                "due_date": due_date_iso,
                "is_overdue": is_overdue,
                "created_at": created_at_iso,
            })

        # 2. Unattempted quizzes
        quizzes_res = await session.execute(
            text("""
                SELECT 
                    q.id, 
                    q.title, 
                    q.topic_id, 
                    q.created_at,
                    t.title as topic_title
                FROM assessments_quiz q
                LEFT JOIN syllabus_topic t ON q.topic_id = t.id
                LEFT JOIN assessments_quizattempt qa ON q.id = qa.quiz_id AND qa.student_id = :uid
                WHERE q.classroom_id = :cid AND qa.id IS NULL
                ORDER BY q.created_at DESC
            """),
            {"cid": classroom_id, "uid": caller_user_id}
        )
        pending_quizzes = []
        for row in quizzes_res.mappings():
            created_at = row["created_at"]
            created_at_iso = created_at.isoformat() if created_at else None

            pending_quizzes.append({
                "id": row["id"],
                "title": row["title"],
                "topic_id": row["topic_id"],
                "topic_title": row["topic_title"] or "General",
                "created_at": created_at_iso,
            })

        return {
            "classroom_id": classroom_id,
            "student_id": caller_user_id,
            "pending_assignments": pending_assignments,
            "pending_quizzes": pending_quizzes,
            "total_pending_tasks": len(pending_assignments) + len(pending_quizzes),
        }


async def search_course_material_data(
    caller_user_id: int,
    classroom_id: int,
    query: str,
) -> Dict[str, Any]:
    """
    Directly delegates to Step 33's retrieve_relevant_chunks for authorization-scoped
    vector search retrieval across classroom materials.
    """
    caller_user_id = int(caller_user_id)
    classroom_id = int(classroom_id)

    # 1. Base authorization check
    if not await is_authorized_for_classroom(user_id=caller_user_id, classroom_id=classroom_id):
        raise MCPAuthorizationError(ERR_ACCESS_DENIED_CLASSROOM)

    try:
        chunks = await retrieve_relevant_chunks(
            user_id=caller_user_id,
            classroom_id=classroom_id,
            query_text=query,
        )
    except NotAuthorizedError:
        raise MCPAuthorizationError(ERR_ACCESS_DENIED_CLASSROOM)

    formatted_chunks = [
        {
            "chunk_id": c.get("id"),
            "material_id": c.get("material_id"),
            "material_title": c.get("material_title"),
            "content": c.get("chunk_text"),
            "similarity_score": round(float(c.get("score", 0.0)), 4),
            "distance": round(float(c.get("distance", 0.0)), 4),
        }
        for c in chunks
    ]

    return {
        "classroom_id": classroom_id,
        "query": query,
        "chunks": formatted_chunks,
        "total_results": len(formatted_chunks),
    }


async def get_weak_topics_data(
    caller_user_id: int,
    classroom_id: int,
    target_user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Identifies topics in the classroom where the target student requires review:
    1. TopicProgress.learning_state == 'REVIEW_REQUIRED', or
    2. Latest quiz score under the topic is below WEAK_TOPIC_QUIZ_THRESHOLD (70%).
    """
    caller_user_id = int(caller_user_id)
    classroom_id = int(classroom_id)
    target_uid = int(target_user_id) if target_user_id is not None else caller_user_id

    # 1. Base authorization check
    if not await is_authorized_for_classroom(user_id=caller_user_id, classroom_id=classroom_id):
        raise MCPAuthorizationError(ERR_ACCESS_DENIED_CLASSROOM)

    # 2. Cross-user privacy check
    if target_uid != caller_user_id:
        if not await is_teacher_for_classroom(user_id=caller_user_id, classroom_id=classroom_id):
            raise MCPAuthorizationError(ERR_ACCESS_DENIED_STUDENT)

    async with async_session_maker() as session:
        # Query topics with hierarchical info, student progress, and quiz scores
        rows_res = await session.execute(
            text("""
                SELECT 
                    t.id as topic_id,
                    t.title as topic_title,
                    t."order" as topic_order,
                    m.id as module_id,
                    m.title as module_title,
                    m."order" as module_order,
                    c.id as course_id,
                    c.title as course_title,
                    c."order" as course_order,
                    tp.learning_state,
                    MAX(qa.score) as latest_quiz_score
                FROM syllabus_topic t
                JOIN syllabus_module m ON t.module_id = m.id
                JOIN syllabus_course c ON m.course_id = c.id
                LEFT JOIN syllabus_topicprogress tp ON t.id = tp.topic_id AND tp.student_id = :uid
                LEFT JOIN assessments_quiz q ON t.id = q.topic_id AND q.classroom_id = :cid
                LEFT JOIN assessments_quizattempt qa ON q.id = qa.quiz_id AND qa.student_id = :uid
                WHERE c.classroom_id = :cid
                GROUP BY t.id, t.title, t."order", m.id, m.title, m."order", c.id, c.title, c."order", tp.learning_state
                ORDER BY c."order", c.id, m."order", m.id, t."order", t.id
            """),
            {"cid": classroom_id, "uid": target_uid}
        )

        weak_topics = []
        for r in rows_res.mappings():
            learning_state = r["learning_state"] or "NOT_STARTED"
            quiz_score = r["latest_quiz_score"]

            is_review_required = (learning_state == "REVIEW_REQUIRED")
            is_low_score = (quiz_score is not None and quiz_score < WEAK_TOPIC_QUIZ_THRESHOLD)

            if is_review_required or is_low_score:
                if is_review_required and is_low_score:
                    reason = f"Flagged as REVIEW_REQUIRED and quiz score ({quiz_score}%) is below {WEAK_TOPIC_QUIZ_THRESHOLD}%"
                elif is_low_score:
                    reason = f"Quiz score ({quiz_score}%) is below mastery threshold of {WEAK_TOPIC_QUIZ_THRESHOLD}%"
                else:
                    reason = "Topic flagged as REVIEW_REQUIRED"

                weak_topics.append({
                    "topic_id": r["topic_id"],
                    "topic_title": r["topic_title"],
                    "module_title": r["module_title"],
                    "course_title": r["course_title"],
                    "learning_state": learning_state,
                    "quiz_score": quiz_score,
                    "reason": reason,
                })

        return {
            "classroom_id": classroom_id,
            "student_id": target_uid,
            "threshold": WEAK_TOPIC_QUIZ_THRESHOLD,
            "weak_topics": weak_topics,
            "total_weak_topics": len(weak_topics),
        }


async def recommend_next_topic_data(
    caller_user_id: int,
    classroom_id: int,
    target_user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Recommends the next topic for the target student with explainable reasoning:
    1. Priority 1 (Weak Topics): If any topics have REVIEW_REQUIRED or quiz score < 70%,
       recommends the first weak topic in syllabus order.
    2. Priority 2 (Next Sequential Topic): The first topic in syllabus order that is not
       yet completed or mastered (NOT_STARTED, LEARNING, PRACTICING).
    3. Priority 3 (All Completed): If all topics are completed/mastered, returns None with
       congratulatory / review advice.
    """
    caller_user_id = int(caller_user_id)
    classroom_id = int(classroom_id)
    target_uid = int(target_user_id) if target_user_id is not None else caller_user_id

    # 1. Base authorization check
    if not await is_authorized_for_classroom(user_id=caller_user_id, classroom_id=classroom_id):
        raise MCPAuthorizationError(ERR_ACCESS_DENIED_CLASSROOM)

    # 2. Cross-user privacy check
    if target_uid != caller_user_id:
        if not await is_teacher_for_classroom(user_id=caller_user_id, classroom_id=classroom_id):
            raise MCPAuthorizationError(ERR_ACCESS_DENIED_STUDENT)

    async with async_session_maker() as session:
        # Fetch all topics ordered by syllabus hierarchy: course.order -> module.order -> topic.order -> topic.id
        rows_res = await session.execute(
            text("""
                SELECT 
                    t.id as topic_id,
                    t.title as topic_title,
                    t."order" as topic_order,
                    m.id as module_id,
                    m.title as module_title,
                    m."order" as module_order,
                    c.id as course_id,
                    c.title as course_title,
                    c."order" as course_order,
                    tp.learning_state,
                    MAX(qa.score) as latest_quiz_score
                FROM syllabus_topic t
                JOIN syllabus_module m ON t.module_id = m.id
                JOIN syllabus_course c ON m.course_id = c.id
                LEFT JOIN syllabus_topicprogress tp ON t.id = tp.topic_id AND tp.student_id = :uid
                LEFT JOIN assessments_quiz q ON t.id = q.topic_id AND q.classroom_id = :cid
                LEFT JOIN assessments_quizattempt qa ON q.id = qa.quiz_id AND qa.student_id = :uid
                WHERE c.classroom_id = :cid
                GROUP BY t.id, t.title, t."order", m.id, m.title, m."order", c.id, c.title, c."order", tp.learning_state
                ORDER BY c."order", c.id, m."order", m.id, t."order", t.id
            """),
            {"cid": classroom_id, "uid": target_uid}
        )
        all_topics = list(rows_res.mappings())

        if not all_topics:
            return {
                "classroom_id": classroom_id,
                "student_id": target_uid,
                "recommended_topic": None,
                "reason": "No syllabus topics found in this classroom.",
            }

        # Step 1: Check for weak topics first (Priority 1)
        for r in all_topics:
            learning_state = r["learning_state"] or "NOT_STARTED"
            quiz_score = r["latest_quiz_score"]

            is_review_required = (learning_state == "REVIEW_REQUIRED")
            is_low_score = (quiz_score is not None and quiz_score < WEAK_TOPIC_QUIZ_THRESHOLD)

            if is_review_required or is_low_score:
                if is_low_score:
                    reason = f"Topic requires review due to low quiz score ({quiz_score}% < {WEAK_TOPIC_QUIZ_THRESHOLD}%): {r['topic_title']} ({r['course_title']} > {r['module_title']})"
                else:
                    reason = f"Topic flagged as REVIEW_REQUIRED for reinforcement: {r['topic_title']} ({r['course_title']} > {r['module_title']})"

                return {
                    "classroom_id": classroom_id,
                    "student_id": target_uid,
                    "recommended_topic": {
                        "topic_id": r["topic_id"],
                        "title": r["topic_title"],
                        "module_title": r["module_title"],
                        "course_title": r["course_title"],
                        "learning_state": learning_state,
                        "quiz_score": quiz_score,
                    },
                    "reason": reason,
                }

        # Step 2: Check for next uncompleted topic in sequential syllabus order (Priority 2)
        for r in all_topics:
            learning_state = r["learning_state"] or "NOT_STARTED"
            if learning_state not in ("COMPLETED", "MASTERED"):
                if learning_state in ("LEARNING", "PRACTICING"):
                    reason = f"Continue in-progress topic: {r['topic_title']} ({r['course_title']} > {r['module_title']})"
                else:
                    reason = f"Next sequential topic in syllabus: {r['topic_title']} ({r['course_title']} > {r['module_title']})"

                return {
                    "classroom_id": classroom_id,
                    "student_id": target_uid,
                    "recommended_topic": {
                        "topic_id": r["topic_id"],
                        "title": r["topic_title"],
                        "module_title": r["module_title"],
                        "course_title": r["course_title"],
                        "learning_state": learning_state,
                        "quiz_score": r["latest_quiz_score"],
                    },
                    "reason": reason,
                }

        # Step 3: All topics completed (Priority 3)
        return {
            "classroom_id": classroom_id,
            "student_id": target_uid,
            "recommended_topic": None,
            "reason": "All syllabus topics completed! Recommend reviewing previous topics or exploring advanced material.",
        }
