"""
Document Processing Orchestrator Service

Pipeline Flow:
1. Fetch Material metadata and join up through Topic -> Module -> Course -> Classroom to resolve classroom_id.
2. Update Material status to 'PROCESSING'.
3. Download PDF file bytes from Supabase Storage bucket 'materials'.
4. Extract text from PDF (pypdf).
5. Chunk text into word-level sliding windows (chunker).
6. Embed all chunks via Gemini gemini-embedding-001 (768-dim, batched, rate-limit aware).
7. Insert all chunks into pgvector embeddings table in a single atomic transaction batch.
   If any chunk embedding or DB insert fails, roll back all inserted chunks so partial context is never committed.
8. On success: set Material status to 'READY'.
9. On failure at any stage: roll back DB batch, set Material status to 'FAILED', and set failure_reason.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from sqlalchemy import select, update, delete, Table, Column, BigInteger, String, Text, MetaData
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.db.models import Base, Embedding
from app.services.storage_client import fetch_storage_file, StorageFetchError
from app.services.pdf_extractor import extract_text_from_pdf, PDFExtractionError
from app.services.chunker import chunk_text
from app.services.embeddings_client import get_embeddings, GeminiEmbeddingError

logger = logging.getLogger(__name__)

# Core Table definitions for Django-owned source-of-truth tables (bound to Base.metadata for ORM FK resolution)

syllabus_material = Table(
    "syllabus_material",
    Base.metadata,
    Column("id", BigInteger, primary_key=True),
    Column("topic_id", BigInteger),
    Column("storage_path", String),
    Column("file_type", String),
    Column("status", String),
    Column("failure_reason", Text),
    extend_existing=True,
)

syllabus_topic = Table(
    "syllabus_topic",
    Base.metadata,
    Column("id", BigInteger, primary_key=True),
    Column("module_id", BigInteger),
    extend_existing=True,
)

syllabus_module = Table(
    "syllabus_module",
    Base.metadata,
    Column("id", BigInteger, primary_key=True),
    Column("course_id", BigInteger),
    extend_existing=True,
)

syllabus_course = Table(
    "syllabus_course",
    Base.metadata,
    Column("id", BigInteger, primary_key=True),
    Column("classroom_id", BigInteger),
    extend_existing=True,
)

classrooms_classroom = Table(
    "classrooms_classroom",
    Base.metadata,
    Column("id", BigInteger, primary_key=True),
    extend_existing=True,
)


async def process_material(material_id: int) -> None:
    """
    Executes the full extraction -> chunking -> embedding -> storage pipeline for a material.

    Args:
        material_id: Primary key of the Django syllabus_material record to process.
    """
    async with async_session_maker() as session:
        # 1. Fetch material metadata and resolve classroom_id via table joins
        stmt = (
            select(
                syllabus_material.c.id,
                syllabus_material.c.topic_id,
                syllabus_material.c.storage_path,
                syllabus_material.c.file_type,
                syllabus_material.c.status,
                syllabus_course.c.classroom_id,
            )
            .select_from(syllabus_material)
            .join(syllabus_topic, syllabus_material.c.topic_id == syllabus_topic.c.id)
            .join(syllabus_module, syllabus_topic.c.module_id == syllabus_module.c.id)
            .join(syllabus_course, syllabus_module.c.course_id == syllabus_course.c.id)
            .where(syllabus_material.c.id == material_id)
        )

        result = await session.execute(stmt)
        record = result.first()

        if not record:
            logger.error(f"Cannot process material {material_id}: record not found in database.")
            return

        mat_id, topic_id, storage_path, file_type, current_status, classroom_id = record

        # 2. Update status to PROCESSING
        await _update_material_status(session, material_id, "PROCESSING", failure_reason=None)

        try:
            # 3. File type check (PDF only for now)
            normalized_file_type = (file_type or "").lower().strip()
            if normalized_file_type != "pdf" and not (storage_path or "").lower().endswith(".pdf"):
                raise ValueError(
                    f"Unsupported file type '{file_type}'. Document processing currently only supports PDF files."
                )

            # 4. Fetch raw file bytes from Supabase Storage
            logger.info(f"Fetching file bytes for material {material_id} at path '{storage_path}'")
            file_bytes = await fetch_storage_file(storage_path)

            # 5. Extract text
            logger.info(f"Extracting text from PDF for material {material_id}")
            raw_text = extract_text_from_pdf(file_bytes)

            # 6. Chunk text
            chunks = chunk_text(raw_text)
            if not chunks:
                raise ValueError("PDF extraction resulted in 0 text chunks.")

            logger.info(f"Material {material_id} split into {len(chunks)} text chunks.")

            # 7. Generate 768-dim embeddings via Gemini API (offloaded to thread worker to prevent blocking event loop)
            logger.info(f"Generating Gemini embeddings for {len(chunks)} chunks of material {material_id}")
            vectors = await asyncio.to_thread(get_embeddings, chunks)

            if len(vectors) != len(chunks):
                raise ValueError(
                    f"Mismatch between chunk count ({len(chunks)}) and generated vector count ({len(vectors)})."
                )

            # 8. Transactional Batch Insert into pgvector embeddings table
            # If reprocessing, delete previous embeddings first to avoid duplicate chunks
            await session.execute(
                delete(Embedding).where(Embedding.material_id == material_id)
            )

            embedding_records = [
                Embedding(
                    material_id=material_id,
                    topic_id=topic_id,
                    classroom_id=classroom_id,
                    chunk_text=chunk_str,
                    chunk_index=idx,
                    embedding=vector,
                )
                for idx, (chunk_str, vector) in enumerate(zip(chunks, vectors))
            ]

            session.add_all(embedding_records)
            await session.commit()
            logger.info(f"Successfully inserted {len(embedding_records)} embeddings for material {material_id}")

            # 9. Update status to READY on success
            await _update_material_status(session, material_id, "READY", failure_reason=None)

        except Exception as e:
            logger.exception(f"Document processing failed for material {material_id}: {e}")
            await session.rollback()

            # Clean human-readable error message (avoid stack traces or internal secrets)
            failure_msg = str(e).strip() or "An unknown error occurred during document processing."
            if len(failure_msg) > 500:
                failure_msg = failure_msg[:497] + "..."

            await _update_material_status(session, material_id, "FAILED", failure_reason=failure_msg)


async def get_material_status_record(material_id: int) -> Optional[Dict[str, Any]]:
    """
    Queries current status and failure_reason for a given material_id from Django's syllabus_material table.
    """
    async with async_session_maker() as session:
        stmt = (
            select(
                syllabus_material.c.id,
                syllabus_material.c.status,
                syllabus_material.c.failure_reason,
            )
            .where(syllabus_material.c.id == material_id)
        )
        result = await session.execute(stmt)
        record = result.first()

        if not record:
            return None

        return {
            "material_id": record[0],
            "status": record[1],
            "failure_reason": record[2],
        }


async def _update_material_status(
    session: AsyncSession,
    material_id: int,
    status: str,
    failure_reason: Optional[str] = None,
) -> None:
    """Helper to update material status and failure_reason in Django's syllabus_material table."""
    stmt = (
        update(syllabus_material)
        .where(syllabus_material.c.id == material_id)
        .values(status=status, failure_reason=failure_reason)
    )
    await session.execute(stmt)
    await session.commit()
