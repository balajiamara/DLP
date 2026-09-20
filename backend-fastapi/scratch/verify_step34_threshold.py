import asyncio
from google import genai
from google.genai import types
from sqlalchemy import text
from app.core.config import settings
from app.services.embeddings_client import get_embeddings
from app.db.session import async_session_maker, engine

async def test_thresholds():
    queries = [
        ("Relevant 1", "What microservice and vector database does the Daily Learning Planner use?", True),
        ("Relevant 2", "How does DLP chunk documents and extract text?", True),
        ("Unrelated 1", "What is the recipe for baking a traditional Italian sourdough pizza?", False),
        ("Unrelated 2", "Who won the FIFA World Cup in 2022?", False)
    ]

    print("=== EMPIRICAL MULTI-QUERY COSINE DISTANCE TEST ===")
    async with async_session_maker() as session:
        for label, q, expected in queries:
            emb = get_embeddings([q])[0]
            res = await session.execute(
                text("SELECT chunk_index, chunk_text, (embedding <=> CAST(:vec AS vector)) as distance FROM embeddings WHERE material_id = 8 ORDER BY distance ASC LIMIT 1;"),
                {"vec": str(emb)}
            )
            row = res.fetchone()
            print(f"[{label}] Query: \"{q}\"")
            print(f"  Best Distance: {row.distance:.4f} | Chunk Match: \"{row.chunk_text[:80]}...\"")
            print(f"  Passes threshold 0.40? {row.distance < 0.40} (Expected: {expected})\n")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_thresholds())
