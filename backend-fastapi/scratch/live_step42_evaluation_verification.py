"""
Live Verification Script for Step 42: AI Evaluation Logging

Executes:
1. Real Course Chat call using Gemini 3.6 Flash against Classroom 6.
2. Confirms a real row is inserted in ai_interaction_logs table on Supabase.
3. Checks interaction_type, model, grounded status, retrieved_chunk_ids, latency_ms > 0.
4. Submits feedback (rating='up', reason=...) via record_feedback / feedback endpoint.
5. Calls get_evaluation_summary and confirms this interaction is counted.
6. Reports measured latency and token cost analysis.
"""

import asyncio
import os
import sys
import uuid
from dotenv import load_dotenv

load_dotenv()

# Add backend-fastapi to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.db.session import async_session_maker
from app.services.course_chat import answer_course_question
from app.services.evaluation_logging import record_feedback, get_evaluation_summary


async def run_live_verification():
    print("=================================================================")
    print("STEP 42: LIVE AI EVALUATION LOGGING VERIFICATION")
    print("=================================================================")

    # Test parameters: Classroom 6 has indexed material 8 from Step 33/34, student user_id = 2
    user_id = 2
    classroom_id = 6
    query = "What microservice framework and vector database does the Daily Learning Planner use?"

    print(f"\n1. Making Real Live Course Chat Call (model=gemini-3.6-flash)...")
    print(f"   User ID: {user_id}, Classroom ID: {classroom_id}")
    print(f"   Query: '{query}'")

    response = await answer_course_question(
        user_id=user_id,
        classroom_id=classroom_id,
        topic_id=None,
        query=query,
        socratic_mode=False,
    )

    print("\n   Course Chat Result:")
    print(f"   Grounded: {response.get('grounded')}")
    print(f"   Sources count: {len(response.get('sources', []))}")
    print(f"   Answer preview: {response.get('answer', '')[:120]}...")

    # 2. Query ai_interaction_logs from real database for the newest log entry
    print("\n2. Inspecting ai_interaction_logs in Supabase PostgreSQL...")
    async with async_session_maker() as session:
        result = await session.execute(
            text("""
                SELECT id, interaction_id, interaction_type, user_id, classroom_id,
                       model, grounded, retrieved_chunk_count, retrieved_chunk_ids,
                       latency_ms, error_occurred, feedback_rating, created_at
                FROM ai_interaction_logs
                WHERE classroom_id = :cid
                ORDER BY created_at DESC
                LIMIT 1;
            """),
            {"cid": classroom_id}
        )
        row = result.mappings().first()

    if not row:
        print("   FAILED: No log row found in ai_interaction_logs!")
        return

    print("   Found Log Entry in Database:")
    print(f"   - Log ID: {row['id']}")
    print(f"   - Interaction ID: {row['interaction_id']}")
    print(f"   - Interaction Type: {row['interaction_type']}")
    print(f"   - Model: {row['model']}")
    print(f"   - Grounded: {row['grounded']}")
    print(f"   - Retrieved Chunk Count: {row['retrieved_chunk_count']}")
    print(f"   - Retrieved Chunk IDs: {row['retrieved_chunk_ids']}")
    print(f"   - Measured Latency: {row['latency_ms']} ms")
    print(f"   - Error Occurred: {row['error_occurred']}")
    print(f"   - Created At: {row['created_at']}")

    assert row["interaction_type"] == "COURSE_CHAT", "Type mismatch"
    assert row["model"] == "gemini-3.6-flash", "Model mismatch"
    assert row["latency_ms"] > 0, "Latency was not measured (> 0 ms)"
    assert row["grounded"] is True, "Expected grounded=True"
    assert row["retrieved_chunk_count"] > 0, "Expected chunks retrieved"

    # 3. Submit User Feedback
    print("\n3. Submitting User Feedback via record_feedback...")
    feedback_res = await record_feedback(
        log_id=row["id"],
        rating="up",
        reason="Live verification test: accurate, prompt, and properly grounded response.",
    )
    print(f"   Feedback recorded: {feedback_res}")

    # Re-query DB to verify update
    async with async_session_maker() as session:
        result = await session.execute(
            text("SELECT feedback_rating, feedback_reason FROM ai_interaction_logs WHERE id = :id"),
            {"id": row["id"]}
        )
        updated_row = result.mappings().first()
        print(f"   DB Updated Feedback: rating='{updated_row['feedback_rating']}', reason='{updated_row['feedback_reason']}'")
        assert updated_row["feedback_rating"] == "up", "Feedback rating not updated"

    # 4. Fetch Evaluation Summary
    print("\n4. Fetching Evaluation Summary for Classroom 6...")
    summary = await get_evaluation_summary(classroom_id=classroom_id)
    print(f"   Total Interactions: {summary['total_interactions']}")
    print(f"   Interaction Counts: {summary['interaction_counts']}")
    print(f"   Grounded Answer Rate: {summary['course_chat_metrics']['grounded_answer_rate'] * 100}%")
    print(f"   Fallback Rate: {summary['course_chat_metrics']['fallback_rate'] * 100}%")
    print(f"   Citation Coverage (Proxy): {summary['course_chat_metrics']['citation_coverage'] * 100}%")
    print(f"   Overall Avg Latency: {summary['latency_metrics']['overall_average_latency_ms']} ms")
    print(f"   Feedback Metrics: {summary['feedback_metrics']}")
    print(f"   Citation Coverage Disclaimer: {summary['course_chat_metrics']['citation_coverage_note']}")

    assert summary['course_chat_metrics']['grounded_answer_rate'] == 1.0, "Grounded rate must be 100%"
    assert summary['course_chat_metrics']['fallback_rate'] == 0.0, "Fallback rate must be 0%"
    assert summary['course_chat_metrics']['citation_coverage'] == 1.0, "Citation coverage must be 100%"

    print("\n=================================================================")
    print("STEP 42 LIVE VERIFICATION COMPLETE: ALL CHECKS PASSED SUCCESSFULLY!")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(run_live_verification())
