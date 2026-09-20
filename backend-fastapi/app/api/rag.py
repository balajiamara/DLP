"""
Internal RAG Retrieval Endpoints

NOTE / SECURITY NOTICE:
These endpoints are internal, server-to-server routes intended exclusively for call requests
from backend-django (or internal LLM pipeline orchestrators). They are NOT meant for direct public frontend or
user access. All endpoints are protected by the X-Internal-Secret header and perform classroom authorization checks.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Header, HTTPException, status
from app.core.config import settings
from app.services.rag_retrieval import retrieve_relevant_chunks, NotAuthorizedError

router = APIRouter(prefix="/rag", tags=["Internal RAG Retrieval"])


class RAGRetrieveRequest(BaseModel):
    student_user_id: int = Field(..., description="ID of the student user making the query")
    classroom_id: int = Field(..., description="ID of the target classroom")
    topic_id: Optional[int] = Field(None, description="Optional topic ID filter")
    query: str = Field(..., description="Student search query text")
    top_k: int = Field(5, ge=1, le=20, description="Maximum number of chunks to return")


class RAGRetrieveResponse(BaseModel):
    chunks: List[Dict[str, Any]]


def _verify_internal_secret(x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret")) -> None:
    """Validates that the incoming request contains a matching X-Internal-Secret header."""
    secret = settings.INTERNAL_SERVICE_SECRET
    if not secret or not x_internal_secret or x_internal_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid X-Internal-Secret header.",
        )


@router.post(
    "/retrieve",
    status_code=status.HTTP_200_OK,
    response_model=RAGRetrieveResponse,
    summary="Retrieve relevant course material chunks (Internal Server-to-Server)",
    description="Performs authorization check FIRST, then embeds query and executes scoped vector similarity search.",
)
async def retrieve_rag_chunks_endpoint(
    request: RAGRetrieveRequest,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    _verify_internal_secret(x_internal_secret)

    try:
        chunks = await retrieve_relevant_chunks(
            user_id=request.student_user_id,
            classroom_id=request.classroom_id,
            query_text=request.query,
            topic_id=request.topic_id,
            top_k=request.top_k,
        )
        return RAGRetrieveResponse(chunks=chunks)

    except NotAuthorizedError:
        # Generic message to avoid leaking classroom existence to unauthorized callers
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied or classroom not found.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG retrieval failed: {e}",
        )
