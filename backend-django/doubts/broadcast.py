"""
Django Broadcast Helper Service

Handles fire-and-forget HTTP notifications to FastAPI's internal broadcast webhook.
Enforces strict timeout and error boundaries to ensure network issues never disrupt
Django database transactions.
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)

FASTAPI_INTERNAL_URL = os.getenv("FASTAPI_INTERNAL_URL", "http://127.0.0.1:8001")
INTERNAL_SERVICE_SECRET = os.getenv("INTERNAL_SERVICE_SECRET", "")


def dispatch_doubt_broadcast(event_type: str, classroom_id: int, payload: dict) -> None:
    """
    Sends a fire-and-forget HTTP POST request to FastAPI internal broadcast endpoint.

    Args:
        event_type: String identifier ('doubt_created', 'reply_created', 'answer_accepted').
        classroom_id: Target classroom ID scope.
        payload: Dict data representing the doubt/reply details.
    """
    if not FASTAPI_INTERNAL_URL or not INTERNAL_SERVICE_SECRET:
        logger.warning("FASTAPI_INTERNAL_URL or INTERNAL_SERVICE_SECRET not configured; skipping broadcast.")
        return

    url = f"{FASTAPI_INTERNAL_URL.rstrip('/')}/broadcast/doubt"
    headers = {
        "X-Internal-Secret": INTERNAL_SERVICE_SECRET,
        "Content-Type": "application/json",
    }
    body = {
        "event_type": event_type,
        "classroom_id": classroom_id,
        "data": payload,
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=2.0)
        if response.status_code != 200:
            logger.warning(
                f"FastAPI broadcast returned unexpected status {response.status_code} for classroom {classroom_id}."
            )
    except requests.exceptions.Timeout:
        logger.warning(
            f"FastAPI broadcast connection timed out (2.0s) for classroom {classroom_id}."
        )
    except requests.exceptions.ConnectionError as e:
        logger.warning(
            f"FastAPI broadcast connection error for classroom {classroom_id}: {e}"
        )
    except Exception as e:
        logger.warning(
            f"Unexpected error during FastAPI broadcast for classroom {classroom_id}: {e}"
        )
