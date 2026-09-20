"""create embeddings table and vector index

Revision ID: 001_create_embeddings_table
Revises: 
Create Date: 2026-09-05

"""
from typing import Sequence, Union
import alembic.op as op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '001_create_embeddings_table'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension (idempotent, safe to run if extension exists)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create embeddings table
    op.create_table(
        'embeddings',
        sa.Column(
            'id',
            UUID(as_uuid=True),
            server_default=sa.text('gen_random_uuid()'),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            'material_id',
            sa.BigInteger(),
            sa.ForeignKey('syllabus_material.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'topic_id',
            sa.BigInteger(),
            sa.ForeignKey('syllabus_topic.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'classroom_id',
            sa.BigInteger(),
            sa.ForeignKey('classrooms_classroom.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        # VECTOR(1536) matches OpenAI ada-002 / text-embedding-3-small dimension.
        # NOT NULL: Embeddings rows are only inserted after successful embedding generation.
        sa.Column('embedding', Vector(1536), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('metadata', JSONB(), nullable=True),
    )

    # 3. Composite index on (classroom_id, topic_id) for authorization pre-filtering.
    # Rationale: Filtering by classroom/topic FIRST narrows search candidates before vector distance computation,
    # preventing unauthorized cross-classroom data leaks and saving compute.
    op.create_index(
        'ix_embeddings_classroom_topic',
        'embeddings',
        ['classroom_id', 'topic_id'],
        unique=False,
    )

    # 4. HNSW Index for approximate nearest neighbor similarity search (vector_cosine_ops).
    # Supabase PostgreSQL 17 comes with pgvector 0.8.2 (>= 0.5.0 required for HNSW).
    op.create_index(
        'ix_embeddings_embedding_hnsw',
        'embeddings',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_with={'m': 16, 'ef_construction': 64},
        postgresql_ops={'embedding': 'vector_cosine_ops'},
    )


def downgrade() -> None:
    # Drop indexes and table cleanly without dropping the vector extension itself
    op.drop_index('ix_embeddings_embedding_hnsw', table_name='embeddings')
    op.drop_index('ix_embeddings_classroom_topic', table_name='embeddings')
    op.drop_table('embeddings')
