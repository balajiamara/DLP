import time
import jwt
import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

def run_live_websocket_verification():
    print("=========================================================")
    print("  SUPERVISED LIVE E2E VERIFICATION: STEP 36 WEBSOCKETS ")
    print("=========================================================\n")

    client = TestClient(app)

    # 1. Generate valid JWT access token for user_id = 2
    user_id = 2
    classroom_id = 6
    payload = {
        "user_id": user_id,
        "token_type": "access",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm="HS256")
    print(f"Generated JWT Access Token for User {user_id} in Classroom {classroom_id}.")

    # 2. Establish WebSocket Connection
    print("Connecting WebSocket client to /ws/classrooms/6/doubts...")
    with client.websocket_connect(f"/ws/classrooms/{classroom_id}/doubts?token={token}") as ws:
        print("  WebSocket Handshake & Auth SUCCESS! Socket open.")

        # 3. Issue Internal Broadcast HTTP POST (Simulating Django notification)
        headers = {"X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET}
        broadcast_payload = {
            "event_type": "doubt_created",
            "classroom_id": classroom_id,
            "data": {
                "id": 999,
                "title": "Real-time WebSocket Test Doubt",
                "body": "Is the WebSocket connection active?",
                "author_id": user_id,
                "author_username": "teacher_user",
                "created_at": "2026-09-08T11:55:00Z",
            },
        }

        print("\nIssuing POST /broadcast/doubt webhook from Django simulation...")
        http_res = client.post("/broadcast/doubt", json=broadcast_payload, headers=headers)
        print(f"  HTTP Response: {http_res.status_code} | Payload: {http_res.json()}")
        assert http_res.status_code == 200
        assert http_res.json()["delivered_count"] == 1

        # 4. Receive and verify real-time WebSocket broadcast event
        print("\nWaiting for WebSocket broadcast event...")
        event_received = ws.receive_json()
        print("  Received WebSocket Event:")
        print(f"    Event Type:   {event_received.get('event_type')}")
        print(f"    Classroom ID: {event_received.get('classroom_id')}")
        print(f"    Doubt Title:  {event_received.get('data', {}).get('title')}\n")

        assert event_received["event_type"] == "doubt_created"
        assert event_received["classroom_id"] == classroom_id
        assert event_received["data"]["id"] == 999

    print("=========================================================")
    print("  ALL SUPERVISED LIVE WEBSOCKET CHECKS PASSED CLEANLY!   ")
    print("=========================================================")

if __name__ == "__main__":
    run_live_websocket_verification()
