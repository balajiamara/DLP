"""
Django Conversation Broadcast Helper Service

Handles fire-and-forget HTTP notifications to FastAPI's internal conversation broadcast webhook.
Enforces strict timeout (2.0s) and exception boundaries so network drops or delays never disrupt
Django database transactions.
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)

FASTAPI_INTERNAL_URL = os.getenv("FASTAPI_INTERNAL_URL", "http://127.0.0.1:8001")
INTERNAL_SERVICE_SECRET = os.getenv("INTERNAL_SERVICE_SECRET", "")


def dispatch_conversation_broadcast(event_type: str, conversation_id: int, payload: dict) -> None:
    """
    Sends a fire-and-forget HTTP POST request to FastAPI /broadcast/message endpoint.

    Args:
        event_type: String identifier ('message_created').
        conversation_id: Target conversation ID room scope.
        payload: Dict data representing serialized Message details.
    """
    if not FASTAPI_INTERNAL_URL or not INTERNAL_SERVICE_SECRET:
        logger.warning("FASTAPI_INTERNAL_URL or INTERNAL_SERVICE_SECRET not configured; skipping conversation broadcast.")
        return

    url = f"{FASTAPI_INTERNAL_URL.rstrip('/')}/broadcast/message"
    headers = {
        "X-Internal-Secret": INTERNAL_SERVICE_SECRET,
        "Content-Type": "application/json",
    }
    body = {
        "event_type": event_type,
        "conversation_id": conversation_id,
        "data": payload,
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=2.0)
        if response.status_code != 200:
            logger.warning(
                f"FastAPI broadcast returned status {response.status_code} for conversation {conversation_id}."
            )
    except requests.exceptions.Timeout:
        logger.warning(
            f"FastAPI broadcast connection timed out (2.0s) for conversation {conversation_id}."
        )
    except requests.exceptions.ConnectionError as e:
        logger.warning(
            f"FastAPI broadcast connection error for conversation {conversation_id}: {e}"
        )
    except Exception as e:
        logger.warning(
            f"Unexpected error during FastAPI broadcast for conversation {conversation_id}: {e}"
        )
