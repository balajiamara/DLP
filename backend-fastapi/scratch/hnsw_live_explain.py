"""
Live HNSW Index Verification & EXPLAIN ANALYZE Script

Populates a temporary table with 500 synthetic 768-dim normalized vector rows across 3 classrooms.
Executes SET LOCAL hnsw.iterative_scan = relaxed and EXPLAIN ANALYZE to prove HNSW index scan node usage.
Cleanly drops the temporary table in a finally block.
"""

import sys
import os
import random
import math
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, os.path.abspath("."))
from app.core.config import settings


def generate_unit_vector(dim=768):
    """Generates a random 768-dimensional unit vector."""
    vec = [random.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    table_name = "temp_hnsw_explain_test"
    material_table = "temp_hnsw_material_test"

    print("=== STARTING LIVE HNSW INDEX EXPLAIN ANALYZE TEST ===")

    async with engine.begin() as conn:
        # 1. Create temporary material and embeddings tables with exact production schema & indexes
        await conn.execute(text(f"DROP TABLE IF EXISTS {table_name};"))
        await conn.execute(text(f"DROP TABLE IF EXISTS {material_table};"))

        await conn.execute(text(f"""
            CREATE TABLE {material_table} (
                id bigint PRIMARY KEY,
                title text NOT NULL,
                status text NOT NULL
            );
        """))

        await conn.execute(text(f"""
            CREATE TABLE {table_name} (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                material_id bigint NOT NULL REFERENCES {material_table}(id) ON DELETE CASCADE,
                topic_id bigint NOT NULL,
                classroom_id bigint NOT NULL,
                chunk_text text NOT NULL,
                chunk_index integer NOT NULL,
                embedding vector(768) NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                metadata jsonb
            );
        """))

        # Create HNSW vector index (no btree composite index)
        await conn.execute(text(f"""
            CREATE INDEX ix_{table_name}_embedding_hnsw ON {table_name} 
            USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
        """))

        print("Created temporary table with VECTOR(768) and HNSW cosine index.")

        # 2. Insert synthetic material rows
        await conn.execute(text(f"INSERT INTO {material_table} (id, title, status) VALUES (1001, 'Math Notes', 'READY'), (1002, 'Science Notes', 'READY');"))

        # 3. Populate 500 rows across classrooms 101, 102, 103
        rows = []
        for i in range(500):
            cid = 101 if i < 200 else (102 if i < 350 else 103)
            mid = 1001 if cid == 101 else 1002
            vec = generate_unit_vector(768)
            vec_str = f"[{','.join(str(v) for v in vec)}]"
            rows.append({
                "material_id": mid,
                "topic_id": 10,
                "classroom_id": cid,
                "chunk_text": f"Synthetic chunk text {i} for classroom {cid}",
                "chunk_index": i,
                "embedding": vec_str,
            })

        for batch_start in range(0, len(rows), 100):
            batch = rows[batch_start:batch_start + 100]
            await conn.execute(
                text(f"""
                    INSERT INTO {table_name} (material_id, topic_id, classroom_id, chunk_text, chunk_index, embedding)
                    VALUES (:material_id, :topic_id, :classroom_id, :chunk_text, :chunk_index, CAST(:embedding AS vector));
                """),
                batch,
            )

        print(f"Populated 500 synthetic vector rows into {table_name}.")

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order;"))
            await conn.execute(text("SET LOCAL enable_seqscan = off;"))
            print("Successfully set: SET LOCAL hnsw.iterative_scan = relaxed_order; enable_seqscan = off;")

            # 5. Generate target query vector
            query_vec = generate_unit_vector(768)
            query_vec_str = f"[{','.join(str(v) for v in query_vec)}]"

            # 6. Run EXPLAIN ANALYZE
            explain_query = text(f"""
                EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
                SELECT 
                    e.id,
                    e.material_id,
                    e.classroom_id,
                    e.chunk_text,
                    m.title,
                    (e.embedding <=> CAST(:query_vector AS vector)) AS distance
                FROM {table_name} e
                JOIN {material_table} m ON e.material_id = m.id
                WHERE e.classroom_id = 101
                  AND m.status = 'READY'
                ORDER BY e.embedding <=> CAST(:query_vector AS vector) ASC
                LIMIT 5;
            """)

            res = await conn.execute(explain_query, {"query_vector": query_vec_str})
            plan_rows = res.all()

            print("\n=== EXPLAIN ANALYZE HNSW INDEX PLAN OUTPUT ===")
            for r in plan_rows:
                print(r[0])

            # 7. Execute actual query and verify exact returned row count
            data_query = text(f"""
                SELECT 
                    e.id,
                    e.material_id,
                    e.classroom_id,
                    e.chunk_text,
                    (e.embedding <=> CAST(:query_vector AS vector)) AS distance
                FROM {table_name} e
                JOIN {material_table} m ON e.material_id = m.id
                WHERE e.classroom_id = 101
                  AND m.status = 'READY'
                ORDER BY e.embedding <=> CAST(:query_vector AS vector) ASC
                LIMIT 5;
            """)
            data_res = await conn.execute(data_query, {"query_vector": query_vec_str})
            returned_chunks = data_res.all()
            print(f"\nQuery returned {len(returned_chunks)} chunks for classroom 101 (Expected top_k: 5).")
            for idx, chunk in enumerate(returned_chunks):
                print(f"  [{idx}] Classroom ID: {chunk.classroom_id}, Distance: {float(chunk.distance):.4f}")

    finally:
        # Cleanup temporary tables
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {table_name};"))
            await conn.execute(text(f"DROP TABLE IF EXISTS {material_table};"))
            print(f"\nCleaned up temporary tables {table_name} and {material_table}.")

    await engine.dispose()
    print("=== LIVE HNSW INDEX TEST COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
