import asyncio
import sys
from unittest.mock import patch
from app.services.course_chat import answer_course_question, UNGROUNDED_FALLBACK_ANSWER
from app.services.chat_client import generate_answer
from app.db.session import engine

async def run_live_verification():
    print("=========================================================")
    print("   SUPERVISED LIVE E2E VERIFICATION: STEP 34 CHAT ROUTE ")
    print("=========================================================\n")

    user_id = 2
    classroom_id = 6

    # ----------------------------------------------------
    # TEST 1: ANSWERABLE / GROUNDED QUERY (Real Gemini API Call)
    # ----------------------------------------------------
    q_answerable = "What microservice framework and vector database does the Daily Learning Planner use?"
    print(f"--- TEST 1: Answerable Query ---")
    print(f"User ID: {user_id} | Classroom ID: {classroom_id}")
    print(f"Query: \"{q_answerable}\"")

    res1 = await answer_course_question(
        user_id=user_id,
        classroom_id=classroom_id,
        topic_id=None,
        query=q_answerable,
    )

    print("\nResult 1:")
    print(f"  Grounded: {res1['grounded']}")
    print(f"  Answer:   \"{res1['answer']}\"")
    print(f"  Sources:  {res1['sources']}\n")

    assert res1["grounded"] is True, "Test 1 failed: Expected grounded=True"
    assert len(res1["sources"]) > 0, "Test 1 failed: Expected sources attribution"
    assert res1["sources"][0]["material_id"] == 8, "Test 1 failed: Expected material_id 8"

    # ----------------------------------------------------
    # TEST 2: UNANSWERABLE / UNGROUNDED QUERY (Must Short-Circuit!)
    # ----------------------------------------------------
    q_unanswerable = "What is the recipe for baking a traditional Italian sourdough pizza?"
    print(f"--- TEST 2: Unanswerable Query ---")
    print(f"User ID: {user_id} | Classroom ID: {classroom_id}")
    print(f"Query: \"{q_unanswerable}\"")

    # Wrap generate_answer with a spy to confirm ZERO real LLM calls are made
    with patch("app.services.course_chat.generate_answer", wraps=generate_answer) as spy_chat_call:
        res2 = await answer_course_question(
            user_id=user_id,
            classroom_id=classroom_id,
            topic_id=None,
            query=q_unanswerable,
        )

        print("\nResult 2:")
        print(f"  Grounded: {res2['grounded']}")
        print(f"  Answer:   \"{res2['answer']}\"")
        print(f"  Sources:  {res2['sources']}")
        print(f"  Real LLM Generation Call Count: {spy_chat_call.call_count}\n")

        assert res2["grounded"] is False, "Test 2 failed: Expected grounded=False"
        assert res2["answer"] == UNGROUNDED_FALLBACK_ANSWER, f"Test 2 failed: Expected fallback answer '{UNGROUNDED_FALLBACK_ANSWER}'"
        assert res2["sources"] == [], "Test 2 failed: Expected empty sources"
        assert spy_chat_call.call_count == 0, f"Test 2 CRITICAL FAILURE: Expected 0 LLM calls, got {spy_chat_call.call_count}!"

    print("=========================================================")
    print("   ALL SUPERVISED LIVE VERIFICATION CHECKS PASSED CLEAN! ")
    print("=========================================================")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_live_verification())
