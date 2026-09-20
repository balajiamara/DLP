"""
Unit tests for Internal Broadcast Webhook Endpoint (app.api.broadcast)
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

client = TestClient(app)

HEADERS = {"X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET}


@patch("app.api.broadcast.manager.broadcast_to_classroom")
def test_broadcast_doubt_endpoint_success(mock_broadcast):
    """Confirms POST /broadcast/doubt returns 200 OK and calls ConnectionManager."""
    mock_broadcast.return_value = 2

    payload = {
        "event_type": "doubt_created",
        "classroom_id": 6,
        "data": {
            "id": 50,
            "title": "Broadcast Test",
            "body": "Testing broadcast endpoint",
        },
    }

    response = client.post("/broadcast/doubt", json=payload, headers=HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "broadcasted"
    assert data["delivered_count"] == 2

    mock_broadcast.assert_called_once_with(
        classroom_id=6,
        message_data={
            "event_type": "doubt_created",
            "classroom_id": 6,
            "data": {
                "id": 50,
                "title": "Broadcast Test",
                "body": "Testing broadcast endpoint",
            },
        },
    )


def test_broadcast_doubt_endpoint_unauthorized():
    """Confirms POST /broadcast/doubt returns 401 Unauthorized if secret header is wrong or missing."""
    payload = {
        "event_type": "doubt_created",
        "classroom_id": 6,
        "data": {"id": 1},
    }

    # Missing header
    res1 = client.post("/broadcast/doubt", json=payload)
    assert res1.status_code == 401

    # Invalid header
    res2 = client.post("/broadcast/doubt", json=payload, headers={"X-Internal-Secret": "invalid-secret"})
    assert res2.status_code == 401
