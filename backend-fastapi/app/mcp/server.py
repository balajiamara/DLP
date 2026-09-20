"""
MCP Server Resources Definition

Exposes Daily Learning Planner classroom and student data as standard Model Context Protocol resources:
1. classroom://{classroom_id}/overview
2. classroom://{classroom_id}/syllabus
3. classroom://{classroom_id}/progress (requesting student's own progress)
4. classroom://{classroom_id}/students/{user_id}/progress (teacher querying student progress)
5. classroom://{classroom_id}/history (requesting student's own learning history)
6. classroom://{classroom_id}/students/{user_id}/history (teacher querying student history)

All endpoints enforce strict active classroom membership and privacy boundaries via Context.
"""

import json
import logging
from mcp.server.mcpserver import MCPServer, Context
from mcp.server.mcpserver.exceptions import ResourceError, ResourceNotFoundError

from app.mcp.auth import extract_user_id_from_context
from app.services.mcp_resource_service import (
    get_classroom_overview_resource,
    get_classroom_syllabus_resource,
    get_student_progress_resource,
    get_learning_history_resource,
    MCPAuthorizationError,
    MCPNotFoundError,
)

logger = logging.getLogger(__name__)

mcp_server = MCPServer("DLP MCP Server")


@mcp_server.resource(
    "classroom://{classroom_id}/overview",
    name="Classroom Overview",
    description="Provides general information about a classroom, including teacher details and active student enrollment count.",
    mime_type="application/json",
)
async def classroom_overview(classroom_id: str, ctx: Context) -> str:
    """Reads classroom overview resource."""
    try:
        user_id = extract_user_id_from_context(ctx)
        data = await get_classroom_overview_resource(user_id=user_id, classroom_id=int(classroom_id))
        return json.dumps(data, indent=2)
    except MCPAuthorizationError as e:
        logger.warning(f"MCP Authorization rejected on classroom://{classroom_id}/overview: {e}")
        raise ResourceError(str(e))
    except MCPNotFoundError as e:
        logger.warning(f"MCP Resource not found on classroom://{classroom_id}/overview: {e}")
        raise ResourceNotFoundError(str(e))


@mcp_server.resource(
    "classroom://{classroom_id}/syllabus",
    name="Classroom Syllabus",
    description="Provides the hierarchical course syllabus (courses -> modules -> topics -> materials & resources) for a classroom.",
    mime_type="application/json",
)
async def classroom_syllabus(classroom_id: str, ctx: Context) -> str:
    """Reads classroom course syllabus resource."""
    try:
        user_id = extract_user_id_from_context(ctx)
        data = await get_classroom_syllabus_resource(user_id=user_id, classroom_id=int(classroom_id))
        return json.dumps(data, indent=2)
    except MCPAuthorizationError as e:
        logger.warning(f"MCP Authorization rejected on classroom://{classroom_id}/syllabus: {e}")
        raise ResourceError(str(e))
    except MCPNotFoundError as e:
        logger.warning(f"MCP Resource not found on classroom://{classroom_id}/syllabus: {e}")
        raise ResourceNotFoundError(str(e))


@mcp_server.resource(
    "classroom://{classroom_id}/progress",
    name="My Student Progress",
    description="Provides the calling student's learning progress across topics, quiz attempts, assignment submissions, and completion rates.",
    mime_type="application/json",
)
async def my_student_progress(classroom_id: str, ctx: Context) -> str:
    """Reads calling student's own progress in the classroom."""
    try:
        user_id = extract_user_id_from_context(ctx)
        data = await get_student_progress_resource(
            requesting_user_id=user_id,
            classroom_id=int(classroom_id),
            target_user_id=user_id,
        )
        return json.dumps(data, indent=2)
    except MCPAuthorizationError as e:
        logger.warning(f"MCP Authorization rejected on classroom://{classroom_id}/progress: {e}")
        raise ResourceError(str(e))
    except MCPNotFoundError as e:
        logger.warning(f"MCP Resource not found on classroom://{classroom_id}/progress: {e}")
        raise ResourceNotFoundError(str(e))


