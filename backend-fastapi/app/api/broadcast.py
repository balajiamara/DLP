"""
Internal Broadcast API Router

Receives server-to-server HTTP notification events from backend-django (`POST /broadcast/doubt`)
and dispatches real-time WebSocket payloads to active connected clients in classroom rooms.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.connection_manager import manager, conversation_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broadcast", tags=["internal-broadcast"])


class DoubtBroadcastRequest(BaseModel):
    event_type: str = Field(..., description="Type of event: doubt_created, reply_created, or answer_accepted")
    classroom_id: int = Field(..., description="Target classroom ID room scope")
    data: Dict[str, Any] = Field(..., description="Event payload dictionary")


class MessageBroadcastRequest(BaseModel):
    event_type: str = Field(..., description="Type of event: message_created")
    conversation_id: int = Field(..., description="Target conversation ID room scope")
    data: Dict[str, Any] = Field(..., description="Event payload dictionary")


def _verify_internal_secret(x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret")) -> None:
    """Validates that the incoming request contains a matching X-Internal-Secret header."""
    secret = settings.INTERNAL_SERVICE_SECRET
    if not secret or not x_internal_secret or x_internal_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid X-Internal-Secret header.",
        )


@router.post(
    "/doubt",
    status_code=status.HTTP_200_OK,
    summary="Internal Broadcast Webhook for Doubt Forum Events",
)
async def broadcast_doubt_event(
    request: DoubtBroadcastRequest,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    """
    Receives doubt/reply events from backend-django and broadcasts them to active WebSockets in classroom_id.
    """
    _verify_internal_secret(x_internal_secret)

    payload = {
        "event_type": request.event_type,
        "classroom_id": request.classroom_id,
        "data": request.data,
    }

    delivered_count = await manager.broadcast_to_classroom(
        classroom_id=request.classroom_id,
        message_data=payload,
    )

    return {
        "status": "broadcasted",
        "delivered_count": delivered_count,
    }


@router.post(
    "/message",
    status_code=status.HTTP_200_OK,
    summary="Internal Broadcast Webhook for Unified Chat Message Events",
)
async def broadcast_message_event(
    request: MessageBroadcastRequest,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
):
    """
    Receives message events from backend-django and broadcasts them to active WebSockets in conversation_id room.
    """
    _verify_internal_secret(x_internal_secret)

    payload = {
        "event_type": request.event_type,
        "conversation_id": request.conversation_id,
        "data": request.data,
    }

    delivered_count = await conversation_manager.broadcast_to_conversation(
        conversation_id=request.conversation_id,
        message_data=payload,
    )

    return {
        "status": "broadcasted",
        "delivered_count": delivered_count,
    }

