"""
Unit and integration tests for Unified Chat WebSocket (/ws/conversations/{id})
and Internal Broadcast (/broadcast/message).
"""

import time
import jwt
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

client = TestClient(app)
HEADERS = {"X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET}


def generate_test_jwt(user_id: int = 2, token_type: str = "access", expires_in: int = 3600, secret: str = None) -> str:
    """Helper to generate signed JWT tokens for testing."""
    payload = {
        "user_id": user_id,
        "token_type": token_type,
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, secret or settings.JWT_SIGNING_KEY, algorithm="HS256")


# =========================================================================
# 1. JWT Authentication & Handshake Tests
# =========================================================================

@patch("app.api.websocket.is_authorized_for_conversation", new_callable=AsyncMock)
def test_conversation_websocket_valid_token(mock_is_auth):
    """Valid access token allows connection to conversation WebSocket."""
    mock_is_auth.return_value = True
    token = generate_test_jwt(user_id=2, token_type="access", expires_in=3600)

    with client.websocket_connect(f"/ws/conversations/10?token={token}") as ws:
        mock_is_auth.assert_called_once_with(user_id=2, conversation_id=10)


@patch("app.api.websocket.is_authorized_for_conversation", new_callable=AsyncMock)
def test_conversation_websocket_refresh_token_rejected(mock_is_auth):
    """Refresh token is rejected before connection."""
    mock_is_auth.return_value = True
    refresh_token = generate_test_jwt(user_id=2, token_type="refresh", expires_in=3600)

    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/conversations/10?token={refresh_token}"):
            pass


@patch("app.api.websocket.is_authorized_for_conversation", new_callable=AsyncMock)
def test_conversation_websocket_expired_token_rejected(mock_is_auth):
    """Expired access token is rejected before connection."""
    mock_is_auth.return_value = True
    expired_token = generate_test_jwt(user_id=2, token_type="access", expires_in=-10)

    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/conversations/10?token={expired_token}"):
            pass


@patch("app.api.websocket.is_authorized_for_conversation", new_callable=AsyncMock)
def test_conversation_websocket_wrong_signing_key_rejected(mock_is_auth):
    """Token signed with wrong key is rejected."""
    mock_is_auth.return_value = True
    bad_token = generate_test_jwt(user_id=2, secret="wrong-secret-key-1234567890123456")

    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/conversations/10?token={bad_token}"):
            pass


def test_conversation_websocket_missing_token_rejected():
    """Missing token query param is rejected."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/conversations/10"):
            pass


# =========================================================================
# 2. Authorization Boundary Tests (CLASSROOM, GROUP, DIRECT)
# =========================================================================

@patch("app.api.websocket.is_authorized_for_conversation", new_callable=AsyncMock)
def test_conversation_websocket_authorized_user_allowed(mock_is_auth):
    """Authorized user is admitted."""
    mock_is_auth.return_value = True
    token = generate_test_jwt(user_id=5)

    with client.websocket_connect(f"/ws/conversations/15?token={token}"):
        pass
    mock_is_auth.assert_called_once_with(user_id=5, conversation_id=15)


@patch("app.api.websocket.is_authorized_for_conversation", new_callable=AsyncMock)
def test_conversation_websocket_unauthorized_user_rejected(mock_is_auth):
    """Unauthorized user (not in classroom, not in group, or not in DM) is rejected."""
    mock_is_auth.return_value = False
    token = generate_test_jwt(user_id=99)

    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/conversations/15?token={token}"):
            pass
    mock_is_auth.assert_called_once_with(user_id=99, conversation_id=15)


# =========================================================================
# 3. Room Isolation & Delivery Tests
# =========================================================================

@patch("app.api.websocket.is_authorized_for_conversation", new_callable=AsyncMock)
def test_conversation_room_isolation_and_delivery(mock_is_auth):
    """
    Confirms broadcast for Conversation 10 reaches only Conversation 10 clients,
    and Conversation 20 clients receive zero messages.
    """
    mock_is_auth.return_value = True

    token10 = generate_test_jwt(user_id=2)
    token20 = generate_test_jwt(user_id=3)

    with client.websocket_connect(f"/ws/conversations/10?token={token10}") as ws10:
        with client.websocket_connect(f"/ws/conversations/20?token={token20}") as ws20:
            # Broadcast to Conversation 10
            payload10 = {
                "event_type": "message_created",
                "conversation_id": 10,
                "data": {
                    "id": 101,
                    "body": "Hello Conv 10",
                    "sender": {"id": 2, "username": "user2"},
                },
            }
            res = client.post("/broadcast/message", json=payload10, headers=HEADERS)
            assert res.status_code == 200
            assert res.json()["delivered_count"] == 1

            # ws10 receives message
            received = ws10.receive_json()
            assert received["event_type"] == "message_created"
            assert received["conversation_id"] == 10
            assert received["data"]["body"] == "Hello Conv 10"

            # Broadcast to Conversation 20
            payload20 = {
                "event_type": "message_created",
                "conversation_id": 20,
                "data": {
                    "id": 102,
                    "body": "Hello Conv 20",
                    "sender": {"id": 3, "username": "user3"},
                },
            }
            res2 = client.post("/broadcast/message", json=payload20, headers=HEADERS)
            assert res2.status_code == 200
            assert res2.json()["delivered_count"] == 1

            # ws20 receives message
            received20 = ws20.receive_json()
            assert received20["event_type"] == "message_created"
            assert received20["conversation_id"] == 20
            assert received20["data"]["body"] == "Hello Conv 20"


# =========================================================================
# 4. Broadcast Endpoint Security
# =========================================================================

def test_broadcast_message_missing_secret_rejected():
    """POST /broadcast/message fails 401 without X-Internal-Secret."""
    payload = {
        "event_type": "message_created",
        "conversation_id": 10,
        "data": {"id": 1, "body": "test"},
    }
    res = client.post("/broadcast/message", json=payload)
    assert res.status_code == 401


def test_broadcast_message_wrong_secret_rejected():
    """POST /broadcast/message fails 401 with invalid secret."""
    payload = {
        "event_type": "message_created",
        "conversation_id": 10,
        "data": {"id": 1, "body": "test"},
    }
    res = client.post("/broadcast/message", json=payload, headers={"X-Internal-Secret": "invalid"})
    assert res.status_code == 401


# =========================================================================
# 5. Service Logic Unit Test (is_authorized_for_conversation)
# =========================================================================

@pytest.mark.asyncio
async def test_is_authorized_for_conversation_service_logic():
    """Test is_authorized_for_conversation logic against mock DB queries."""
    from app.services.conversation_authorization import is_authorized_for_conversation

    from unittest.mock import MagicMock
    # Test non-existent conversation returns False
    with patch("app.services.conversation_authorization.async_session_maker") as mock_maker:
        mock_session = AsyncMock()
        mock_maker.return_value.__aenter__.return_value = mock_session
        mock_res = MagicMock()
        mock_res.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_res)

        authorized = await is_authorized_for_conversation(user_id=1, conversation_id=999)
        assert authorized is False

    # Test DIRECT conversation: participant A authorized, participant B authorized, user C rejected
    with patch("app.services.conversation_authorization.async_session_maker") as mock_maker:
        mock_session = AsyncMock()
        mock_maker.return_value.__aenter__.return_value = mock_session

        class MockConv:
            type = "DIRECT"
            classroom_id = None
            group_id = None
            user_a_id = 5
            user_b_id = 10

        mock_res = MagicMock()
        mock_res.first.return_value = MockConv()
        mock_session.execute = AsyncMock(return_value=mock_res)

        assert await is_authorized_for_conversation(user_id=5, conversation_id=1) is True
        assert await is_authorized_for_conversation(user_id=10, conversation_id=1) is True
        assert await is_authorized_for_conversation(user_id=99, conversation_id=1) is False


@patch("app.api.websocket.is_authorized_for_conversation", new_callable=AsyncMock)
def test_conversation_websocket_ping_pong_heartbeat(mock_is_auth):
    """
    Confirms client-side ping messages are received gracefully and replied to with pong,
    and arbitrary text is ignored without dropping the connection.
    """
    mock_is_auth.return_value = True
    token = generate_test_jwt(user_id=2)

    with client.websocket_connect(f"/ws/conversations/10?token={token}") as ws:
        # 1. Send JSON ping -> receive JSON pong
        ws.send_json({"type": "ping"})
        pong_data = ws.receive_json()
        assert pong_data == {"type": "pong"}

        # 2. Send plain text ping -> receive plain text pong
        ws.send_text("ping")
        pong_text = ws.receive_text()
        assert pong_text == "pong"

        # 3. Send arbitrary unrecognized text frame -> does NOT raise error or close socket
        ws.send_text("random client payload")
        # Connection stays open and ready for future frames
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


