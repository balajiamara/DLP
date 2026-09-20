"""
RAG Retrieval Service with Authorization Defense-in-Depth

Security Architecture:
1. Authorization MUST be checked BEFORE any similarity search or query embedding generation runs.
2. A student cannot retrieve chunks from a classroom they are not an ACTIVE member of,
   regardless of vector semantic similarity.
3. If unauthorized, the function short-circuits immediately without invoking Gemini API or querying vector tables.
4. Cosine similarity distance ordering is scoped with explicit SQL filters:
   WHERE e.classroom_id = :classroom_id AND m.status = 'READY'
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy import select, text, Table, Column, BigInteger, String, MetaData
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.db.models import Base, Embedding
from app.services.embeddings_client import get_embeddings

logger = logging.getLogger(__name__)


class NotAuthorizedError(Exception):
    """Raised when a user is not an active member of the requested classroom."""
    pass


# Table definitions for Django-owned source-of-truth tables (bound to Base.metadata)
classrooms_classroommembership = Table(
    "classrooms_classroommembership",
    Base.metadata,
    Column("id", BigInteger, primary_key=True),
    Column("user_id", BigInteger),
    Column("classroom_id", BigInteger),
    Column("role_in_classroom", String),
    Column("status", String),
    extend_existing=True,
)

syllabus_material = Table(
    "syllabus_material",
    Base.metadata,
    Column("id", BigInteger, primary_key=True),
    Column("topic_id", BigInteger),
    Column("storage_path", String),
    Column("file_type", String),
    Column("status", String),
    Column("title", String),
    extend_existing=True,
)


async def is_authorized_for_classroom(user_id: int, classroom_id: int) -> bool:
    """
    Checks if a user has an active membership ('ACTIVE') in the specified classroom.

    Args:
        user_id: Primary key of the student user (accounts_user.id).
        classroom_id: Primary key of the classroom (classrooms_classroom.id).

    Returns:
        True if the user has an active membership row, False otherwise.
    """
    user_id_int = int(user_id)
    classroom_id_int = int(classroom_id)
    async with async_session_maker() as session:
        stmt = (
            select(classrooms_classroommembership.c.id)
            .where(
                classrooms_classroommembership.c.user_id == user_id_int,
                classrooms_classroommembership.c.classroom_id == classroom_id_int,
                classrooms_classroommembership.c.status == "ACTIVE",
            )
        )
        result = await session.execute(stmt)
        return result.first() is not None


async def retrieve_relevant_chunks(
    user_id: int,
    classroom_id: int,
    query_text: str,
    topic_id: Optional[int] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Retrieves the top-k most relevant material text chunks for a query within an authorized classroom.

    Security Order of Operations:
    1. Check authorization FIRST. If not active member -> raise NotAuthorizedError immediately.
    2. Embed query_text via Gemini API (async thread worker).
    3. Execute single SQL query filtering by classroom_id, topic_id (if provided), and material status 'READY',
       ordered by cosine distance (`embedding <=> query_vector`).

    Returns:
        List of dicts containing material_id, material_title, chunk_text, chunk_index, and distance score.
    """
    # 1. Authorization check runs FIRST before embedding generation or vector search
    authorized = await is_authorized_for_classroom(user_id, classroom_id)
    if not authorized:
        logger.warning(
            f"Unauthorized RAG retrieval attempt: user {user_id} requested classroom {classroom_id}."
        )
        raise NotAuthorizedError(f"User {user_id} is not an active member of classroom {classroom_id}.")

    if not query_text or not query_text.strip():
        return []

    # 2. Embed query text using Gemini API (offloaded to thread worker)
    query_vectors = await asyncio.to_thread(get_embeddings, [query_text])
    if not query_vectors:
        return []
    query_vector = query_vectors[0]

    # Format vector array for pgvector string representation: '[0.1, 0.2, ...]'
    formatted_vector = f"[{','.join(str(v) for v in query_vector)}]"

    # 3. Execute vector similarity search with explicit pre-filters
    async with async_session_maker() as session:
        # Enable pgvector iterative scan to ensure filtered HNSW searches do not drop candidate matches
        try:
            await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order;"))
        except Exception as e:
            logger.debug(f"Could not set hnsw.iterative_scan: {e}")

        # Build SQL query joining embeddings with syllabus_material for READY status filter & material_title
        query_sql = text("""
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
            WHERE e.classroom_id = :classroom_id
              AND (CAST(:topic_id AS bigint) IS NULL OR e.topic_id = CAST(:topic_id AS bigint))
              AND m.status = 'READY'
            ORDER BY e.embedding <=> CAST(:query_vector AS vector) ASC
            LIMIT :top_k;
        """)

        params = {
            "classroom_id": classroom_id,
            "topic_id": topic_id,
            "query_vector": formatted_vector,
            "top_k": top_k,
        }

        result = await session.execute(query_sql, params)
        rows = result.all()

        chunks = []
        for row in rows:
            chunks.append({
                "id": str(row.id),
                "material_id": row.material_id,
                "material_title": row.material_title,
                "topic_id": row.topic_id,
                "classroom_id": row.classroom_id,
                "chunk_text": row.chunk_text,
                "chunk_index": row.chunk_index,
                "score": round(1.0 - float(row.distance), 4) if row.distance is not None else 0.0,
                "distance": float(row.distance) if row.distance is not None else 0.0,
            })

        return chunks
