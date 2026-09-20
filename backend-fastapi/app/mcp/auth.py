"""
MCP Authentication & Session Lifecycle Middleware

Manages request-scoped identity and session lifecycle for MCP resources over HTTP/SSE.
Supports dual-path identity propagation:
1. Path A (Primary): Authorization Bearer header forwarded on POST /messages/.
2. Path B (Fallback): session_user_map fallback from initial GET /sse?token=<jwt>,
   with guaranteed cleanup in finally block on disconnect and active TTL validation.
"""

import time
import logging
import jwt
from typing import Dict, Tuple, Optional
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.requests import Request
from mcp.server.mcpserver import Context

from app.core.config import settings
from app.services.mcp_resource_service import MCPAuthorizationError

logger = logging.getLogger(__name__)

# Server-side active session store: session_id -> (user_id, exp_timestamp)
session_user_map: Dict[str, Tuple[int, float]] = {}


def extract_user_id_from_context(ctx: Context) -> int:
    """
    Extracts authenticated user_id from an MCP resource Context.

    1. Path A (Primary): Header inspection on the POST /messages/ request.
    2. Path B (Fallback): Session map lookup using ?session_id=<id> query parameter.

    Raises:
        MCPAuthorizationError if unauthenticated, token invalid, or session expired.
    """
    req: Request = ctx.request_context.request
    if req is None:
        raise MCPAuthorizationError("No active HTTP request context available.")

    # --- Path A: Authorization Header on POST request ---
    auth_header = req.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SIGNING_KEY,
                algorithms=["HS256"],
                options={"verify_exp": True},
            )
            token_type = payload.get("token_type")
            if token_type and token_type != "access":
                raise MCPAuthorizationError(f"Invalid token type '{token_type}', expected 'access'.")
            return int(payload["user_id"])
        except jwt.ExpiredSignatureError:
            raise MCPAuthorizationError("Authentication token has expired.")
        except jwt.PyJWTError as e:
            raise MCPAuthorizationError(f"Invalid JWT authentication: {e}")

    # --- Path B: Session Map Fallback via session_id query param ---
    session_id = req.query_params.get("session_id")
    if session_id and session_id in session_user_map:
        uid, exp = session_user_map[session_id]
        if time.time() > exp:
            session_user_map.pop(session_id, None)
            raise MCPAuthorizationError("MCP session token has expired.")
        return uid

    raise MCPAuthorizationError("Unauthenticated MCP request: Missing or invalid token.")


class MCPSessionAuthMiddleware:
    """
    ASGI middleware for MCP routes:
    1. Intercepts GET /sse to extract JWT from query param (?token=<jwt>) or Authorization header.
    2. Intercepts the generated session_id in the SSE endpoint priming event.
    3. Registers session_user_map[session_id] = (user_id, exp).
    4. Automatically purges session_id in finally block upon SSE client disconnection.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            query_string = scope.get("query_string", b"").decode("utf-8")

            # Extract token if connecting to SSE endpoint
            user_info: Optional[Tuple[int, float]] = None

            # Check query string (?token=...)
            if "token=" in query_string:
                for part in query_string.split("&"):
                    if part.startswith("token="):
                        raw_token = part.split("=", 1)[1]
                        user_info = self._verify_token(raw_token)
                        break

            # Check Authorization header if query token was not provided
            if not user_info:
                headers = dict(scope.get("headers", []))
                auth_header = headers.get(b"authorization", b"").decode("utf-8")
                if auth_header.startswith("Bearer "):
                    raw_token = auth_header.split(" ", 1)[1].strip()
                    user_info = self._verify_token(raw_token)

            # If this is an SSE connection with a verified user, intercept and track session
            if user_info is not None and (path.endswith("/sse") or "/sse" in path):
                user_id, exp = user_info
                captured_sid: Optional[str] = None

                async def intercept_send(message):
                    nonlocal captured_sid
                    if message.get("type") == "http.response.body":
                        body = message.get("body", b"").decode("utf-8", errors="ignore")
                        if "session_id=" in body:
                            try:
                                idx = body.find("session_id=") + len("session_id=")
                                sid = body[idx:].splitlines()[0].split("&")[0].strip()
                                captured_sid = sid
                                session_user_map[sid] = (user_id, exp)
                                logger.info(f"Registered MCP session {sid} for user {user_id}")
                            except Exception as e:
                                logger.warning(f"Failed to parse session_id from SSE endpoint event: {e}")
                    await send(message)

                try:
                    await self.app(scope, receive, intercept_send)
                finally:
                    if captured_sid:
                        session_user_map.pop(captured_sid, None)
                        logger.info(f"Cleaned up MCP session {captured_sid} on SSE disconnect")
                return

        await self.app(scope, receive, send)

    @staticmethod
    def _verify_token(token: str) -> Optional[Tuple[int, float]]:
        """Validates JWT access token and returns (user_id, exp) or None."""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SIGNING_KEY,
                algorithms=["HS256"],
                options={"verify_exp": True},
            )
            token_type = payload.get("token_type")
            if token_type and token_type != "access":
                return None
            user_id = int(payload["user_id"])
            exp = float(payload.get("exp", time.time() + 3600.0))
            return (user_id, exp)
        except Exception as e:
            logger.debug(f"MCP token verification failed: {e}")
            return None
