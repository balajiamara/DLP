import asyncio
from app.services.general_chat import answer_general_question
from app.db.session import engine

async def run_live_general_verification():
    print("=========================================================")
    print("  SUPERVISED LIVE E2E VERIFICATION: GENERAL CHAT MODE   ")
    print("=========================================================\n")

    user_id = 2
    classroom_id = 6
    query = "Explain the concept of quantum superposition in simple terms."

    print(f"User ID: {user_id} | Classroom ID: {classroom_id}")
    print(f"Query: \"{query}\"\n")

    result = await answer_general_question(
        user_id=user_id,
        classroom_id=classroom_id,
        query=query,
    )

    print("--- LIVE RESPONSE ---")
    print(f"Grounded: {result['grounded']}")
    print(f"Sources:  {result['sources']}")
    print(f"Answer:\n{result['answer']}\n")

    # Assertions
    assert result["grounded"] is False, "Expected grounded=False for General Mode"
    assert result["sources"] == [], "Expected sources=[] for General Mode"
    assert len(result["answer"]) > 50, "Expected substantive LLM response"
    assert "quantum" in result["answer"].lower() or "superposition" in result["answer"].lower(), "Expected quantum explanation"

    print("=========================================================")
    print("  LIVE GENERAL CHAT MODE VERIFICATION PASSED CLEANLY!    ")
    print("=========================================================")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_live_general_verification())
