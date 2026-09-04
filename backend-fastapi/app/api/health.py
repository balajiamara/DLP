import asyncio
import logging
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def health_live():
    """
    Liveness probe: verifies that the FastAPI process is running.
    Does not perform any DB calls. Used by Render health check.
    """
    return {"status": "ok"}


@router.get("/ready")
async def health_ready(response: Response, db: AsyncSession = Depends(get_db)):
    """
    Readiness probe: executes SELECT 1 query against Supabase database with a 3s timeout.
    Returns 200 on success, 503 on database failure or timeout.
    """
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=3.0)
        return {"status": "ok", "database": "connected"}
    except asyncio.TimeoutError:
        logger.error("Health readiness check timed out after 3.0 seconds")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "error",
            "database": "disconnected",
            "detail": "Database ping operation timed out",
        }
    except Exception as exc:
        logger.error(f"Health readiness check database error: {exc}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "error",
            "database": "disconnected",
            "detail": "Database connection unavailable",
        }
