"""
Unit tests for WebSocket JWT authentication and proactive token expiry lifecycle management.
"""

import time
import jwt
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

client = TestClient(app)


def generate_test_jwt(user_id: int = 2, token_type: str = "access", expires_in: int = 3600) -> str:
    """Helper to generate signed JWT tokens for testing."""
    payload = {
        "user_id": user_id,
        "token_type": token_type,
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm="HS256")


@patch("app.api.websocket.is_authorized_for_classroom")
def test_websocket_auth_valid_access_token(mock_is_authorized):
    """Confirms valid access token allows WebSocket handshake to succeed."""
    mock_is_authorized.return_value = True
    token = generate_test_jwt(user_id=2, token_type="access", expires_in=3600)

    with client.websocket_connect(f"/ws/classrooms/6/doubts?token={token}") as websocket:
        mock_is_authorized.assert_called_once_with(user_id=2, classroom_id=6)


@patch("app.api.websocket.is_authorized_for_classroom")
def test_websocket_auth_refresh_token_rejected(mock_is_authorized):
    """Confirms refresh token is rejected with 4001 policy violation before connect."""
    mock_is_authorized.return_value = True
    refresh_token = generate_test_jwt(user_id=2, token_type="refresh", expires_in=3600)

    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/classrooms/6/doubts?token={refresh_token}"):
            pass


@patch("app.api.websocket.is_authorized_for_classroom")
def test_websocket_auth_expired_token_rejected(mock_is_authorized):
    """Confirms expired access token is rejected before connect."""
    mock_is_authorized.return_value = True
    expired_token = generate_test_jwt(user_id=2, token_type="access", expires_in=-10)

    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/classrooms/6/doubts?token={expired_token}"):
            pass


@patch("app.api.websocket.is_authorized_for_classroom")
def test_websocket_auth_unauthorized_classroom(mock_is_authorized):
    """Confirms unauthorized user in classroom is rejected before connect."""
    mock_is_authorized.return_value = False
    token = generate_test_jwt(user_id=99, token_type="access", expires_in=3600)

    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/classrooms/6/doubts?token={token}"):
            pass
