"""
AI Content Generation API Router (Step 40)

Exposes endpoints for generating quiz and study-plan drafts under the
review-before-save gate:
- POST /content/generate-quiz
- POST /content/generate-study-plan

Security:
- Gated by X-Internal-Secret server-to-server header
- Gated by classroom-scoped authorization checks
"""

import logging
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, status

from app.core.config import settings
from app.schemas.content_generation import (
    GenerateQuizRequest,
    GenerateStudyPlanRequest,
    GeneratedDraftResponse,
)
from app.services.content_generation import (
    generate_quiz_draft,
    generate_study_plan_draft,
    ContentGenerationError,
)
from app.services.rag_retrieval import NotAuthorizedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["content-generation"])


def _verify_internal_secret(x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret")) -> None:
    """Validates that the incoming request contains a matching X-Internal-Secret header."""
    secret = settings.INTERNAL_SERVICE_SECRET
    if not secret or not x_internal_secret or x_internal_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid X-Internal-Secret header.",
        )


@router.post(
    "/generate-quiz",
    response_model=GeneratedDraftResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Grounded Quiz Draft",
    description="Generates an AI quiz grounded in classroom material and saves it as a draft for teacher review.",
)
async def generate_quiz_endpoint(
    request_data: GenerateQuizRequest,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    _verify_internal_secret(x_internal_secret)

    try:
        draft = await generate_quiz_draft(
            classroom_id=request_data.classroom_id,
            topic_id=request_data.topic_id,
            teacher_user_id=request_data.teacher_user_id,
            num_questions=request_data.num_questions,
        )
        return draft
    except NotAuthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied or classroom not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ContentGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Content generation failed: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in generate_quiz_endpoint: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {exc}",
        ) from exc


@router.post(
    "/generate-study-plan",
    response_model=GeneratedDraftResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Grounded Study Plan Draft",
    description="Generates an AI study plan tailored to student progress and saves it as a draft for review.",
)
async def generate_study_plan_endpoint(
    request_data: GenerateStudyPlanRequest,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    _verify_internal_secret(x_internal_secret)

    try:
        draft = await generate_study_plan_draft(
            classroom_id=request_data.classroom_id,
            student_user_id=request_data.student_user_id,
            requesting_user_id=request_data.requesting_user_id,
            goal_description=request_data.goal_description,
            deadline=request_data.deadline,
        )
        return draft
    except NotAuthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied or classroom not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ContentGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Content generation failed: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in generate_study_plan_endpoint: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {exc}",
        ) from exc
