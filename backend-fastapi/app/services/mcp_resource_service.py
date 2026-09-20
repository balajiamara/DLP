"""
MCP Resource Service

Queries and aggregates data from Django-managed PostgreSQL tables for MCP resources:
- Classroom Overview: classroom details, teacher info, active student count.
- Course Structure: hierarchical course -> module -> topic -> (material, resource) tree.
- Student Progress: topic completion states, quiz attempts, assignments, completion metrics.
- Learning History: chronological unified timeline of progress, quizzes, assignments, doubts.

Security:
All methods enforce active classroom membership and cross-student privacy before querying.
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from app.db.session import async_session_maker
from app.services.rag_retrieval import is_authorized_for_classroom


class MCPAuthorizationError(PermissionError):
    """Raised when an MCP resource access is unauthorized."""
    pass


class MCPNotFoundError(ValueError):
    """Raised when an MCP resource is not found."""
    pass


async def is_teacher_for_classroom(user_id: int, classroom_id: int) -> bool:
    """Checks if a user is the teacher or has TEACHER role in the classroom."""
    async with async_session_maker() as session:
        # Check if user is the designated classroom teacher
        res = await session.execute(
            text("SELECT teacher_id FROM classrooms_classroom WHERE id = :cid"),
            {"cid": classroom_id}
        )
        row = res.first()
        if row and row[0] == user_id:
            return True

        # Also check classroom membership role
        mem_res = await session.execute(
            text("""
                SELECT 1 FROM classrooms_classroommembership
                WHERE classroom_id = :cid AND user_id = :uid
                  AND role_in_classroom = 'TEACHER' AND status = 'ACTIVE'
            """),
            {"cid": classroom_id, "uid": user_id}
        )
        return mem_res.first() is not None


async def get_classroom_overview_resource(user_id: int, classroom_id: int) -> Dict[str, Any]:
    """
    Returns classroom overview: name, description, teacher, student count.
    Authorized for any ACTIVE student or teacher in the classroom.
    """
    user_id = int(user_id)
    classroom_id = int(classroom_id)

    if not await is_authorized_for_classroom(user_id=user_id, classroom_id=classroom_id):
        raise MCPAuthorizationError(f"User {user_id} is not an active member of classroom {classroom_id}")

    async with async_session_maker() as session:
        res = await session.execute(
            text("""
                SELECT c.id, c.name, c.description, c.created_at,
                       u.id as teacher_id, u.username as teacher_username, u.email as teacher_email,
                       (
                           SELECT COUNT(*)
                           FROM classrooms_classroommembership cm
                           WHERE cm.classroom_id = c.id
                             AND cm.status = 'ACTIVE'
                             AND cm.role_in_classroom = 'STUDENT'
                       ) as student_count
                FROM classrooms_classroom c
                JOIN accounts_user u ON c.teacher_id = u.id
                WHERE c.id = :cid
            """),
            {"cid": classroom_id}
        )
        row = res.mappings().first()
        if not row:
            raise MCPNotFoundError(f"Classroom {classroom_id} not found")

        created_at_iso = row["created_at"].isoformat() if isinstance(row["created_at"], datetime) else str(row["created_at"])
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"] or "",
            "teacher": {
                "id": row["teacher_id"],
                "username": row["teacher_username"],
                "email": row["teacher_email"],
            },
            "student_count": row["student_count"],
            "created_at": created_at_iso,
        }


async def get_classroom_syllabus_resource(user_id: int, classroom_id: int) -> Dict[str, Any]:
    """
    Returns the complete hierarchical course structure for a classroom.
    Hierarchy: Courses -> Modules -> Topics -> (Materials, Resources).
    Authorized for any ACTIVE student or teacher in the classroom.
    """
    user_id = int(user_id)
    classroom_id = int(classroom_id)

    if not await is_authorized_for_classroom(user_id=user_id, classroom_id=classroom_id):
        raise MCPAuthorizationError(f"User {user_id} is not an active member of classroom {classroom_id}")

    async with async_session_maker() as session:
        # 1. Fetch courses
        courses_res = await session.execute(
            text("""
                SELECT id, title, description, "order"
                FROM syllabus_course
                WHERE classroom_id = :cid
                ORDER BY "order", id
            """),
            {"cid": classroom_id}
        )
        courses = [dict(r) for r in courses_res.mappings()]
        course_ids = [c["id"] for c in courses]

        if not course_ids:
            return {"classroom_id": classroom_id, "courses": []}

        # 2. Fetch modules
        modules_res = await session.execute(
            text("""
                SELECT id, course_id, title, description, "order"
                FROM syllabus_module
                WHERE course_id = ANY(:cids)
                ORDER BY "order", id
            """),
            {"cids": course_ids}
        )
        modules = [dict(r) for r in modules_res.mappings()]
        module_ids = [m["id"] for m in modules]

        # 3. Fetch topics
        topics_by_module: Dict[int, List[Dict[str, Any]]] = {m_id: [] for m_id in module_ids}
        topic_ids: List[int] = []
        if module_ids:
            topics_res = await session.execute(
                text("""
                    SELECT id, module_id, title, description, "order"
                    FROM syllabus_topic
                    WHERE module_id = ANY(:mids)
                    ORDER BY "order", id
                """),
                {"mids": module_ids}
            )
            for t in topics_res.mappings():
                td = dict(t)
                td["materials"] = []
                td["resources"] = []
                topics_by_module[td["module_id"]].append(td)
                topic_ids.append(td["id"])

        # 4. Fetch materials & resources for topics
        if topic_ids:
            mat_res = await session.execute(
                text("""
                    SELECT id, topic_id, title, file_type, status
                    FROM syllabus_material
                    WHERE topic_id = ANY(:tids)
                    ORDER BY id
                """),
                {"tids": topic_ids}
            )
            topic_materials: Dict[int, List[Dict[str, Any]]] = {}
            for m in mat_res.mappings():
                topic_materials.setdefault(m["topic_id"], []).append({
                    "id": m["id"],
                    "title": m["title"],
                    "file_type": m["file_type"],
                    "status": m["status"],
                })

            rec_res = await session.execute(
                text("""
                    SELECT id, topic_id, title, resource_type, url_or_note, "order"
                    FROM syllabus_resource
                    WHERE topic_id = ANY(:tids)
                    ORDER BY "order", id
                """),
                {"tids": topic_ids}
            )
            topic_resources: Dict[int, List[Dict[str, Any]]] = {}
            for r in rec_res.mappings():
                topic_resources.setdefault(r["topic_id"], []).append({
                    "id": r["id"],
                    "title": r["title"],
                    "resource_type": r["resource_type"],
                    "url_or_note": r["url_or_note"] or "",
                })

            for m_topics in topics_by_module.values():
                for t in m_topics:
                    t["materials"] = topic_materials.get(t["id"], [])
                    t["resources"] = topic_resources.get(t["id"], [])

        # 5. Assemble nested hierarchy
        modules_by_course: Dict[int, List[Dict[str, Any]]] = {c_id: [] for c_id in course_ids}
        for m in modules:
            m["topics"] = topics_by_module.get(m["id"], [])
            modules_by_course[m["course_id"]].append(m)

        for c in courses:
            c["modules"] = modules_by_course.get(c["id"], [])

        return {"classroom_id": classroom_id, "courses": courses}


async def get_student_progress_resource(
    requesting_user_id: int,
    classroom_id: int,
    target_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Returns student topic progress, completion percentages, quiz scores, and submissions.
    Authorization:
    - If target_user_id == requesting_user_id: Allowed for active student/teacher.
    - If target_user_id != requesting_user_id: Only allowed if requesting user is the classroom's teacher.
    """
    requesting_user_id = int(requesting_user_id)
    classroom_id = int(classroom_id)
    target_user_id = int(target_user_id) if target_user_id is not None else requesting_user_id

    # 1. Base classroom membership check
    if not await is_authorized_for_classroom(user_id=requesting_user_id, classroom_id=classroom_id):
        raise MCPAuthorizationError(f"User {requesting_user_id} is not an active member of classroom {classroom_id}")

    # 2. Cross-user privacy check
    if target_user_id != requesting_user_id:
        if not await is_teacher_for_classroom(user_id=requesting_user_id, classroom_id=classroom_id):
            raise MCPAuthorizationError(
                f"User {requesting_user_id} is not permitted to view progress for user {target_user_id}."
            )

    async with async_session_maker() as session:
        # Check target user membership in classroom
        target_mem = await session.execute(
            text("""
                SELECT 1 FROM classrooms_classroommembership
                WHERE classroom_id = :cid AND user_id = :uid AND status = 'ACTIVE'
            """),
            {"cid": classroom_id, "uid": target_user_id}
        )
        if not target_mem.first():
            raise MCPNotFoundError(f"Target user {target_user_id} has no active membership in classroom {classroom_id}")

        # Total topics in this classroom
        total_topics_res = await session.execute(
            text("""
                SELECT COUNT(t.id)
                FROM syllabus_topic t
                JOIN syllabus_module m ON t.module_id = m.id
                JOIN syllabus_course c ON m.course_id = c.id
                WHERE c.classroom_id = :cid
            """),
            {"cid": classroom_id}
        )
        total_topics = total_topics_res.scalar() or 0

        # Topic progress rows for target student
        progress_res = await session.execute(
            text("""
                SELECT tp.topic_id, t.title as topic_title, tp.learning_state, tp.updated_at
                FROM syllabus_topicprogress tp
                JOIN syllabus_topic t ON tp.topic_id = t.id
                JOIN syllabus_module m ON t.module_id = m.id
                JOIN syllabus_course c ON m.course_id = c.id
                WHERE c.classroom_id = :cid AND tp.student_id = :uid
                ORDER BY tp.updated_at DESC
            """),
            {"cid": classroom_id, "uid": target_user_id}
        )
        topic_progress = []
        completed_count = 0
        for r in progress_res.mappings():
            learning_state = r["learning_state"]
            if learning_state in ("COMPLETED", "MASTERED"):
                completed_count += 1
            updated_at_iso = r["updated_at"].isoformat() if isinstance(r["updated_at"], datetime) else str(r["updated_at"])
            topic_progress.append({
                "topic_id": r["topic_id"],
                "topic_title": r["topic_title"],
                "learning_state": learning_state,
                "updated_at": updated_at_iso,
            })

        # Quiz attempts
        quiz_res = await session.execute(
            text("""
                SELECT qa.id, q.title as quiz_title, qa.score, qa.attempted_at
                FROM assessments_quizattempt qa
                JOIN assessments_quiz q ON qa.quiz_id = q.id
                WHERE q.classroom_id = :cid AND qa.student_id = :uid
                ORDER BY qa.attempted_at DESC
            """),
            {"cid": classroom_id, "uid": target_user_id}
        )
        quizzes = []
        for q in quiz_res.mappings():
            attempted_at_iso = q["attempted_at"].isoformat() if isinstance(q["attempted_at"], datetime) else str(q["attempted_at"])
            quizzes.append({
                "id": q["id"],
                "title": q["quiz_title"],
                "score": q["score"],
                "attempted_at": attempted_at_iso,
            })

        # Submissions
        sub_res = await session.execute(
            text("""
                SELECT s.id, a.title as assignment_title, s.grade, s.submitted_at
                FROM assessments_submission s
                JOIN assessments_assignment a ON s.assignment_id = a.id
                WHERE a.classroom_id = :cid AND s.student_id = :uid
                ORDER BY s.submitted_at DESC
            """),
            {"cid": classroom_id, "uid": target_user_id}
        )
        submissions = []
        for s in sub_res.mappings():
            submitted_at_iso = s["submitted_at"].isoformat() if isinstance(s["submitted_at"], datetime) else str(s["submitted_at"])
            submissions.append({
                "id": s["id"],
                "title": s["assignment_title"],
                "grade": s["grade"],
                "submitted_at": submitted_at_iso,
            })

        completion_percentage = round((completed_count / total_topics * 100), 1) if total_topics > 0 else 0.0

        return {
            "classroom_id": classroom_id,
            "student_id": target_user_id,
            "summary_stats": {
                "total_topics": total_topics,
                "completed_topics": completed_count,
                "completion_percentage": completion_percentage,
                "quiz_attempts_count": len(quizzes),
                "assignment_submissions_count": len(submissions),
            },
            "topic_progress": topic_progress,
            "quiz_attempts": quizzes,
            "assignment_submissions": submissions,
        }


