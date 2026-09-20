"""
Chat API Router

Provides Course-Grounded RAG chat (`POST /chat/course`) and General Learning Mode chat (`POST /chat/general`) endpoints.
Gated by internal secret authorization and pre-search classroom membership checks.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.course_chat import answer_course_question, stream_course_question
from app.services.general_chat import answer_general_question, stream_general_question
from app.services.rag_retrieval import is_authorized_for_classroom, NotAuthorizedError
from app.services.chat_client import GeminiChatError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class CourseChatRequest(BaseModel):
    student_user_id: int = Field(..., description="ID of the student or teacher user making the query")
    classroom_id: int = Field(..., description="ID of the target classroom scope")
    topic_id: Optional[int] = Field(default=None, description="Optional topic ID filter within classroom")
    query: str = Field(..., min_length=1, description="Question string to be answered")
    socratic_mode: bool = Field(default=False, description="When true, responds with a guiding question/hint rather than direct answer")


class GeneralChatRequest(BaseModel):
    student_user_id: int = Field(..., description="ID of the student or teacher user making the query")
    classroom_id: int = Field(..., description="ID of the target classroom scope for authorization")
    query: str = Field(..., min_length=1, description="Question string to be answered")
    socratic_mode: bool = Field(default=False, description="When true, responds with a guiding question/hint rather than direct answer")


class SourceItem(BaseModel):
    material_title: str
    material_id: int
    chunk_index: int


class ChatResponse(BaseModel):
    answer: str
    grounded: bool
    sources: list[SourceItem]


# Alias for backward compatibility
CourseChatResponse = ChatResponse


def _verify_internal_secret(x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret")) -> None:
    """Validates that the incoming request contains a matching X-Internal-Secret header."""
    secret = settings.INTERNAL_SERVICE_SECRET
    if not secret or not x_internal_secret or x_internal_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid X-Internal-Secret header.",
        )


@router.post(
    "/course",
    status_code=status.HTTP_200_OK,
    response_model=ChatResponse,
    summary="Course-Grounded RAG Chat Endpoint",
)
async def course_chat_endpoint(
    request: CourseChatRequest,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    """
    Answers a user question grounded in classroom materials.

    - Verifies user authorization in classroom before retrieval.
    - Short-circuits with fallback if no relevant materials meet distance threshold.
    - Generates cited response using Gemini 3.6 Flash.
    """
    _verify_internal_secret(x_internal_secret)

    try:
        result = await answer_course_question(
            user_id=request.student_user_id,
            classroom_id=request.classroom_id,
            topic_id=request.topic_id,
            query=request.query,
            socratic_mode=request.socratic_mode,
        )
        return result

    except NotAuthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied or classroom not found.",
        )
    except GeminiChatError as e:
        logger.error(f"Gemini Chat service error in /chat/course: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat generation failed: {e}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in course chat endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing course chat request: {e}",
        )


@router.post(
    "/general",
    status_code=status.HTTP_200_OK,
    response_model=ChatResponse,
    summary="General Learning Mode Chat Endpoint",
)
async def general_chat_endpoint(
    request: GeneralChatRequest,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    """
    Answers a general-knowledge question using Gemini 3.6 Flash.

    - Verifies user authorization in classroom before answering.
    - Does NOT perform vector retrieval or grounding in classroom materials.
    - Always returns grounded=False and sources=[].
    """
    _verify_internal_secret(x_internal_secret)

    try:
        result = await answer_general_question(
            user_id=request.student_user_id,
            classroom_id=request.classroom_id,
            query=request.query,
            socratic_mode=request.socratic_mode,
        )
        return result


    except NotAuthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied or classroom not found.",
        )
    except GeminiChatError as e:
        logger.error(f"Gemini Chat service error in /chat/general: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat generation failed: {e}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in general chat endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing general chat request: {e}",
        )


@router.post(
    "/course/stream",
    summary="Course-Grounded RAG Chat Streaming Endpoint (SSE)",
)
async def course_chat_stream_endpoint(
    request: CourseChatRequest,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    """
    Answers a user question grounded in classroom materials, streaming tokens via SSE.
    Pre-authorizes the user against classroom membership BEFORE returning the stream.
    """
    _verify_internal_secret(x_internal_secret)

    # Pre-search classroom authorization check BEFORE opening stream
    authorized = await is_authorized_for_classroom(request.student_user_id, request.classroom_id)
    if not authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied or classroom not found.",
        )

    return StreamingResponse(
        stream_course_question(
            user_id=request.student_user_id,
            classroom_id=request.classroom_id,
            topic_id=request.topic_id,
            query=request.query,
            socratic_mode=request.socratic_mode,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/general/stream",
    summary="General Learning Mode Chat Streaming Endpoint (SSE)",
)
async def general_chat_stream_endpoint(
    request: GeneralChatRequest,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    """
    Answers a general-knowledge question, streaming tokens via SSE.
    Pre-authorizes the user against classroom membership BEFORE returning the stream.
    """
    _verify_internal_secret(x_internal_secret)

    # Pre-search classroom authorization check BEFORE opening stream
    authorized = await is_authorized_for_classroom(request.student_user_id, request.classroom_id)
    if not authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied or classroom not found.",
        )

    return StreamingResponse(
        stream_general_question(
            user_id=request.student_user_id,
            classroom_id=request.classroom_id,
            query=request.query,
            socratic_mode=request.socratic_mode,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

