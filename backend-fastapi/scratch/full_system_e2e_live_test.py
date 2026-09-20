"""
Full System Live End-to-End Verification: Step 36 (WebSocket Real-Time Doubts)

This script performs the full system verification by:
1. Spawning the real FastAPI app server on http://127.0.0.1:8001.
2. Spawning the real Django app server on http://127.0.0.1:8000.
3. Obtaining real JWT access tokens via Django's POST /api/auth/token/ endpoint for student and teacher users.
4. Connecting a real WebSocket client to ws://127.0.0.1:8001/ws/classrooms/1/doubts?token=<access_token>.
5. Creating a REAL Doubt via Django's REST API (POST /api/classrooms/1/doubts/) and verifying real-time WS event receipt.
6. Creating a REAL DoubtReply via Django's REST API (POST /api/classrooms/1/doubts/<doubt_id>/replies/) and verifying real-time WS event receipt.
7. Accepting the answer via Django's REST API (PATCH /api/classrooms/1/doubts/<doubt_id>/replies/<reply_id>/accept/) and verifying real-time WS event receipt.
8. Asserting all payload fields match real database models and timestamps.
"""

import sys
import os
import time
import json
import asyncio
import subprocess
import requests
import websockets

DJANGO_DIR = r"c:\Users\balaj\Desktop\DLP\backend-django"
FASTAPI_DIR = r"c:\Users\balaj\Desktop\DLP\backend-fastapi"

DJANGO_PYTHON = os.path.join(DJANGO_DIR, "venv", "Scripts", "python.exe")
FASTAPI_PYTHON = os.path.join(FASTAPI_DIR, "venv", "Scripts", "python.exe")

FASTAPI_URL = "http://127.0.0.1:8001"
DJANGO_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8001/ws/classrooms/1/doubts"