async def get_learning_history_resource(
    requesting_user_id: int,
    classroom_id: int,
    target_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Returns unified chronological learning history for a student.
    Aggregates:
    - TopicProgress updates
    - Quiz attempts
    - Assignment submissions
    - Doubts posted
    - Doubt replies posted
    Sorted descending by timestamp.
    """
    requesting_user_id = int(requesting_user_id)
    classroom_id = int(classroom_id)
    target_user_id = int(target_user_id) if target_user_id is not None else requesting_user_id

    # 1. Base classroom membership check
    if not await is_authorized_for_classroom(user_id=requesting_user_id, classroom_id=classroom_id):
        raise MCPAuthorizationError(f"User {requesting_user_id} is not an active member of classroom {classroom_id}")

    # 2. Cross-user privacy check
    if target_user_id != requesting_user_id:
        if not await is_teacher_for_classroom(user_id=requesting_user_id, classroom_id=classroom_id):
            raise MCPAuthorizationError(
                f"User {requesting_user_id} is not permitted to view learning history for user {target_user_id}."
            )

    events: List[Dict[str, Any]] = []

    async with async_session_maker() as session:
        # A. Topic Progress updates
        tp_res = await session.execute(
            text("""
                SELECT tp.topic_id, t.title as topic_title, tp.learning_state, tp.updated_at
                FROM syllabus_topicprogress tp
                JOIN syllabus_topic t ON tp.topic_id = t.id
                JOIN syllabus_module m ON t.module_id = m.id
                JOIN syllabus_course c ON m.course_id = c.id
                WHERE c.classroom_id = :cid AND tp.student_id = :uid
            """),
            {"cid": classroom_id, "uid": target_user_id}
        )
        for r in tp_res.mappings():
            dt = r["updated_at"]
            events.append({
                "type": "TOPIC_PROGRESS",
                "timestamp": dt.isoformat() if isinstance(dt, datetime) else str(dt),
                "_dt": dt if isinstance(dt, datetime) else datetime.min,
                "details": {
                    "topic_id": r["topic_id"],
                    "topic_title": r["topic_title"],
                    "learning_state": r["learning_state"],
                }
            })

        # B. Quiz attempts
        qa_res = await session.execute(
            text("""
                SELECT qa.id, q.title as quiz_title, qa.score, qa.attempted_at
                FROM assessments_quizattempt qa
                JOIN assessments_quiz q ON qa.quiz_id = q.id
                WHERE q.classroom_id = :cid AND qa.student_id = :uid
            """),
            {"cid": classroom_id, "uid": target_user_id}
        )
        for r in qa_res.mappings():
            dt = r["attempted_at"]
            events.append({
                "type": "QUIZ_ATTEMPT",
                "timestamp": dt.isoformat() if isinstance(dt, datetime) else str(dt),
                "_dt": dt if isinstance(dt, datetime) else datetime.min,
                "details": {
                    "attempt_id": r["id"],
                    "quiz_title": r["quiz_title"],
                    "score": r["score"],
                }
            })

        # C. Assignment Submissions
        sub_res = await session.execute(
            text("""
                SELECT s.id, a.title as assignment_title, s.grade, s.submitted_at
                FROM assessments_submission s
                JOIN assessments_assignment a ON s.assignment_id = a.id
                WHERE a.classroom_id = :cid AND s.student_id = :uid
            """),
            {"cid": classroom_id, "uid": target_user_id}
        )
        for r in sub_res.mappings():
            dt = r["submitted_at"]
            events.append({
                "type": "ASSIGNMENT_SUBMISSION",
                "timestamp": dt.isoformat() if isinstance(dt, datetime) else str(dt),
                "_dt": dt if isinstance(dt, datetime) else datetime.min,
                "details": {
                    "submission_id": r["id"],
                    "assignment_title": r["assignment_title"],
                    "grade": r["grade"],
                }
            })

        # D. Doubts Posted
        d_res = await session.execute(
            text("""
                SELECT id, title, is_resolved, created_at
                FROM doubts_doubt
                WHERE classroom_id = :cid AND author_id = :uid
            """),
            {"cid": classroom_id, "uid": target_user_id}
        )
        for r in d_res.mappings():
            dt = r["created_at"]
            events.append({
                "type": "DOUBT_POSTED",
                "timestamp": dt.isoformat() if isinstance(dt, datetime) else str(dt),
                "_dt": dt if isinstance(dt, datetime) else datetime.min,
                "details": {
                    "doubt_id": r["id"],
                    "title": r["title"],
                    "is_resolved": r["is_resolved"],
                }
            })

        # E. Doubt Replies Posted
        dr_res = await session.execute(
            text("""
                SELECT dr.id, dr.doubt_id, dr.is_accepted_answer, dr.created_at, d.title as doubt_title
                FROM doubts_doubtreply dr
                JOIN doubts_doubt d ON dr.doubt_id = d.id
                WHERE d.classroom_id = :cid AND dr.author_id = :uid
            """),
            {"cid": classroom_id, "uid": target_user_id}
        )
        for r in dr_res.mappings():
            dt = r["created_at"]
            events.append({
                "type": "DOUBT_REPLY",
                "timestamp": dt.isoformat() if isinstance(dt, datetime) else str(dt),
                "_dt": dt if isinstance(dt, datetime) else datetime.min,
                "details": {
                    "reply_id": r["id"],
                    "doubt_id": r["doubt_id"],
                    "doubt_title": r["doubt_title"],
                    "is_accepted_answer": r["is_accepted_answer"],
                }
            })

    # Sort descending by datetime
    events.sort(key=lambda x: x["_dt"], reverse=True)
    for e in events:
        e.pop("_dt", None)

    return {
        "classroom_id": classroom_id,
        "student_id": target_user_id,
        "total_activities": len(events),
        "timeline": events,
    }
