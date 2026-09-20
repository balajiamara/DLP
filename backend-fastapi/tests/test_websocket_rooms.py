"""
Unit tests for room-scoped WebSocket broadcasting (app.services.connection_manager)
"""

import time
import jwt
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

client = TestClient(app)
HEADERS = {"X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET}


def generate_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "token_type": "access",
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm="HS256")


@patch("app.api.websocket.is_authorized_for_classroom", return_value=True)
def test_websocket_room_broadcasting_isolation(mock_is_authorized):
    """
    Confirms broadcast for Classroom 6 reaches Classroom 6 connections,
    and is isolated from Classroom 1 connections.
    """
    token6 = generate_token(user_id=2)
    token1 = generate_token(user_id=3)

    with client.websocket_connect(f"/ws/classrooms/6/doubts?token={token6}") as ws6:
        with client.websocket_connect(f"/ws/classrooms/1/doubts?token={token1}") as ws1:
            # Issue internal broadcast HTTP POST to Classroom 6
            broadcast_payload = {
                "event_type": "doubt_created",
                "classroom_id": 6,
                "data": {
                    "id": 100,
                    "title": "Room 6 Doubt",
                    "author_id": 2,
                },
            }
            res = client.post("/broadcast/doubt", json=broadcast_payload, headers=HEADERS)
            assert res.status_code == 200
            assert res.json()["delivered_count"] == 1

            # Assert ws6 received event payload
            received_data = ws6.receive_json()
            assert received_data["event_type"] == "doubt_created"
            assert received_data["classroom_id"] == 6
            assert received_data["data"]["title"] == "Room 6 Doubt"

            # Issue internal broadcast HTTP POST to Classroom 1
            broadcast_payload1 = {
                "event_type": "doubt_created",
                "classroom_id": 1,
                "data": {
                    "id": 101,
                    "title": "Room 1 Doubt",
                    "author_id": 3,
                },
            }
            res1 = client.post("/broadcast/doubt", json=broadcast_payload1, headers=HEADERS)
            assert res1.status_code == 200
            assert res1.json()["delivered_count"] == 1

            received_data1 = ws1.receive_json()
            assert received_data1["data"]["title"] == "Room 1 Doubt"
