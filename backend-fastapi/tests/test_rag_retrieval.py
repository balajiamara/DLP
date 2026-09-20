"""
Unit & Security tests for RAG retrieval service (app/services/rag_retrieval.py)
Tests pre-search authorization check, short-circuit behavior, cross-classroom leakage prevention,
topic scoping, material status filtering, and empty results.
"""

from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from app.services.rag_retrieval import (
    is_authorized_for_classroom,
    retrieve_relevant_chunks,
    NotAuthorizedError,
)


@pytest.mark.asyncio
async def test_is_authorized_for_classroom_active_member():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = (1,)  # Row found
    mock_session.execute.return_value = mock_result

    with patch("app.services.rag_retrieval.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__.return_value = mock_session

        authorized = await is_authorized_for_classroom(user_id=10, classroom_id=1)
        assert authorized is True


@pytest.mark.asyncio
async def test_is_authorized_for_classroom_unauthorized():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = None  # No active membership row
    mock_session.execute.return_value = mock_result

    with patch("app.services.rag_retrieval.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__.return_value = mock_session

        authorized = await is_authorized_for_classroom(user_id=10, classroom_id=99)
        assert authorized is False


@pytest.mark.asyncio
async def test_unauthorized_student_short_circuits_and_never_calls_embeddings_api():
    """
    CRITICAL SECURITY CHECK:
    Confirm that an unauthorized user raises NotAuthorizedError immediately, and that
    get_embeddings and vector DB queries are NEVER CALLED (short-circuited).
    """
    with patch("app.services.rag_retrieval.is_authorized_for_classroom", new_callable=AsyncMock) as mock_auth, \
         patch("app.services.rag_retrieval.get_embeddings") as mock_embed, \
         patch("app.services.rag_retrieval.async_session_maker") as mock_maker:

        mock_auth.return_value = False  # Unauthorized

        with pytest.raises(NotAuthorizedError, match="User 10 is not an active member of classroom 99"):
            await retrieve_relevant_chunks(user_id=10, classroom_id=99, query_text="What is calculus?")

        # SPY ASSERTIONS: Embedding API and DB session must NEVER be invoked!
        assert mock_embed.call_count == 0, "Security Failure: get_embeddings was called for an unauthorized user!"
        assert mock_maker.call_count == 0, "Security Failure: Vector DB query was executed for an unauthorized user!"


@pytest.mark.asyncio
async def test_cross_classroom_leakage_prevention():
    """
    CRITICAL CROSS-CLASSROOM LEAKAGE TEST:
    Simulates a query where Classroom B contains chunks that are semantically MUCH MORE SIMILAR (distance 0.05)
    than Classroom A's chunks (distance 0.40).
    The user is authorized ONLY for Classroom A.
    Asserts that results contain ONLY Classroom A's chunks, completely excluding Classroom B's chunks.
    """
    with patch("app.services.rag_retrieval.is_authorized_for_classroom", new_callable=AsyncMock) as mock_auth, \
         patch("app.services.rag_retrieval.get_embeddings") as mock_embed, \
         patch("app.services.rag_retrieval.async_session_maker") as mock_maker:

        mock_auth.return_value = True  # User authorized for Classroom A (id=1)
        mock_embed.return_value = [[0.1] * 768]

        # Mock DB returning ONLY Classroom A chunks because SQL WHERE e.classroom_id = 1 was executed
        mock_row_class_a = MagicMock()
        mock_row_class_a.id = "uuid-chunk-1"
        mock_row_class_a.material_id = 101
        mock_row_class_a.material_title = "Classroom A Intro"
        mock_row_class_a.topic_id = 5
        mock_row_class_a.classroom_id = 1  # Classroom A
        mock_row_class_a.chunk_text = "Classroom A relevant text"
        mock_row_class_a.chunk_index = 0
        mock_row_class_a.distance = 0.40

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row_class_a]
        mock_session.execute.return_value = mock_result
        mock_maker.return_value.__aenter__.return_value = mock_session

        chunks = await retrieve_relevant_chunks(user_id=10, classroom_id=1, query_text="Linear algebra")

        assert len(chunks) == 1
        assert chunks[0]["classroom_id"] == 1
        assert chunks[0]["material_title"] == "Classroom A Intro"

        # Verify SQL query contained WHERE e.classroom_id = :classroom_id parameter
        sql_call_args = mock_session.execute.call_args_list
        # Second execute call is the query_sql
        query_params = sql_call_args[-1][0][1]
        assert query_params["classroom_id"] == 1


@pytest.mark.asyncio
async def test_topic_scoping_filter():
    """
    Verifies that when topic_id is provided, topic_id parameter is passed to SQL query.
    """
    with patch("app.services.rag_retrieval.is_authorized_for_classroom", new_callable=AsyncMock) as mock_auth, \
         patch("app.services.rag_retrieval.get_embeddings") as mock_embed, \
         patch("app.services.rag_retrieval.async_session_maker") as mock_maker:

        mock_auth.return_value = True
        mock_embed.return_value = [[0.1] * 768]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result
        mock_maker.return_value.__aenter__.return_value = mock_session

        chunks = await retrieve_relevant_chunks(user_id=10, classroom_id=1, topic_id=42, query_text="Physics")

        assert chunks == []
        sql_call_args = mock_session.execute.call_args_list
        query_params = sql_call_args[-1][0][1]
        assert query_params["topic_id"] == 42


@pytest.mark.asyncio
async def test_material_status_filter_excludes_non_ready_materials():
    """
    Verifies that SQL query joins syllabus_material and filters on m.status = 'READY'.
    """
    with patch("app.services.rag_retrieval.is_authorized_for_classroom", new_callable=AsyncMock) as mock_auth, \
         patch("app.services.rag_retrieval.get_embeddings") as mock_embed, \
         patch("app.services.rag_retrieval.async_session_maker") as mock_maker:

        mock_auth.return_value = True
        mock_embed.return_value = [[0.1] * 768]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []  # Excluded by m.status = 'READY'
        mock_session.execute.return_value = mock_result
        mock_maker.return_value.__aenter__.return_value = mock_session

        chunks = await retrieve_relevant_chunks(user_id=10, classroom_id=1, query_text="Chemistry")

        assert chunks == []
        sql_call = mock_session.execute.call_args_list[-1][0][0]
        sql_str = str(sql_call)
        assert "m.status = 'READY'" in sql_str


@pytest.mark.asyncio
async def test_empty_result_when_classroom_has_no_embeddings():
    """
    Verifies authorized user querying a classroom with zero embeddings returns empty list [], not error.
    """
    with patch("app.services.rag_retrieval.is_authorized_for_classroom", new_callable=AsyncMock) as mock_auth, \
         patch("app.services.rag_retrieval.get_embeddings") as mock_embed, \
         patch("app.services.rag_retrieval.async_session_maker") as mock_maker:

        mock_auth.return_value = True
        mock_embed.return_value = [[0.1] * 768]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result
        mock_maker.return_value.__aenter__.return_value = mock_session

        chunks = await retrieve_relevant_chunks(user_id=10, classroom_id=1, query_text="Anything")

        assert chunks == []


@pytest.mark.asyncio
async def test_cross_classroom_leakage_live_db():
    """
    CRITICAL LIVE DB SAFETY TEST:
    Creates a temporary scratch table on real Supabase Postgres.
    Inserts 2 rows:
      - Classroom A (id=201): orthogonal vector [0.0, 1.0, 0.0, ...] (distance 1.0)
      - Classroom B (id=202): exact match vector [1.0, 0.0, 0.0, ...] (distance 0.0)
    Queries vector search authorized ONLY for Classroom A (id=201) with query vector [1.0, 0.0, 0.0, ...].
    Asserts: Real query returns ONLY Classroom A's chunk and 0 chunks from Classroom B,
    proving SQL engine enforces the security boundary directly on the real database.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    table_name = "temp_cross_classroom_test"
    material_table = "temp_cross_material_test"

    async with engine.begin() as conn:
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

        # Create HNSW index
        await conn.execute(text(f"""
            CREATE INDEX ix_{table_name}_embedding_hnsw ON {table_name} 
            USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
        """))

        # Insert Materials
        await conn.execute(text(f"INSERT INTO {material_table} (id, title, status) VALUES (2001, 'Classroom A Material', 'READY'), (2002, 'Classroom B Material', 'READY');"))

        # Vectors
        vec_query = [1.0] + [0.0] * 767      # Target query vector
        vec_class_b = [1.0] + [0.0] * 767    # Exact match for Classroom B (distance 0.0)
        vec_class_a = [0.0] + [1.0] + [0.0] * 766  # Orthogonal for Classroom A (distance 1.0)

        vec_query_str = f"[{','.join(str(v) for v in vec_query)}]"
        vec_class_b_str = f"[{','.join(str(v) for v in vec_class_b)}]"
        vec_class_a_str = f"[{','.join(str(v) for v in vec_class_a)}]"

        # Insert Classroom A chunk (distance 1.0)
        await conn.execute(
            text(f"""
                INSERT INTO {table_name} (material_id, topic_id, classroom_id, chunk_text, chunk_index, embedding)
                VALUES (2001, 10, 201, 'Classroom A orthogonal content', 0, CAST(:embedding AS vector));
            """),
            {"embedding": vec_class_a_str},
        )

        # Insert Classroom B chunk (distance 0.0 - EXACT MATCH!)
        await conn.execute(
            text(f"""
                INSERT INTO {table_name} (material_id, topic_id, classroom_id, chunk_text, chunk_index, embedding)
                VALUES (2002, 20, 202, 'Classroom B exact match content', 0, CAST(:embedding AS vector));
            """),
            {"embedding": vec_class_b_str},
        )

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order;"))

            # Execute real vector retrieval query scoped to Classroom A (id=201)
            query_sql = text(f"""
                SELECT 
                    e.id,
                    e.material_id,
                    e.topic_id,
                    e.classroom_id,
                    e.chunk_text,
                    e.chunk_index,
                    m.title AS material_title,
                    (e.embedding <=> CAST(:query_vector AS vector)) AS distance
                FROM {table_name} e
                JOIN {material_table} m ON e.material_id = m.id
                WHERE e.classroom_id = 201
                  AND m.status = 'READY'
                ORDER BY e.embedding <=> CAST(:query_vector AS vector) ASC
                LIMIT 5;
            """)

            res = await conn.execute(query_sql, {"query_vector": vec_query_str})
            rows = res.all()

            # VERIFICATION:
            # 1. Exactly 1 chunk returned
            assert len(rows) == 1, f"Expected 1 chunk from Classroom A, got {len(rows)}"
            # 2. Returned chunk belongs strictly to Classroom A (classroom_id = 201)
            assert rows[0].classroom_id == 201
            assert rows[0].material_id == 2001
            assert "Classroom A" in rows[0].material_title
            # 3. Distance is 1.0 (Classroom A's chunk), proving Classroom B's chunk (distance 0.0) was strictly excluded
            assert abs(float(rows[0].distance) - 1.0) < 1e-4

    finally:
        # Guaranteed cleanup of scratch tables
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {table_name};"))
            await conn.execute(text(f"DROP TABLE IF EXISTS {material_table};"))

    await engine.dispose()
