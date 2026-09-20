import time
import json
import jwt
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.requests import Request
from starlette.datastructures import Headers, QueryParams

from app.core.config import settings
from app.mcp.server import mcp_server
from app.mcp.auth import (
    extract_user_id_from_context,
    session_user_map,
    MCPSessionAuthMiddleware,
)
from app.services.mcp_resource_service import (
    get_classroom_overview_resource,
    get_classroom_syllabus_resource,
    get_student_progress_resource,
    get_learning_history_resource,
    is_teacher_for_classroom,
    MCPAuthorizationError,
    MCPNotFoundError,
)


@pytest.mark.asyncio
async def test_mcp_resource_templates_registered():
    """Confirms all 6 resource templates are registered in MCPServer."""
    templates = await mcp_server.list_resource_templates()
    uri_templates = [t.uri_template for t in templates]
    
    assert "classroom://{classroom_id}/overview" in uri_templates
    assert "classroom://{classroom_id}/syllabus" in uri_templates
    assert "classroom://{classroom_id}/progress" in uri_templates
    assert "classroom://{classroom_id}/students/{user_id}/progress" in uri_templates
    assert "classroom://{classroom_id}/history" in uri_templates
    assert "classroom://{classroom_id}/students/{user_id}/history" in uri_templates


def test_extract_user_id_from_context_header_success():
    """Verifies user_id extraction via Authorization Bearer header on incoming request."""
    token = jwt.encode(
        {"user_id": 55, "token_type": "access", "exp": int(time.time()) + 3600},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256"
    )
    mock_request = MagicMock(spec=Request)
    mock_request.headers = Headers({"authorization": f"Bearer {token}"})
    mock_request.query_params = QueryParams({})

    mock_ctx = MagicMock()
    mock_ctx.request_context.request = mock_request

    uid = extract_user_id_from_context(mock_ctx)
    assert uid == 55


def test_extract_user_id_from_context_header_expired():
    """Verifies expired token in header raises MCPAuthorizationError."""
    token = jwt.encode(
        {"user_id": 55, "token_type": "access", "exp": int(time.time()) - 100},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256"
    )
    mock_request = MagicMock(spec=Request)
    mock_request.headers = Headers({"authorization": f"Bearer {token}"})
    mock_request.query_params = QueryParams({})

    mock_ctx = MagicMock()
    mock_ctx.request_context.request = mock_request

    with pytest.raises(MCPAuthorizationError, match="expired"):
        extract_user_id_from_context(mock_ctx)


def test_extract_user_id_from_context_invalid_token_type():
    """Verifies refresh token in header is rejected."""
    token = jwt.encode(
        {"user_id": 55, "token_type": "refresh", "exp": int(time.time()) + 3600},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256"
    )
    mock_request = MagicMock(spec=Request)
    mock_request.headers = Headers({"authorization": f"Bearer {token}"})
    mock_request.query_params = QueryParams({})

    mock_ctx = MagicMock()
    mock_ctx.request_context.request = mock_request

    with pytest.raises(MCPAuthorizationError, match="Invalid token type"):
        extract_user_id_from_context(mock_ctx)


def test_extract_user_id_from_context_session_map_success():
    """Verifies fallback user_id lookup from session_user_map via session_id."""
    sid = "test-session-uuid-123"
    session_user_map[sid] = (77, time.time() + 3600)

    try:
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({})
        mock_request.query_params = QueryParams({"session_id": sid})

        mock_ctx = MagicMock()
        mock_ctx.request_context.request = mock_request

        uid = extract_user_id_from_context(mock_ctx)
        assert uid == 77
    finally:
        session_user_map.pop(sid, None)


def test_extract_user_id_from_context_session_map_expired():
    """Verifies expired session in session_user_map is purged and raises error."""
    sid = "test-session-uuid-expired"
    session_user_map[sid] = (77, time.time() - 10)

    mock_request = MagicMock(spec=Request)
    mock_request.headers = Headers({})
    mock_request.query_params = QueryParams({"session_id": sid})

    mock_ctx = MagicMock()
    mock_ctx.request_context.request = mock_request

    with pytest.raises(MCPAuthorizationError, match="expired"):
        extract_user_id_from_context(mock_ctx)

    assert sid not in session_user_map


@pytest.mark.asyncio
@patch("app.services.mcp_resource_service.is_authorized_for_classroom", new_callable=AsyncMock)
async def test_classroom_overview_unauthorized(mock_is_auth):
    """Verifies non-member access to classroom overview is rejected with MCPAuthorizationError."""
    mock_is_auth.return_value = False

    with pytest.raises(MCPAuthorizationError, match="not an active member"):
        await get_classroom_overview_resource(user_id=99, classroom_id=1)


