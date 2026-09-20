import uuid
import pytest
import pytest_asyncio
from alembic.script import ScriptDirectory
from alembic.config import Config
from sqlalchemy import Table, BigInteger, Text, Integer, DateTime, ForeignKey, Index, text
from sqlalchemy.exc import DBAPIError, IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.db.models import Base, Embedding
from app.core.config import get_settings

settings = get_settings()


def test_alembic_script_structure_and_revision():
    """Test 1: Verify Alembic migration head points to 003_ai_interaction_logs."""
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    head_revision = script.get_current_head()
    assert head_revision == "003_ai_interaction_logs"
    rev_003 = script.get_revision("003_ai_interaction_logs")
    assert rev_003.down_revision == "002_alter_embedding_dimension"


def test_embedding_model_mapping():
    """Test 2: Verify Embedding model maps attributes correctly resolving metadata conflict."""
    assert Embedding.__tablename__ == "embeddings"
    assert hasattr(Embedding, "extra_data")
    assert Embedding.extra_data.property.columns[0].name == "metadata"
    assert hasattr(Base, "metadata")
    assert "embeddings" in Base.metadata.tables


def test_embedding_table_schema_definition():
    """Test 3: Verify table schema definition matching FKs, NOT NULLs, and Vector(768)."""
    table: Table = Base.metadata.tables["embeddings"]
    columns = {col.name: col for col in table.columns}

    assert "id" in columns
    assert "material_id" in columns
    assert "topic_id" in columns
    assert "classroom_id" in columns
    assert "chunk_text" in columns
    assert "chunk_index" in columns
    assert "embedding" in columns
    assert "created_at" in columns
    assert "metadata" in columns

    assert not columns["material_id"].nullable
    assert not columns["topic_id"].nullable
    assert not columns["classroom_id"].nullable
    assert not columns["chunk_text"].nullable
    assert not columns["chunk_index"].nullable
    assert not columns["embedding"].nullable
    assert not columns["created_at"].nullable

    fk_targets = {list(col.foreign_keys)[0].target_fullname for col in table.columns if col.foreign_keys}
    assert "syllabus_material.id" in fk_targets
    assert "syllabus_topic.id" in fk_targets
    assert "classrooms_classroom.id" in fk_targets


def test_embedding_indexes_definition():
    """Test 4: Verify composite authorization pre-filtering and HNSW vector indexes exist."""
    table: Table = Base.metadata.tables["embeddings"]
    indexes = {idx.name: idx for idx in table.indexes}

    assert "ix_embeddings_classroom_topic" in indexes
    assert "ix_embeddings_embedding_hnsw" in indexes

    composite_cols = [col.name for col in indexes["ix_embeddings_classroom_topic"].columns]
    assert composite_cols == ["classroom_id", "topic_id"]

    hnsw_idx = indexes["ix_embeddings_embedding_hnsw"]
    assert hnsw_idx.dialect_options["postgresql"]["using"] == "hnsw"
    assert hnsw_idx.dialect_options["postgresql"]["ops"] == {"embedding": "vector_cosine_ops"}


@pytest.mark.asyncio
async def test_vector_dimension_constraint_live():
    """
    Test 5 (Live DB test using isolated temporary table):
    Creates temporary table 'test_embeddings_constraint_check' with VECTOR(768).
    Inserts a valid 768-dim vector (succeeds), then attempts inserting an invalid 1536-dim vector,
    asserting vector dimension error is raised, and drops the temporary table in finally block.
    """
    test_engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"statement_cache_size": 0},
    )
    temp_table_name = "test_embeddings_constraint_check"
    try:
        async with AsyncSession(test_engine) as session:
            # 1. Enable vector extension & create temporary test table with VECTOR(768)
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await session.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {temp_table_name} (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    material_id BIGINT NOT NULL,
                    topic_id BIGINT NOT NULL,
                    classroom_id BIGINT NOT NULL,
                    chunk_text TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    embedding VECTOR(768) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
                    metadata JSONB
                );
            """))
            await session.commit()

            # 2. Valid 768-dim vector insertion succeeds
            valid_vector_768 = [0.05] * 768
            valid_uuid = str(uuid.uuid4())
            insert_valid = text(f"""
                INSERT INTO {temp_table_name} (id, material_id, topic_id, classroom_id, chunk_text, chunk_index, embedding)
                VALUES (:id, 1, 1, 1, 'Valid 768-dim chunk', 0, :vec);
            """)
            await session.execute(insert_valid, {"id": valid_uuid, "vec": str(valid_vector_768)})
            await session.commit()

            # 3. Attempt inserting invalid 1536-dim vector against VECTOR(768) column -> expect dimension error
            invalid_vector_1536 = [0.1] * 1536
            invalid_uuid = str(uuid.uuid4())
            with pytest.raises((DBAPIError, StatementError, IntegrityError)):
                insert_invalid = text(f"""
                    INSERT INTO {temp_table_name} (id, material_id, topic_id, classroom_id, chunk_text, chunk_index, embedding)
                    VALUES (:id, 1, 1, 1, 'Bad 1536-dim vector chunk', 1, :vec);
                """)
                await session.execute(insert_invalid, {"id": invalid_uuid, "vec": str(invalid_vector_1536)})
                await session.commit()
            await session.rollback()

            # Clean up valid inserted row
            await session.execute(text(f"DELETE FROM {temp_table_name} WHERE id = :id;"), {"id": valid_uuid})
            await session.commit()
    finally:
        # 4. Clean drop of temporary table
        async with AsyncSession(test_engine) as session:
            await session.execute(text(f"DROP TABLE IF EXISTS {temp_table_name};"))
            await session.commit()
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_foreign_key_constraint_live():
    """
    Test 6 (Live DB test using isolated temporary table):
    Creates temporary table 'test_embeddings_constraint_check' with VECTOR(768).
    Inserts invalid FK classroom_id=9999999, asserts foreign key violation error is raised,
    and drops the temporary table in finally block.
    """
    test_engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"statement_cache_size": 0},
    )
    temp_table_name = "test_embeddings_constraint_check"
    try:
        async with AsyncSession(test_engine) as session:
            # 1. Enable vector extension & create temporary test table with FK constraints
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await session.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {temp_table_name} (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    material_id BIGINT NOT NULL REFERENCES syllabus_material(id) ON DELETE CASCADE,
                    topic_id BIGINT NOT NULL REFERENCES syllabus_topic(id) ON DELETE CASCADE,
                    classroom_id BIGINT NOT NULL REFERENCES classrooms_classroom(id) ON DELETE CASCADE,
                    chunk_text TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    embedding VECTOR(768) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
                    metadata JSONB
                );
            """))
            await session.commit()

            # 2. Attempt inserting row with non-existent classroom_id=9999999
            invalid_uuid = str(uuid.uuid4())
            valid_vector = [0.05] * 768
            with pytest.raises((IntegrityError, DBAPIError)):
                insert_bad_fk = text(f"""
                    INSERT INTO {temp_table_name} (id, material_id, topic_id, classroom_id, chunk_text, chunk_index, embedding)
                    VALUES (:id, 1, 1, 9999999, 'Invalid FK chunk', 0, :vec);
                """)
                await session.execute(insert_bad_fk, {"id": invalid_uuid, "vec": str(valid_vector)})
                await session.commit()
            await session.rollback()
    finally:
        # 3. Clean drop of temporary table
        async with AsyncSession(test_engine) as session:
            await session.execute(text(f"DROP TABLE IF EXISTS {temp_table_name};"))
            await session.commit()
        await test_engine.dispose()
