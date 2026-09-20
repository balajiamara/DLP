"""
Internal Materials Processing & Status Endpoints

NOTE / SECURITY NOTICE:
These endpoints are internal, server-to-server routes intended exclusively for call requests
from backend-django (or internal task schedulers). They are NOT meant for direct public frontend or
user access. All endpoints are protected by the X-Internal-Secret header.
"""

from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Header, HTTPException, BackgroundTasks, status
from app.core.config import settings
from app.services.document_processor import process_material, get_material_status_record

router = APIRouter(prefix="/materials", tags=["Internal Materials Pipeline"])


class ProcessMaterialResponse(BaseModel):
    material_id: int
    status: str


class MaterialStatusResponse(BaseModel):
    material_id: int
    status: str
    failure_reason: Optional[str] = None


def _verify_internal_secret(x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret")) -> None:
    """Validates that the incoming request contains a matching X-Internal-Secret header."""
    secret = settings.INTERNAL_SERVICE_SECRET
    if not secret or not x_internal_secret or x_internal_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid X-Internal-Secret header.",
        )


@router.post(
    "/{material_id}/process",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ProcessMaterialResponse,
    summary="Trigger document processing pipeline (Internal Server-to-Server)",
    description="Asynchronously starts text extraction, chunking, Gemini embedding, and vector storage for a material PDF.",
)
async def process_material_endpoint(
    material_id: int,
    background_tasks: BackgroundTasks,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    _verify_internal_secret(x_internal_secret)

    # Queue document processing pipeline in the background so HTTP response returns immediately
    background_tasks.add_task(process_material, material_id)

    return ProcessMaterialResponse(
        material_id=material_id,
        status="processing_started",
    )


@router.get(
    "/{material_id}/status",
    status_code=status.HTTP_200_OK,
    response_model=MaterialStatusResponse,
    summary="Poll material processing status (Internal Server-to-Server)",
    description="Returns the current status (UPLOADED, PROCESSING, READY, FAILED) and failure_reason (if any).",
)
async def get_material_status_endpoint(
    material_id: int,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    _verify_internal_secret(x_internal_secret)

    record = await get_material_status_record(material_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found.",
        )

    return MaterialStatusResponse(
        material_id=record["material_id"],
        status=record["status"],
        failure_reason=record["failure_reason"],
    )
