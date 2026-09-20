import asyncio
import os
import time
import json
import jwt
import uvicorn
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp, Scope, Receive, Send
from mcp.server.mcpserver import MCPServer, Context
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

JWT_SECRET = "test-jwt-secret-key-123"

# Global session mapping: session_id -> user_id
session_user_map: dict[str, int] = {}

mcp_server = MCPServer("DLP MCP Server")

def extract_user_id_from_context(ctx: Context) -> int:
    """
    Extracts authenticated user_id from MCP Context.
    1. Primary: Extract from Authorization header on the incoming POST message request.
    2. Fallback: Extract from session_user_map via session_id query param (from GET /sse).
    """
    req: Request = ctx.request_context.request
    
    # 1. Primary: Header check
    auth_header = req.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            uid = int(payload.get("user_id"))
            return uid
        except Exception:
            pass

    # 2. Fallback: Session map check
    session_id = req.query_params.get("session_id")
    if session_id and session_id in session_user_map:
        return session_user_map[session_id]

    raise PermissionError("Unauthenticated MCP request: No valid JWT or session found.")

@mcp_server.resource("classroom://{classroom_id}/overview")
async def get_overview(classroom_id: str, ctx: Context) -> str:
    user_id = extract_user_id_from_context(ctx)
    print(f"\n[RESOURCE HANDLER EXECUTED]")
    print(f"  classroom_id: {classroom_id}")
    print(f"  RESOLVED user_id: {user_id}")
    return f"Overview for classroom {classroom_id} for user {user_id}"

class MCPSessionAuthMiddleware:
    """
    ASGI middleware that:
    1. For GET /mcp/sse?token=<jwt>:
       Captures the session_id emitted by SseServerTransport in the 'endpoint' SSE event,
       and maps session_user_map[session_id] = user_id.
    2. For POST /mcp/messages/?session_id=...:
       If Authorization header present, validates JWT.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            query_string = scope.get("query_string", b"").decode("utf-8")
            
            # Check for token in query params on SSE connect
            user_id = None
            if "token=" in query_string:
                for part in query_string.split("&"):
                    if part.startswith("token="):
                        raw_token = part.split("=", 1)[1]
                        try:
                            payload = jwt.decode(raw_token, JWT_SECRET, algorithms=["HS256"])
                            user_id = int(payload.get("user_id"))
                        except Exception as e:
                            print(f"[AUTH ERROR] Invalid token on SSE connect: {e}")

            if user_id is not None and path.endswith("/sse"):
                # Intercept send to catch the session_id in the endpoint event
                async def intercept_send(message):
                    if message.get("type") == "http.response.body":
                        body = message.get("body", b"").decode("utf-8", errors="ignore")
                        # e.g., event: endpoint\ndata: /mcp/messages/?session_id=3b9a58bf7cd9407aa085b1d5a9b6ed0b\n\n
                        if "session_id=" in body:
                            idx = body.find("session_id=") + len("session_id=")
                            sid = body[idx:].splitlines()[0].split("&")[0].strip()
                            session_user_map[sid] = user_id
                            print(f" [SESSION MAP REGISTERED] session_id={sid} -> user_id={user_id}")
                    await send(message)

                await self.app(scope, receive, intercept_send)
                return

        await self.app(scope, receive, send)

app = FastAPI()
app.add_middleware(MCPSessionAuthMiddleware)
app.mount("/mcp", mcp_server.sse_app())

async def run_test():
    config = uvicorn.Config(app, host="127.0.0.1", port=8009, log_level="error")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    await asyncio.sleep(1.0)
    
    # Generate tokens
    token_user_10 = jwt.encode({"user_id": 10, "token_type": "access", "exp": int(time.time()) + 3600}, JWT_SECRET, algorithm="HS256")
    token_user_20 = jwt.encode({"user_id": 20, "token_type": "access", "exp": int(time.time()) + 3600}, JWT_SECRET, algorithm="HS256")

    print("\n=======================================================")
    print(" TEST 1: Client using Authorization Header (User 10)  ")
    print("=======================================================")
    headers = {"Authorization": f"Bearer {token_user_10}"}
    async with sse_client("http://127.0.0.1:8009/mcp/sse", headers=headers) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            res1 = await session.read_resource("classroom://1/overview")
            print("Client received:", res1)
            assert "user 10" in res1.contents[0].text
            print(" [PASS] User 10 verified via Authorization Header!")

    print("\n=======================================================")
    print(" TEST 2: Client using ?token=<jwt> on SSE (User 20)   ")
    print("=======================================================")
    async with sse_client(f"http://127.0.0.1:8009/mcp/sse?token={token_user_20}") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            res2 = await session.read_resource("classroom://2/overview")
            print("Client received:", res2)
            assert "user 20" in res2.contents[0].text
            print(" [PASS] User 20 verified via session_user_map fallback!")

    print("\n=======================================================")
    print(" ALL MCP REAL HTTP ROUNDTRIP IDENTITY TESTS PASSED!    ")
    print("=======================================================")

    server.should_exit = True
    await server_task

if __name__ == "__main__":
    asyncio.run(run_test())
