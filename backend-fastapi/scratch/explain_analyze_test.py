"""
Runs EXPLAIN ANALYZE on RAG Retrieval Query against live Supabase PostgreSQL database
Verifies index usage (composite index ix_embeddings_classroom_topic / HNSW index) and hnsw.iterative_scan setting.
"""

import sys
import os
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, os.path.abspath("."))
from app.core.config import settings


async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        print("=== Checking pgvector settings & Running EXPLAIN ANALYZE ===")

        # 1. Test SET LOCAL hnsw.iterative_scan = relaxed
        try:
            await conn.execute(text("SET LOCAL hnsw.iterative_scan = relaxed;"))
            print("Successfully executed: SET LOCAL hnsw.iterative_scan = relaxed;")
        except Exception as e:
            print(f"hnsw.iterative_scan setting notice: {e}")

        # 2. Construct sample 768-dim query vector
        sample_vec = f"[{','.join(['0.01'] * 768)}]"

        # 3. EXPLAIN ANALYZE query
        explain_sql = text("""
            EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
            SELECT 
                e.id,
                e.material_id,
                e.topic_id,
                e.classroom_id,
                e.chunk_text,
                e.chunk_index,
                m.title AS material_title,
                (e.embedding <=> CAST(:query_vector AS vector)) AS distance
            FROM embeddings e
            JOIN syllabus_material m ON e.material_id = m.id
            WHERE e.classroom_id = 6
              AND m.status = 'READY'
            ORDER BY e.embedding <=> CAST(:query_vector AS vector) ASC
            LIMIT 5;
        """)

        result = await conn.execute(explain_sql, {"query_vector": sample_vec})
        rows = result.all()

        print("\n--- EXPLAIN ANALYZE OUTPUT ---")
        for r in rows:
            print(r[0])

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
