import asyncio
import sys
from google import genai
from google.genai import types
from sqlalchemy import text
from app.core.config import settings
from app.services.embeddings_client import get_embeddings
from app.db.session import async_session_maker, engine

def run_part1():
    print("=== PART 1: LIVE MODEL LISTING & PROOF ===")
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    models_list = list(client.models.list())
    all_names = [m.name for m in models_list]
    print(f"Total models returned by client.models.list(): {len(all_names)}")
    print("Full list of model names:")
    for name in sorted(all_names):
        print(f"  - {name}")

    print("\n1. Testing gemini-2.0-flash:")
    try:
        client.models.generate_content(model="gemini-2.0-flash", contents="hi")
        print("  Result: SUCCESS")
    except Exception as e:
        print(f"  Result Error: {e}")

    print("\n2. Testing gemini-2.5-flash:")
    try:
        client.models.generate_content(model="gemini-2.5-flash", contents="hi")
        print("  Result: SUCCESS")
    except Exception as e:
        print(f"  Result Error: {e}")

    print("\n3. Testing gemini-3.5-flash-lite with system_instruction:")
    try:
        resp_lite = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents="Say hello",
            config=types.GenerateContentConfig(system_instruction="You are a polite assistant.")
        )
        print(f"  Result Text: {resp_lite.text.strip()}")
    except Exception as e:
        print(f"  Result Error: {e}")

    print("\n4. Testing gemini-3.5-flash with system_instruction:")
    try:
        resp_flash = client.models.generate_content(
            model="gemini-3.5-flash",
            contents="Say hello",
            config=types.GenerateContentConfig(system_instruction="You are a polite assistant.")
        )
        print(f"  Result Text: {resp_flash.text.strip()}")
    except Exception as e:
        print(f"  Result Error: {e}")

async def run_part2():
    print("\n=== PART 2: EMPIRICAL DISTANCE VALIDATION ===")
    q_relevant = "What microservice and vector database does the Daily Learning Planner use?"
    q_unrelated = "What is the recipe for baking a traditional Italian sourdough pizza?"

    print(f"Relevant Query:   \"{q_relevant}\"")
    print(f"Unrelated Query:  \"{q_unrelated}\"")

    emb_rel = get_embeddings([q_relevant])[0]
    emb_unrel = get_embeddings([q_unrelated])[0]

    async with async_session_maker() as session:
        # Cosine distance to Material 8 chunks
        res_rel = await session.execute(
            text("SELECT chunk_index, chunk_text, (embedding <=> CAST(:vec AS vector)) as distance FROM embeddings WHERE material_id = 8 ORDER BY distance ASC LIMIT 1;"),
            {"vec": str(emb_rel)}
        )
        row_rel = res_rel.fetchone()

        res_unrel = await session.execute(
            text("SELECT chunk_index, chunk_text, (embedding <=> CAST(:vec AS vector)) as distance FROM embeddings WHERE material_id = 8 ORDER BY distance ASC LIMIT 1;"),
            {"vec": str(emb_unrel)}
        )
        row_unrel = res_unrel.fetchone()

        print("\n--- EMPIRICAL RESULTS FROM PRODUCTION DB ---")
        print(f"Relevant Query Distance:   {row_rel.distance:.4f}")
        print(f"Relevant Query Chunk Text:  \"{row_rel.chunk_text[:120]}...\"")
        print(f"Unrelated Query Distance:  {row_unrel.distance:.4f}")
        print(f"Unrelated Query Chunk Text: \"{row_unrel.chunk_text[:120]}...\"")
        print(f"Separation Delta:          {row_unrel.distance - row_rel.distance:.4f}")
        
        # Check if 0.65 threshold cleanly separates them
        threshold = 0.65
        print(f"\nEvaluating threshold MAX_RELEVANCE_DISTANCE = {threshold}:")
        print(f"  Relevant query distance ({row_rel.distance:.4f}) < {threshold}: {row_rel.distance < threshold} (Expected: True)")
        print(f"  Unrelated query distance ({row_unrel.distance:.4f}) < {threshold}: {row_unrel.distance < threshold} (Expected: False)")

    await engine.dispose()

if __name__ == "__main__":
    run_part1()
    asyncio.run(run_part2())
