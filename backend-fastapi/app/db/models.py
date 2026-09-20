import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import BigInteger, DateTime, Index, Integer, Text, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class Embedding(Base):
    """
    RAG Embeddings table schema for Daily Learning Planner.
    Maps text chunks of course Materials to 768-dim vector embeddings (Gemini gemini-embedding-001) for similarity search.
    """
    __tablename__ = "embeddings"

    # UUID primary key using native Postgres gen_random_uuid() or Python uuid4
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    # DB Foreign keys referencing Django source-of-truth tables (BigInt PKs)
    material_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("syllabus_material.id", ondelete="CASCADE"),
        nullable=False,
    )

    topic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("syllabus_topic.id", ondelete="CASCADE"),
        nullable=False,
    )

    classroom_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("classrooms_classroom.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Chunk details
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # 768-dimensional vector embedding.
    # Note: 768 dimensions matches Google Gemini gemini-embedding-001 output size.
    # NOT NULL: Embeddings rows are only inserted after successful embedding generation.
    embedding: Mapped[Any] = mapped_column(Vector(768), nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # Metadata column mapped to extra_data to avoid collision with DeclarativeBase.metadata
    extra_data: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    __table_args__ = (
        # Composite index for authorization pre-filtering.
        # Rationale: Filtering by (classroom_id, topic_id) FIRST isolates accessible chunks
        # before running vector similarity search. Running vector search across all classrooms
        # and discarding unauthorized results post-hoc wastes compute and creates a security risk.
        Index("ix_embeddings_classroom_topic", "classroom_id", "topic_id"),

        # HNSW Index for approximate nearest neighbor search (vector_cosine_ops).
        # Requires pgvector >= 0.5.0 (Supabase default is 0.8.2).
        Index(
            "ix_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class AIInteractionLog(Base):
    """
    Observability and evaluation telemetry log for all AI interactions:
    Course chat, General chat, Quiz generation, Study plan generation, and Personalized assistant.

    Data Retention & Privacy Note:
    query_text and answer_text are logged (truncated to 500 characters) for debugging,
    hallucination inspection, and offline evaluation purposes. In a full production deployment,
    this table would be governed by a documented data retention policy (e.g. 30/90-day TTL or anonymization).
    """
    __tablename__ = "ai_interaction_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    # Note: Generated fresh per interaction (single-turn currently).
    # Will become a correlated conversation_id when multi-turn session history is added.
    interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )

    interaction_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )

    # Plain integers without foreign keys to Django tables (observability data must not fail on FK constraints)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    classroom_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    model: Mapped[str] = mapped_column(Text, nullable=False)
    grounded: Mapped[Optional[bool]] = mapped_column(nullable=True)

    retrieved_chunk_ids: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    retrieved_chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    socratic_mode: Mapped[Optional[bool]] = mapped_column(nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    query_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    error_occurred: Mapped[bool] = mapped_column(
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    feedback_rating: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    feedback_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
        index=True,
    )

