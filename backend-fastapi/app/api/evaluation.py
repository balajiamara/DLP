"""
Evaluation API Router (Step 42)

Exposes endpoints for user feedback collection and internal evaluation summaries:
- POST /evaluation/feedback
- GET /evaluation/summary

Security:
- Gated by X-Internal-Secret server-to-server header
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.evaluation_logging import record_feedback, get_evaluation_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


def _verify_internal_secret(x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret")) -> None:
    secret = settings.INTERNAL_SERVICE_SECRET
    if not secret or not x_internal_secret or x_internal_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid X-Internal-Secret header.",
        )


class FeedbackRequest(BaseModel):
    log_id: uuid.UUID = Field(..., description="UUID of the interaction log row to rate")
    rating: Literal["up", "down"] = Field(..., description="User rating: 'up' or 'down'")
    reason: Optional[str] = Field(None, description="Optional textual feedback or rationale")


class FeedbackResponse(BaseModel):
    status: str
    log_id: uuid.UUID
    rating: str


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Record AI Interaction Feedback",
)
async def feedback_endpoint(
    payload: FeedbackRequest,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    _verify_internal_secret(x_internal_secret)

    updated = await record_feedback(
        log_id=payload.log_id,
        rating=payload.rating,
        reason=payload.reason,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interaction log with id {payload.log_id} not found.",
        )

    return FeedbackResponse(
        status="success",
        log_id=payload.log_id,
        rating=payload.rating,
    )


@router.get(
    "/summary",
    status_code=status.HTTP_200_OK,
    summary="Retrieve AI Evaluation Summary Metrics",
)
async def summary_endpoint(
    classroom_id: Optional[int] = Query(None, description="Optional classroom filter"),
    start_date: Optional[datetime] = Query(None, description="Optional start timestamp (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Optional end timestamp (ISO format)"),
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    _verify_internal_secret(x_internal_secret)

    return await get_evaluation_summary(
        classroom_id=classroom_id,
        start_date=start_date,
        end_date=end_date,
    )
