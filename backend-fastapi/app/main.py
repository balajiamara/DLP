from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
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


@app.get("/")
async def root():
    """Root sanity check endpoint."""
    return {
        "service": "daily-learning-planner-fastapi",
        "status": "running",
    }
