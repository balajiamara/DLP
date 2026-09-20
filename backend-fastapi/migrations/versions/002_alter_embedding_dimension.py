"""alter embedding column dimension from 1536 to 768 for Gemini text-embedding-004

Revision ID: 002_alter_embedding_dimension
Revises: 001_create_embeddings_table
Create Date: 2026-09-05

"""
from typing import Sequence, Union
import alembic.op as op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '002_alter_embedding_dimension'
down_revision: Union[str, None] = '001_create_embeddings_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop dependent HNSW vector index before altering vector dimension
    op.drop_index('ix_embeddings_embedding_hnsw', table_name='embeddings')

    # 2. Alter embedding column from VECTOR(1536) to VECTOR(768)
    op.alter_column(
        'embeddings',
        'embedding',
        type_=Vector(768),
        existing_type=Vector(1536),
        existing_nullable=False,
    )

    # 3. Recreate HNSW vector index on resized VECTOR(768) column
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
    # 1. Drop HNSW vector index
    op.drop_index('ix_embeddings_embedding_hnsw', table_name='embeddings')

    # 2. Revert embedding column from VECTOR(768) back to VECTOR(1536)
    op.alter_column(
        'embeddings',
        'embedding',
        type_=Vector(1536),
        existing_type=Vector(768),
        existing_nullable=False,
    )

    # 3. Recreate HNSW vector index on VECTOR(1536) column
    op.create_index(
        'ix_embeddings_embedding_hnsw',
        'embeddings',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_with={'m': 16, 'ef_construction': 64},
        postgresql_ops={'embedding': 'vector_cosine_ops'},
    )
