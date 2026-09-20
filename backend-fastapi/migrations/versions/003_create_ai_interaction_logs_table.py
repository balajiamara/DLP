"""create ai_interaction_logs table for AI evaluation logging

Revision ID: 003_ai_interaction_logs
Revises: 002_alter_embedding_dimension
Create Date: 2026-09-10

"""
from typing import Sequence, Union
import alembic.op as op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = '003_ai_interaction_logs'
down_revision: Union[str, None] = '002_alter_embedding_dimension'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, widen alembic_version.version_num to VARCHAR(64) to prevent future truncation
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64);")

    op.create_table(
        'ai_interaction_logs',
        sa.Column(
            'id',
            UUID(as_uuid=True),
            server_default=sa.text('gen_random_uuid()'),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            'interaction_id',
            UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column('interaction_type', sa.Text(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('classroom_id', sa.BigInteger(), nullable=True),
        sa.Column('model', sa.Text(), nullable=False),
        sa.Column('grounded', sa.Boolean(), nullable=True),
        sa.Column(
            'retrieved_chunk_ids',
            JSONB,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            'retrieved_chunk_count',
            sa.Integer(),
            server_default=sa.text('0'),
            nullable=False,
        ),
        sa.Column('socratic_mode', sa.Boolean(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=True),
        sa.Column('answer_text', sa.Text(), nullable=True),
        sa.Column(
            'error_occurred',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('feedback_rating', sa.Text(), nullable=True),
        sa.Column('feedback_reason', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )

    op.create_index('ix_ai_interaction_logs_interaction_id', 'ai_interaction_logs', ['interaction_id'])
    op.create_index('ix_ai_interaction_logs_interaction_type', 'ai_interaction_logs', ['interaction_type'])
    op.create_index('ix_ai_interaction_logs_user_id', 'ai_interaction_logs', ['user_id'])
    op.create_index('ix_ai_interaction_logs_classroom_id', 'ai_interaction_logs', ['classroom_id'])
    op.create_index('ix_ai_interaction_logs_created_at', 'ai_interaction_logs', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_ai_interaction_logs_created_at', table_name='ai_interaction_logs')
    op.drop_index('ix_ai_interaction_logs_classroom_id', table_name='ai_interaction_logs')
    op.drop_index('ix_ai_interaction_logs_user_id', table_name='ai_interaction_logs')
    op.drop_index('ix_ai_interaction_logs_interaction_type', table_name='ai_interaction_logs')
    op.drop_index('ix_ai_interaction_logs_interaction_id', table_name='ai_interaction_logs')
    op.drop_table('ai_interaction_logs')