@mcp_server.resource(
    "classroom://{classroom_id}/students/{user_id}/progress",
    name="Student Progress By ID",
    description="Allows a classroom teacher to view a specific student's learning progress, quiz attempts, and completion rates.",
    mime_type="application/json",
)
async def student_progress_by_id(classroom_id: str, user_id: str, ctx: Context) -> str:
    """Reads specific student's progress in the classroom (teacher or self)."""
    try:
        req_uid = extract_user_id_from_context(ctx)
        data = await get_student_progress_resource(
            requesting_user_id=req_uid,
            classroom_id=int(classroom_id),
            target_user_id=int(user_id),
        )
        return json.dumps(data, indent=2)
    except MCPAuthorizationError as e:
        logger.warning(f"MCP Authorization rejected on student progress: {e}")
        raise ResourceError(str(e))
    except MCPNotFoundError as e:
        logger.warning(f"MCP Resource not found on student progress: {e}")
        raise ResourceNotFoundError(str(e))


@mcp_server.resource(
    "classroom://{classroom_id}/history",
    name="My Learning History",
    description="Provides the calling student's chronological learning history timeline (progress updates, quiz attempts, submissions, doubts).",
    mime_type="application/json",
)
async def my_learning_history(classroom_id: str, ctx: Context) -> str:
    """Reads calling student's own learning history timeline."""
    try:
        user_id = extract_user_id_from_context(ctx)
        data = await get_learning_history_resource(
            requesting_user_id=user_id,
            classroom_id=int(classroom_id),
            target_user_id=user_id,
        )
        return json.dumps(data, indent=2)
    except MCPAuthorizationError as e:
        logger.warning(f"MCP Authorization rejected on classroom://{classroom_id}/history: {e}")
        raise ResourceError(str(e))
    except MCPNotFoundError as e:
        logger.warning(f"MCP Resource not found on classroom://{classroom_id}/history: {e}")
        raise ResourceNotFoundError(str(e))


@mcp_server.resource(
    "classroom://{classroom_id}/students/{user_id}/history",
    name="Student Learning History By ID",
    description="Allows a classroom teacher to view a specific student's chronological learning history timeline.",
    mime_type="application/json",
)
async def student_learning_history_by_id(classroom_id: str, user_id: str, ctx: Context) -> str:
    """Reads specific student's learning history timeline (teacher or self)."""
    try:
        req_uid = extract_user_id_from_context(ctx)
        data = await get_learning_history_resource(
            requesting_user_id=req_uid,
            classroom_id=int(classroom_id),
            target_user_id=int(user_id),
        )
        return json.dumps(data, indent=2)
    except MCPAuthorizationError as e:
        logger.warning(f"MCP Authorization rejected on student history: {e}")
        raise ResourceError(str(e))
    except MCPNotFoundError as e:
        logger.warning(f"MCP Resource not found on student history: {e}")
        raise ResourceNotFoundError(str(e))


# ============================================================================
#                               MCP TOOLS
# ============================================================================

from mcp.server.mcpserver.exceptions import ToolError
from typing import Optional
from app.services.mcp_tool_service import (
    get_student_progress_data,
    get_pending_tasks_data,
    search_course_material_data,
    get_weak_topics_data,
    recommend_next_topic_data,
    ERR_ACCESS_DENIED_CLASSROOM,
)


