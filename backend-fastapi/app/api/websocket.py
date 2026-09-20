"""
WebSocket Doubts Router

Handles direct real-time WebSocket connections from students and teachers (`WS /ws/classrooms/{classroom_id}/doubts`).
Performs JWT query param verification (HS256, access token_type), pre-connection classroom authorization,
and room registration.
"""

import json
import jwt
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from app.core.config import settings
from app.services.connection_manager import manager, conversation_manager
from app.services.rag_retrieval import is_authorized_for_classroom
from app.services.conversation_authorization import is_authorized_for_conversation


logger = logging.getLogger(__name__)

router = APIRouter(tags=["websockets"])


@router.websocket("/ws/classrooms/{classroom_id}/doubts")
async def websocket_doubts_endpoint(
    websocket: WebSocket,
    classroom_id: int,
):
    """
    WebSocket endpoint for real-time doubt forum updates within classroom_id scope.

    Handshake Validation (Pre-Connect):
    1. Extract `token` query param (`ws://.../doubts?token=<jwt>`).
    2. Decode JWT with PyJWT using `JWT_SIGNING_KEY` & algorithm HS256 (`verify_exp=True`).
    3. Assert `token_type == 'access'`. If invalid or refresh token -> close 4001 Unauthorized.
    4. Verify user membership (`is_authorized_for_classroom`). If unauthorized -> close 4003 Forbidden.
    5. Accept socket (`websocket.accept()`) and schedule token-expiry disconnect timer.
    """
    token = websocket.query_params.get("token")
    if not token:
        logger.warning(f"WebSocket connect rejected: Missing token query parameter for classroom {classroom_id}.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return

    # 1. Decode and verify JWT signature and claims
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SIGNING_KEY,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        logger.warning(f"WebSocket connect rejected: Token expired for classroom {classroom_id}.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token expired")
        return
    except jwt.PyJWTError as e:
        logger.warning(f"WebSocket connect rejected: Invalid JWT for classroom {classroom_id}: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
        return

    # 2. Assert token_type == 'access'
    token_type = payload.get("token_type")
    if token_type != "access":
        logger.warning(
            f"WebSocket connect rejected: Invalid token_type '{token_type}' (expected 'access') for classroom {classroom_id}."
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token type")
        return

    user_id_raw = payload.get("user_id")
    if not user_id_raw:
        logger.warning(f"WebSocket connect rejected: Missing user_id claim for classroom {classroom_id}.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token claims")
        return
    user_id = int(user_id_raw)

    # 3. Pre-connection classroom authorization check
    authorized = await is_authorized_for_classroom(user_id=user_id, classroom_id=classroom_id)
    if not authorized:
        logger.warning(
            f"WebSocket connect rejected: User {user_id} is not an active member of classroom {classroom_id}."
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Forbidden: Classroom access denied")
        return

    # 4. Accept connection and register room manager
    await websocket.accept()
    exp_timestamp = float(payload.get("exp", 0.0))
    await manager.connect(classroom_id=classroom_id, websocket=websocket, exp_timestamp=exp_timestamp)

    # 5. Listen for disconnection or incoming ping/pong frames
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
                if isinstance(data, dict) and data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except (json.JSONDecodeError, UnicodeDecodeError):
                if raw_text.strip().lower() == "ping":
                    await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected naturally from classroom {classroom_id}.")
    except Exception as e:
        logger.warning(f"WebSocket error in classroom {classroom_id}: {e}")
    finally:
        await manager.disconnect(classroom_id=classroom_id, websocket=websocket)


@router.websocket("/ws/conversations/{conversation_id}")
async def websocket_conversation_endpoint(
    websocket: WebSocket,
    conversation_id: int,
):
    """
    WebSocket endpoint for real-time chat messages within conversation_id scope.

    Handshake Validation (Pre-Connect):
    1. Extract `token` query param (`ws://.../ws/conversations/{id}?token=<jwt>`).
    2. Decode JWT with PyJWT using `JWT_SIGNING_KEY` & algorithm HS256 (`verify_exp=True`).
    3. Assert `token_type == 'access'`. If invalid or refresh token -> close 4001/1008.
    4. Verify conversation authorization (`is_authorized_for_conversation`). If unauthorized -> close 1008 Forbidden.
    5. Accept socket (`websocket.accept()`) and schedule token-expiry disconnect timer.
    """
    token = websocket.query_params.get("token")
    if not token:
        logger.warning(f"WebSocket connect rejected: Missing token query parameter for conversation {conversation_id}.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return

    # 1. Decode and verify JWT signature and claims
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SIGNING_KEY,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        logger.warning(f"WebSocket connect rejected: Token expired for conversation {conversation_id}.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token expired")
        return
    except jwt.PyJWTError as e:
        logger.warning(f"WebSocket connect rejected: Invalid JWT for conversation {conversation_id}: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
        return

    # 2. Assert token_type == 'access'
    token_type = payload.get("token_type")
    if token_type != "access":
        logger.warning(
            f"WebSocket connect rejected: Invalid token_type '{token_type}' (expected 'access') for conversation {conversation_id}."
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token type")
        return

    user_id_raw = payload.get("user_id")
    if not user_id_raw:
        logger.warning(f"WebSocket connect rejected: Missing user_id claim for conversation {conversation_id}.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token claims")
        return
    user_id = int(user_id_raw)

    # 3. Pre-connection conversation authorization check
    authorized = await is_authorized_for_conversation(user_id=user_id, conversation_id=conversation_id)
    if not authorized:
        logger.warning(
            f"WebSocket connect rejected: User {user_id} is not authorized for conversation {conversation_id}."
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Forbidden: Conversation access denied")
        return

    # 4. Accept connection and register room manager
    await websocket.accept()
    exp_timestamp = float(payload.get("exp", 0.0))
    await conversation_manager.connect(classroom_id=conversation_id, websocket=websocket, exp_timestamp=exp_timestamp)

    # 5. Listen for disconnection or incoming ping/pong frames
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
                if isinstance(data, dict) and data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except (json.JSONDecodeError, UnicodeDecodeError):
                if raw_text.strip().lower() == "ping":
                    await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected naturally from conversation {conversation_id}.")
    except Exception as e:
        logger.warning(f"WebSocket error in conversation {conversation_id}: {e}")
    finally:
        await conversation_manager.disconnect(classroom_id=conversation_id, websocket=websocket)

