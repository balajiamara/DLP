"""
Live end-to-end verification script for Step 43a: Backend Streaming Chat Support.
Spins up FastAPI on port 8019 via Uvicorn and tests:
1. Grounded course chat streaming with real Gemini 3.6 Flash.
2. Fallback course chat streaming (out-of-scope query).
3. General chat streaming.
4. Database telemetry verification in ai_interaction_logs.
"""

import os
import sys
import time
import json
import asyncio
import httpx
import uvicorn
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.core.config import settings
from app.db.session import async_session_maker
from app.db.models import AIInteractionLog
from sqlalchemy import select, desc

HEADERS = {
    "X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET,
    "Content-Type": "application/json",
}


async def parse_async_sse_stream(response):
    events = []
    chunk_deltas = []
    print("\n--- Reading SSE Stream ---")
    start_t = time.perf_counter()

    async for line in response.aiter_lines():
        if not line:
            continue
        line_str = line.strip()
        if line_str.startswith("data: "):
            payload_str = line_str[len("data: "):]
            event = json.loads(payload_str)
            elapsed = (time.perf_counter() - start_t) * 1000
            events.append(event)
            if event.get("type") == "chunk":
                delta = event.get("delta", "")
                chunk_deltas.append(delta)
                print(f"  [T + {elapsed:6.1f}ms] CHUNK: {repr(delta)}")
            elif event.get("type") == "done":
                print(f"  [T + {elapsed:6.1f}ms] DONE: grounded={event.get('grounded')}, sources={len(event.get('sources', []))}, interaction_id={event.get('interaction_id')}")
            elif event.get("type") == "error":
                print(f"  [T + {elapsed:6.1f}ms] ERROR: {event.get('detail')}")

    return events, "".join(chunk_deltas)


async def check_telemetry_logged(expected_type):
    async with async_session_maker() as session:
        query = (
            select(AIInteractionLog)
            .where(AIInteractionLog.interaction_type == expected_type)
            .order_by(desc(AIInteractionLog.created_at))
            .limit(1)
        )
        result = await session.execute(query)
        record = result.scalars().first()
        return record


async def run_verification():
    port = 8019
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    await asyncio.sleep(1.5)

    base_url = f"http://127.0.0.1:{port}"

    print("=================================================================")
    print("STEP 43a: LIVE END-TO-END STREAMING VERIFICATION")
    print("=================================================================")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Course Mode Grounded Stream (Real call)
            print("\n1. Testing POST /chat/course/stream (Grounded)...")
            payload_grounded = {
                "student_user_id": 3,
                "classroom_id": 6,
                "query": "What is the Daily Learning Planner document pipeline test?",
                "socratic_mode": False,
            }
            async with client.stream(
                "POST", f"{base_url}/chat/course/stream", json=payload_grounded, headers=HEADERS
            ) as resp:
                assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
                assert "text/event-stream" in resp.headers.get("content-type", "")
                events, full_answer = await parse_async_sse_stream(resp)

            assert any(e.get("type") == "chunk" for e in events), "Expected chunk events"
            assert any(e.get("type") == "done" and e.get("grounded") is True for e in events), "Expected done event with grounded=True"
            print(f"-> Full Reconstructed Answer ({len(full_answer)} chars):\n{full_answer[:200]}...")

            # 2. Course Mode Fallback Stream
            print("\n2. Testing POST /chat/course/stream (Fallback - Out of Scope Query)...")
            payload_fallback = {
                "student_user_id": 3,
                "classroom_id": 6,
                "query": "What is quantum gravity on Jupiter?",
                "socratic_mode": False,
            }
            async with client.stream(
                "POST", f"{base_url}/chat/course/stream", json=payload_fallback, headers=HEADERS
            ) as resp_fb:
                assert resp_fb.status_code == 200, f"Expected 200, got {resp_fb.status_code}"
                events_fb, full_answer_fb = await parse_async_sse_stream(resp_fb)

            assert any(e.get("type") == "done" and e.get("grounded") is False for e in events_fb), "Expected done event with grounded=False"
            print(f"-> Fallback Response verified: {repr(full_answer_fb)}")

            # 3. General Mode Stream
            print("\n3. Testing POST /chat/general/stream...")
            payload_general = {
                "student_user_id": 3,
                "classroom_id": 6,
                "query": "Explain what an algorithm is in one short sentence.",
                "socratic_mode": False,
            }
            async with client.stream(
                "POST", f"{base_url}/chat/general/stream", json=payload_general, headers=HEADERS
            ) as resp_gen:
                assert resp_gen.status_code == 200, f"Expected 200, got {resp_gen.status_code}"
                events_gen, full_answer_gen = await parse_async_sse_stream(resp_gen)

            assert any(e.get("type") == "done" and e.get("grounded") is False for e in events_gen), "Expected done event with grounded=False"
            print(f"-> General Answer: {repr(full_answer_gen)}")

        # 4. Check Telemetry in Database
        print("\n4. Verifying telemetry in ai_interaction_logs table...")
        log_record = await check_telemetry_logged("COURSE_CHAT")
        assert log_record is not None, "Expected log record in database"
        print(f"-> Latest COURSE_CHAT log found:")
        print(f"   ID: {log_record.id}")
        print(f"   Model: {log_record.model}")
        print(f"   Latency: {log_record.latency_ms}ms")
        print(f"   Grounded: {log_record.grounded}")
        print(f"   Retrieved Chunks: {log_record.retrieved_chunk_count}")
        print(f"   Answer Text: {repr(log_record.answer_text[:80])}...")

        print("\n=================================================================")
        print("ALL LIVE STREAMING VERIFICATIONS PASSED SUCCESSFULLY!")
        print("=================================================================")

    finally:
        server.should_exit = True
        await server_task


if __name__ == "__main__":
    asyncio.run(run_verification())