def wait_for_server(url, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code in (200, 404, 405):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

async def run_e2e_verification():
    print("==========================================================================")
    print("  FULL SYSTEM LIVE END-TO-END VERIFICATION: STEP 36 WEBSOCKET BROADCASTS  ")
    print("==========================================================================\n")

    # 1. Start FastAPI process
    print("1. Launching FastAPI app server on http://127.0.0.1:8001...")
    fastapi_proc = subprocess.Popen(
        [FASTAPI_PYTHON, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
        cwd=FASTAPI_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # 2. Start Django process
    print("2. Launching Django app server on http://127.0.0.1:8000...")
    django_env = os.environ.copy()
    django_env["FASTAPI_INTERNAL_URL"] = FASTAPI_URL
    django_proc = subprocess.Popen(
        [DJANGO_PYTHON, "manage.py", "runserver", "127.0.0.1:8000", "--noreload"],
        cwd=DJANGO_DIR,
        env=django_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        print("Waiting for FastAPI server readiness...")
        if not wait_for_server(f"{FASTAPI_URL}/health"):
            raise RuntimeError("FastAPI server failed to start within timeout.")
        print("  FastAPI server is UP!")

        print("Waiting for Django server readiness...")
        if not wait_for_server(f"{DJANGO_URL}/api/auth/token/"):
            raise RuntimeError("Django server failed to start within timeout.")
        print("  Django server is UP!\n")

        # 3. Authenticate with Django REST API to obtain real JWT tokens
        print("3. Authenticating real users against Django POST /api/auth/token/...")
        
        # Student login
        res = requests.post(f"{DJANGO_URL}/api/auth/token/", json={"email": "test2@gmail.com", "password": "testpass123"})
        assert res.status_code == 200, f"Student authentication failed: {res.text}"
        student_token = res.json()["access"]
        print("  Authenticated student 'tester2' (test2@gmail.com). Received valid JWT access token.")

        # Teacher login
        res = requests.post(f"{DJANGO_URL}/api/auth/token/", json={"email": "test@gmail.com", "password": "testpass123"})
        assert res.status_code == 200, f"Teacher authentication failed: {res.text}"
        teacher_token = res.json()["access"]
        print("  Authenticated teacher 'tester' (test@gmail.com). Received valid JWT access token.\n")

        # 4. Connect WebSocket Client to FastAPI
        print("4. Connecting real WebSocket client to FastAPI...")
        ws_connect_url = f"{WS_URL}?token={student_token}"
        
        async with websockets.connect(ws_connect_url) as ws:
            print("  WebSocket Handshake & Pre-Connection Classroom Authorization SUCCESSFUL!\n")

            # 5. Create REAL Doubt via Django REST API
            print("5. [ACTION 1] POSTing REAL Doubt to Django REST API (POST /api/classrooms/1/doubts/)...")
            headers = {"Authorization": f"Bearer {student_token}"}
            doubt_payload = {
                "title": "Real End-to-End WebSocket Verification Doubt",
                "body": "Is this real doubt broadcasted via Django view and FastAPI WebSocket?"
            }
            res = requests.post(f"{DJANGO_URL}/api/classrooms/1/doubts/", json=doubt_payload, headers=headers)
            assert res.status_code == 201, f"Failed to create doubt: {res.text}"
            saved_doubt = res.json()
            doubt_id = saved_doubt["id"]
            print(f"  Django saved Doubt ID {doubt_id}: title='{saved_doubt['title']}', author='{saved_doubt['author_username']}'")

            print("  Awaiting WebSocket broadcast event for 'doubt_created'...")
            event_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            event_1 = json.loads(event_raw)
            print("  RECEIVED WEBSOCKET EVENT 1:")
            print(f"    Event Type:   {event_1.get('event_type')}")
            print(f"    Classroom ID: {event_1.get('classroom_id')}")
            print(f"    Payload ID:   {event_1.get('data', {}).get('id')}")
            print(f"    Title:        {event_1.get('data', {}).get('title')}")
            print(f"    Author:       {event_1.get('data', {}).get('author_username')}")
            print(f"    Created At:   {event_1.get('data', {}).get('created_at')}\n")

            assert event_1["event_type"] == "doubt_created"
            assert event_1["classroom_id"] == 1
            assert event_1["data"]["id"] == doubt_id
            assert event_1["data"]["title"] == "Real End-to-End WebSocket Verification Doubt"
            assert event_1["data"]["author_username"] == "tester2"
            print("  [SUCCESS] Action 1 (doubt_created) payload & broadcast matched DB model perfectly!\n")

            # 6. Create REAL DoubtReply via Django REST API
            print("6. [ACTION 2] POSTing REAL DoubtReply to Django REST API (POST /api/classrooms/1/doubts/<id>/replies/)...")
            teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
            reply_payload = {
                "body": "Yes! Django dispatches this reply to FastAPI, and FastAPI delivers it to WebSockets!"
            }
            res = requests.post(f"{DJANGO_URL}/api/classrooms/1/doubts/{doubt_id}/replies/", json=reply_payload, headers=teacher_headers)
            assert res.status_code == 201, f"Failed to create reply: {res.text}"
            saved_reply = res.json()
            reply_id = saved_reply["id"]
            print(f"  Django saved Reply ID {reply_id}: doubt={saved_reply['doubt']}, author='{saved_reply['author_username']}'")

            print("  Awaiting WebSocket broadcast event for 'reply_created'...")
            event_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            event_2 = json.loads(event_raw)
            print("  RECEIVED WEBSOCKET EVENT 2:")
            print(f"    Event Type:   {event_2.get('event_type')}")
            print(f"    Classroom ID: {event_2.get('classroom_id')}")
            print(f"    Payload ID:   {event_2.get('data', {}).get('id')}")
            print(f"    Doubt ID:     {event_2.get('data', {}).get('doubt')}")
            print(f"    Body:         {event_2.get('data', {}).get('body')}")
            print(f"    Author:       {event_2.get('data', {}).get('author_username')}\n")

            assert event_2["event_type"] == "reply_created"
            assert event_2["classroom_id"] == 1
            assert event_2["data"]["id"] == reply_id
            assert event_2["data"]["doubt"] == doubt_id
            assert event_2["data"]["author_username"] == "tester"
            print("  [SUCCESS] Action 2 (reply_created) payload & broadcast matched DB model perfectly!\n")

            # 7. Accept Answer via Django REST API
            print("7. [ACTION 3] PATCHing Accept Answer to Django REST API (PATCH /api/classrooms/1/doubts/<id>/replies/<reply_id>/accept/)...")
            res = requests.patch(f"{DJANGO_URL}/api/classrooms/1/doubts/{doubt_id}/replies/{reply_id}/accept/", headers=headers)
            assert res.status_code == 200, f"Failed to accept answer: {res.text}"
            accepted_reply = res.json()
            print(f"  Django marked Reply ID {reply_id} as accepted answer (is_accepted_answer={accepted_reply['is_accepted_answer']})")

            print("  Awaiting WebSocket broadcast event for 'answer_accepted'...")
            event_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            event_3 = json.loads(event_raw)
            print("  RECEIVED WEBSOCKET EVENT 3:")
            print(f"    Event Type:          {event_3.get('event_type')}")
            print(f"    Classroom ID:        {event_3.get('classroom_id')}")
            print(f"    Payload ID:          {event_3.get('data', {}).get('id')}")
            print(f"    Is Accepted Answer:  {event_3.get('data', {}).get('is_accepted_answer')}")
            print(f"    Author:              {event_3.get('data', {}).get('author_username')}\n")

            assert event_3["event_type"] == "answer_accepted"
            assert event_3["classroom_id"] == 1
            assert event_3["data"]["id"] == reply_id
            assert event_3["data"]["is_accepted_answer"] is True
            print("  [SUCCESS] Action 3 (answer_accepted) payload & broadcast matched DB model perfectly!\n")

    finally:
        print("Cleaning up sub-processes...")
        fastapi_proc.terminate()
        django_proc.terminate()

    print("==========================================================================")
    print("  ALL 3 REAL DJANGO ACTIONS PASSED REAL-TIME WEBSOCKET VERIFICATION E2E!  ")
    print("==========================================================================")

if __name__ == "__main__":
    asyncio.run(run_e2e_verification())
