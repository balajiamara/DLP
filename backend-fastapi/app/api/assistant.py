"""
Personalized Learning Assistant API Router

Provides the daily recommendation endpoint (`POST /assistant/daily-recommendation`).
Gated by internal secret authorization and pre-search classroom membership checks.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.personalized_assistant import get_daily_recommendation
from app.services.rag_retrieval import NotAuthorizedError
from app.services.chat_client import GeminiChatError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


class DailyRecommendationRequest(BaseModel):
    student_user_id: int = Field(..., description="ID of the student user requesting the recommendation")
    classroom_id: int = Field(..., description="ID of the target classroom scope")


class DailyRecommendationResponse(BaseModel):
    recommendation: str = Field(..., description="LLM-synthesized natural-language daily study recommendation")
    supporting_data: Dict[str, Any] = Field(..., description="Underlying raw data: progress, weak topics, tasks, and recommendation")


def _verify_internal_secret(x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret")) -> None:
    """Validates that the incoming request contains a matching X-Internal-Secret header."""
    secret = settings.INTERNAL_SERVICE_SECRET
    if not secret or not x_internal_secret or x_internal_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid X-Internal-Secret header.",
        )


@router.post(
    "/daily-recommendation",
    status_code=status.HTTP_200_OK,
    response_model=DailyRecommendationResponse,
    summary="Daily Personalized Study Recommendation Endpoint",
)
async def daily_recommendation_endpoint(
    request: DailyRecommendationRequest,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    """
    Synthesizes a personalized 'What should I study today?' recommendation.

    - Gated by X-Internal-Secret server-to-server auth.
    - Verifies student membership in target classroom (403 on failure).
    - Directly orchestrates progress, pending tasks, weak topics, and syllabus sequence.
    - Generates grounded advice using Gemini 3.6 Flash.
    """
    _verify_internal_secret(x_internal_secret)

    try:
        result = await get_daily_recommendation(
            user_id=request.student_user_id,
            classroom_id=request.classroom_id,
        )
        return DailyRecommendationResponse(**result)
    except NotAuthorizedError as e:
        logger.warning(
            f"Daily recommendation authorization failed: user {request.student_user_id} in classroom {request.classroom_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied or classroom not found",
        )
    except GeminiChatError as e:
        logger.error(f"Gemini API error during daily recommendation: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate recommendation via AI service.",
        )
    except Exception as e:
        logger.error(f"Unexpected error in daily recommendation endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while processing your daily recommendation.",
        )