@pytest.mark.asyncio
@patch("app.services.mcp_resource_service.is_authorized_for_classroom", new_callable=AsyncMock)
async def test_student_progress_cross_student_forbidden(mock_is_auth):
    """Verifies a student cannot view another student's progress if not a teacher."""
    mock_is_auth.return_value = True

    with patch("app.services.mcp_resource_service.is_teacher_for_classroom", new_callable=AsyncMock) as mock_teacher:
        mock_teacher.return_value = False

        with pytest.raises(MCPAuthorizationError, match="not permitted to view progress"):
            await get_student_progress_resource(requesting_user_id=3, classroom_id=1, target_user_id=4)


@pytest.mark.asyncio
@patch("app.services.mcp_resource_service.is_authorized_for_classroom", new_callable=AsyncMock)
async def test_learning_history_cross_student_forbidden(mock_is_auth):
    """Verifies a student cannot view another student's learning history if not a teacher."""
    mock_is_auth.return_value = True

    with patch("app.services.mcp_resource_service.is_teacher_for_classroom", new_callable=AsyncMock) as mock_teacher:
        mock_teacher.return_value = False

        with pytest.raises(MCPAuthorizationError, match="not permitted to view learning history"):
            await get_learning_history_resource(requesting_user_id=3, classroom_id=1, target_user_id=4)


@pytest.mark.asyncio
async def test_session_cleanup_on_sse_disconnect():
    """Confirms MCPSessionAuthMiddleware cleans up session_user_map when the SSE stream disconnects."""
    token = jwt.encode(
        {"user_id": 999, "token_type": "access", "exp": int(time.time()) + 3600},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256"
    )
    
    test_sid = "test-cleanup-sid-999"
    
    async def fake_mcp_app(scope, receive, send):
        # Emit the endpoint line with session_id
        msg = {
            "type": "http.response.body",
            "body": f"event: endpoint\ndata: /mcp/messages/?session_id={test_sid}\n\n".encode("utf-8")
        }
        await send(msg)
        # Connection active: check that session was registered
        assert test_sid in session_user_map
        assert session_user_map[test_sid][0] == 999

    middleware = MCPSessionAuthMiddleware(fake_mcp_app)
    
    scope = {
        "type": "http",
        "path": "/mcp/sse",
        "query_string": f"token={token}".encode("utf-8"),
        "headers": []
    }
    
    sent_messages = []
    async def fake_send(msg):
        sent_messages.append(msg)
        
    await middleware(scope, None, fake_send)
    
    # Assert session was purged upon completion (disconnect)
    assert test_sid not in session_user_map


@pytest.mark.asyncio
@patch("app.services.mcp_resource_service.is_authorized_for_classroom", new_callable=AsyncMock)
async def test_student_progress_teacher_allowed(mock_is_auth):
    """Verifies a teacher CAN view any student's progress in their classroom."""
    mock_is_auth.return_value = True

    with patch("app.services.mcp_resource_service.is_teacher_for_classroom", new_callable=AsyncMock) as mock_teacher:
        mock_teacher.return_value = True

        with patch("app.services.mcp_resource_service.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            # Target user membership check returns True
            mock_mem_res = MagicMock()
            mock_mem_res.first.return_value = (1,)
            
            # Total topics count
            mock_topics_res = MagicMock()
            mock_topics_res.scalar.return_value = 5

            # Progress rows
            mock_prog_res = MagicMock()
            mock_prog_res.mappings.return_value = []

            # Quiz attempts
            mock_quiz_res = MagicMock()
            mock_quiz_res.mappings.return_value = []

            # Submissions
            mock_sub_res = MagicMock()
            mock_sub_res.mappings.return_value = []

            mock_session.execute.side_effect = [
                mock_mem_res,
                mock_topics_res,
                mock_prog_res,
                mock_quiz_res,
                mock_sub_res,
            ]

            res = await get_student_progress_resource(requesting_user_id=2, classroom_id=1, target_user_id=3)
            assert res["classroom_id"] == 1
            assert res["student_id"] == 3
            assert res["summary_stats"]["total_topics"] == 5


@pytest.mark.asyncio
@patch("app.mcp.server.extract_user_id_from_context")
@patch("app.mcp.server.get_classroom_overview_resource", new_callable=AsyncMock)
async def test_mcp_server_resource_overview_authorized(mock_get_overview, mock_extract_uid):
    """Verifies mcp_server.read_resource executes handler and returns JSON content."""
    from mcp.server.mcpserver import Context
    mock_extract_uid.return_value = 10
    mock_get_overview.return_value = {
        "id": 1,
        "name": "Maths",
        "description": "Calculus",
        "teacher": {"id": 2, "username": "tester", "email": "test@gmail.com"},
        "student_count": 5,
        "created_at": "2026-09-01T10:00:00Z"
    }

    mock_ctx = MagicMock(spec=Context)
    res = await mcp_server.read_resource("classroom://1/overview", context=mock_ctx)
    assert len(res) == 1
    content = json.loads(res[0].content)
    assert content["id"] == 1
    assert content["name"] == "Maths"
    assert content["student_count"] == 5
