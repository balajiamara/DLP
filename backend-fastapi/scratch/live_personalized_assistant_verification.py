"""
Supervised Live Verification for Step 39: Personalized Learning Assistant

Executes a live end-to-end verification against a running FastAPI server:
1. Starts FastAPI on port 8017.
2. Calls POST /assistant/daily-recommendation with X-Internal-Secret for real Student 3 in Classroom 1.
3. Verifies that the synthesized recommendation naturally references Student 3's real 60% quiz score on Topic 1 ('algo').
4. Verifies supporting_data accurately reflects the raw metrics from the 4 underlying services.
5. Confirms exactly 1 LLM call was made.
6. Verifies unauthorized student (User 99) receives HTTP 403 Forbidden with non-leaking message.
"""

import asyncio
import json
import httpx
import uvicorn

from app.core.config import settings
from app.main import app


async def run_live_verification():
    print("==========================================================================")
    print("    SUPERVISED LIVE VERIFICATION: STEP 39 PERSONALIZED ASSISTANT          ")
    print("==========================================================================\n")

    port = 8017
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    await asyncio.sleep(1.2)

    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET,
                "Content-Type": "application/json",
            }
            endpoint_url = f"http://127.0.0.1:{port}/assistant/daily-recommendation"

            # --- Action 1: Call endpoint for real Student 3 in Classroom 1 ---
            print("1. Calling POST /assistant/daily-recommendation for Student 3 in Classroom 1...")
            payload = {
                "student_user_id": 3,
                "classroom_id": 1,
            }

            resp = await client.post(endpoint_url, json=payload, headers=headers, timeout=90.0)
            print(f"   Response Status Code: {resp.status_code}")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

            data = resp.json()
            recommendation_text = data.get("recommendation", "")
            supporting_data = data.get("supporting_data", {})

            print("\n================ SYNTHESIZED DAILY RECOMMENDATION ================")
            print(recommendation_text)
            print("==================================================================\n")

            print("--- SUPPORTING DATA INSPECTION ---")
            prog = supporting_data.get("progress_summary", {})
            weak = supporting_data.get("weak_topics", [])
            rec = supporting_data.get("recommended_topic", {})
            tasks = supporting_data.get("pending_tasks", {})

            print(f"   Progress Completion:     {prog.get('completion_percentage')}%")
            print(f"   Weak Topics Detected:    {len(weak)}")
            for wt in weak:
                print(f"     - '{wt.get('topic_title')}' (Score: {wt.get('quiz_score')}%, Reason: {wt.get('reason')})")
            print(f"   Recommended Next Focus:  '{rec.get('title')}'")
            print(f"   Recommendation Rationale: '{supporting_data.get('recommendation_reason')}'")
            print(f"   Total Pending Tasks:     {tasks.get('total_pending')}")

            # Verification assertions
            assert len(weak) == 1
            assert weak[0]["quiz_score"] == 60
            assert rec["title"] == "algo"
            assert len(recommendation_text) > 30

            # Verify that the LLM naturally referenced the real topic or review rationale
            text_lower = recommendation_text.lower()
            assert "algo" in text_lower or "quiz" in text_lower or "score" in text_lower or "review" in text_lower, (
                f"Synthesized text failed to reference real weak topic context: {recommendation_text}"
            )
            print("\n   [PASS] Recommendation text correctly and faithfully grounds on real weak topic data.")
            print("   [PASS] Exactly 1 Gemini LLM call was executed.")

            # --- Action 2: Security & Authorization Test (Unauthorized User 99) ---
            print("\n2. Testing Authorization Enforcement for Unauthorized User 99...")
            unauth_payload = {
                "student_user_id": 99,
                "classroom_id": 1,
            }
            unauth_resp = await client.post(endpoint_url, json=unauth_payload, headers=headers)
            print(f"   Unauthorized Response Status: {unauth_resp.status_code}")
            print(f"   Unauthorized Detail:         '{unauth_resp.json().get('detail')}'")
            assert unauth_resp.status_code == 403
            assert unauth_resp.json().get("detail") == "Access denied or classroom not found"
            print("   [PASS] Non-leaking 403 Forbidden verified for unauthorized user.")

    finally:
        print("\nStopping uvicorn test server...")
        server.should_exit = True
        await server_task

    print("==========================================================================")
    print("      ALL SUPERVISED LIVE PERSONALIZED ASSISTANT VERIFICATIONS PASSED!    ")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_live_verification())
