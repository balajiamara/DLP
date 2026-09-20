"""
Live Two-Session Verification Script for Unified Chat WebSockets

Connects real WebSocket clients to FastAPI (port 8001) while making real REST requests
to Django (port 8000). Verifies live message delivery across two sessions for:
1. CLASSROOM conversation
2. DIRECT conversation (DM)
3. Negative authorization check (outsider rejected)
"""

import os
import sys
import json
import time
import asyncio
import websockets
import requests

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import jwt
from app.core.config import settings


DJANGO_URL = "http://127.0.0.1:8000"
FASTAPI_WS_URL = "ws://127.0.0.1:8001"


import uuid

def get_token_for_user(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "token_type": "access",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm="HS256")



async def test_classroom_conversation_live():
    print("\n=======================================================")
    print("TEST 1: Real-Time Live Delivery for CLASSROOM Conversation")
    print("=======================================================")

    teacher_id = 2  # 'tester'
    student_id = 4  # 'test3'

    teacher_token = get_token_for_user(teacher_id)
    student_token = get_token_for_user(student_id)

    conv_id = 6  # Classroom 6 conversation

    ws_uri = f"{FASTAPI_WS_URL}/ws/conversations/{conv_id}?token={student_token}"
    print(f"[Session B - Student 'test3'] Connecting to WebSocket: {ws_uri[:65]}...")

    async with websockets.connect(ws_uri) as ws_b:
        print("[Session B] WebSocket handshake SUCCEEDED. Listening for real-time messages...")

        # Small pause to ensure socket is registered in connection_manager
        await asyncio.sleep(0.5)

        # Session A (Teacher 'tester') sends message via Django REST API
        rest_url = f"{DJANGO_URL}/api/conversations/{conv_id}/messages/"
        headers = {
            "Authorization": f"Bearer {teacher_token}",
            "Content-Type": "application/json",
        }
        test_body = f"Live Classroom broadcast test from Session A at {time.time()}!"
        print(f"[Session A - Teacher 'tester'] Sending POST {rest_url} with body='{test_body[:35]}...'")

        send_time = time.time()
        resp = requests.post(rest_url, json={"body": test_body}, headers=headers, timeout=15.0)
        assert resp.status_code == 201, f"Django returned {resp.status_code}: {resp.text}"
        print(f"[Session A] Django saved message (ID={resp.json()['id']}) and returned HTTP 201.")

        # Session B awaits message over WebSocket
        print("[Session B] Awaiting WebSocket message frame...")
        raw_msg = await asyncio.wait_for(ws_b.recv(), timeout=15.0)
        recv_time = time.time()
        latency_ms = (recv_time - send_time) * 1000

        data = json.loads(raw_msg)
        print(f"[Session B] RECEIVED WEBSOCKET EVENT in {latency_ms:.1f}ms:")
        print(json.dumps(data, indent=2))

        assert data["event_type"] == "message_created"
        assert data["conversation_id"] == conv_id
        assert data["data"]["body"] == test_body
        assert data["data"]["sender"]["username"] == "tester"
        print(">>> [SUCCESS] Classroom live broadcast received and verified perfectly!")


async def test_direct_conversation_live():
    print("\n=======================================================")
    print("TEST 2: Real-Time Live Delivery for DIRECT Conversation (DM)")
    print("=======================================================")

    teacher_id = 2  # 'tester'
    student_id = 4  # 'test3'

    teacher_token = get_token_for_user(teacher_id)
    student_token = get_token_for_user(student_id)

    # Find or create DM conversation
    dm_res = requests.post(
        f"{DJANGO_URL}/api/conversations/direct/",
        json={"target_user_id": student_id},
        headers={"Authorization": f"Bearer {teacher_token}"},
        timeout=15.0
    )
    assert dm_res.status_code in (200, 201), f"DM find-or-create failed: {dm_res.text}"
    dm_conv_id = dm_res.json()["id"]
    print(f"[DM Setup] Target conversation ID = {dm_conv_id} between tester (ID=2) and test3 (ID=4)")

    ws_uri = f"{FASTAPI_WS_URL}/ws/conversations/{dm_conv_id}?token={student_token}"
    print(f"[Session B - Student 'test3'] Connecting to DM WebSocket: {ws_uri[:65]}...")

    async with websockets.connect(ws_uri) as ws_b:
        print("[Session B] WebSocket handshake SUCCEEDED for DM room. Listening for messages...")

        await asyncio.sleep(0.5)

        # Session A sends DM message via Django REST API
        rest_url = f"{DJANGO_URL}/api/conversations/{dm_conv_id}/messages/"
        headers = {
            "Authorization": f"Bearer {teacher_token}",
            "Content-Type": "application/json",
        }
        test_body = f"Live DM broadcast test from Session A at {time.time()}!"
        print(f"[Session A - Teacher 'tester'] Sending POST {rest_url} with body='{test_body[:35]}...'")

        send_time = time.time()
        resp = requests.post(rest_url, json={"body": test_body}, headers=headers, timeout=15.0)
        assert resp.status_code == 201, f"Django returned {resp.status_code}: {resp.text}"
        print(f"[Session A] Django saved DM message (ID={resp.json()['id']}) and returned HTTP 201.")

        # Session B awaits DM over WebSocket
        print("[Session B] Awaiting DM WebSocket message frame...")
        raw_msg = await asyncio.wait_for(ws_b.recv(), timeout=15.0)
        recv_time = time.time()
        latency_ms = (recv_time - send_time) * 1000

        data = json.loads(raw_msg)
        print(f"[Session B] RECEIVED DM WEBSOCKET EVENT in {latency_ms:.1f}ms:")
        print(json.dumps(data, indent=2))

        assert data["event_type"] == "message_created"
        assert data["conversation_id"] == dm_conv_id
        assert data["data"]["body"] == test_body
        assert data["data"]["sender"]["username"] == "tester"
        print(">>> [SUCCESS] Direct message live broadcast received and verified perfectly!")

    # Test 3: Negative Authorization test (Outsider User 5 'test4' cannot connect to this DM)
    print("\n[Negative Check] User 'test4' (outsider) attempts connection to this DM room...")
    test4_token = get_token_for_user(5)

    outsider_ws_uri = f"{FASTAPI_WS_URL}/ws/conversations/{dm_conv_id}?token={test4_token}"
    rejected = False
    try:
        async with websockets.connect(outsider_ws_uri) as ws_outsider:
            pass
    except (websockets.exceptions.InvalidStatus, getattr(websockets.exceptions, 'InvalidStatusCode', Exception)) as e:
        print(f"[Negative Check] Rejected as expected with status: {e}")
        rejected = True
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"[Negative Check] Connection closed before accept as expected: {e}")
        rejected = True

    assert rejected, "Outsider should have been rejected from DM WebSocket room!"
    print(">>> [SUCCESS] Negative authorization check verified: outsider denied access.")


async def main():
    await test_classroom_conversation_live()
    await test_direct_conversation_live()
    print("\n=======================================================")
    print("  ALL LIVE TWO-SESSION WEBSOCKET TESTS PASSED CLEANLY! ")
    print("=======================================================\n")


if __name__ == "__main__":
    asyncio.run(main())
