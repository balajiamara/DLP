import socket
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Force IPv4 resolution to prevent Windows IPv6 pooler connection drops on Supabase
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_getaddrinfo

from app.api.health import router as health_router
from app.api.materials import router as materials_router
from app.api.rag import router as rag_router
from app.api.chat import router as chat_router
from app.api.assistant import router as assistant_router
from app.api.websocket import router as websocket_router
from app.api.broadcast import router as broadcast_router
from app.api.content_generation import router as content_generation_router
from app.api.evaluation import router as evaluation_router
from app.mcp.server import mcp_server
from app.mcp.auth import MCPSessionAuthMiddleware
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Daily Learning Planner - FastAPI Service",
    description="Microservice for DLP vector search, AI capabilities, and async tasks",
    version="1.0.0",
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(health_router)
app.include_router(materials_router)
app.include_router(rag_router)
app.include_router(chat_router)
app.include_router(assistant_router)
app.include_router(websocket_router)
app.include_router(broadcast_router)
app.include_router(content_generation_router)
app.include_router(evaluation_router)



# Mount MCP Server over SSE
app.mount("/mcp", MCPSessionAuthMiddleware(mcp_server.sse_app()))


@app.get("/")
async def root():
    """Root sanity check endpoint."""
    return {
        "service": "daily-learning-planner-fastapi",
        "status": "running",
    }