@mcp_server.tool(
    name="get_student_progress",
    description="Retrieves topic progress, quiz scores, and completion percentage for a student in a classroom.",
)
async def get_student_progress(
    classroom_id: int,
    target_user_id: Optional[int] = None,
    ctx: Context = None,
) -> dict:
    """Retrieves student progress in a classroom. Defaults to caller; teachers can query any student."""
    try:
        user_id = extract_user_id_from_context(ctx)
        return await get_student_progress_data(
            caller_user_id=user_id,
            classroom_id=classroom_id,
            target_user_id=target_user_id,
        )
    except (MCPAuthorizationError, MCPNotFoundError) as e:
        logger.warning(f"Tool get_student_progress authorization/not-found error: {e}")
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Unexpected error in get_student_progress: {e}", exc_info=True)
        raise ToolError("An unexpected error occurred while fetching student progress.")


@mcp_server.tool(
    name="get_pending_tasks",
    description="Retrieves unsubmitted assignments and unattempted quizzes for the calling student in a classroom.",
)
async def get_pending_tasks(
    classroom_id: int,
    ctx: Context = None,
) -> dict:
    """Retrieves pending assignments (with due dates/overdue status) and quizzes for the calling student."""
    try:
        user_id = extract_user_id_from_context(ctx)
        return await get_pending_tasks_data(
            caller_user_id=user_id,
            classroom_id=classroom_id,
        )
    except (MCPAuthorizationError, MCPNotFoundError) as e:
        logger.warning(f"Tool get_pending_tasks authorization/not-found error: {e}")
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Unexpected error in get_pending_tasks: {e}", exc_info=True)
        raise ToolError("An unexpected error occurred while fetching pending tasks.")


@mcp_server.tool(
    name="search_course_material",
    description="Searches classroom materials using semantic vector retrieval and returns relevant chunks with similarity scores.",
)
async def search_course_material(
    classroom_id: int,
    query: str,
    ctx: Context = None,
) -> dict:
    """Searches course materials for a classroom using Step 33 RAG vector retrieval."""
    try:
        user_id = extract_user_id_from_context(ctx)
        return await search_course_material_data(
            caller_user_id=user_id,
            classroom_id=classroom_id,
            query=query,
        )
    except (MCPAuthorizationError, MCPNotFoundError) as e:
        logger.warning(f"Tool search_course_material authorization/not-found error: {e}")
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Unexpected error in search_course_material: {e}", exc_info=True)
        raise ToolError("An unexpected error occurred while searching course materials.")


@mcp_server.tool(
    name="get_weak_topics",
    description="Identifies syllabus topics where the student requires review based on REVIEW_REQUIRED state or low quiz scores (<70%).",
)
async def get_weak_topics(
    classroom_id: int,
    target_user_id: Optional[int] = None,
    ctx: Context = None,
) -> dict:
    """Identifies topics needing review for self or a student (if caller is teacher)."""
    try:
        user_id = extract_user_id_from_context(ctx)
        return await get_weak_topics_data(
            caller_user_id=user_id,
            classroom_id=classroom_id,
            target_user_id=target_user_id,
        )
    except (MCPAuthorizationError, MCPNotFoundError) as e:
        logger.warning(f"Tool get_weak_topics authorization/not-found error: {e}")
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Unexpected error in get_weak_topics: {e}", exc_info=True)
        raise ToolError("An unexpected error occurred while identifying weak topics.")


@mcp_server.tool(
    name="recommend_next_topic",
    description="Recommends the next topic for study with explainable reasoning, prioritizing weak topics then sequential syllabus progression.",
)
async def recommend_next_topic(
    classroom_id: int,
    target_user_id: Optional[int] = None,
    ctx: Context = None,
) -> dict:
    """Recommends next study topic with explicit reasoning string."""
    try:
        user_id = extract_user_id_from_context(ctx)
        return await recommend_next_topic_data(
            caller_user_id=user_id,
            classroom_id=classroom_id,
            target_user_id=target_user_id,
        )
    except (MCPAuthorizationError, MCPNotFoundError) as e:
        logger.warning(f"Tool recommend_next_topic authorization/not-found error: {e}")
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Unexpected error in recommend_next_topic: {e}", exc_info=True)
        raise ToolError("An unexpected error occurred while generating topic recommendation.")
