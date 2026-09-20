"""
Integration-style tests for document processing pipeline orchestrator (app/services/document_processor.py)
All external API calls (Storage, Gemini) and DB operations are mocked.
"""

import time
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from app.services.document_processor import process_material
from app.db.models import Embedding


@pytest.mark.asyncio
async def test_process_material_success():
    fake_record = (
        101,  # material_id
        10,   # topic_id
        "materials/test_doc.pdf",  # storage_path
        "pdf", # file_type
        "UPLOADED", # status
        1,    # classroom_id
    )

    mock_db_result = MagicMock()
    mock_db_result.first.return_value = fake_record

    mock_session = AsyncMock()
    mock_session.add_all = MagicMock()
    mock_session.execute.return_value = mock_db_result

    with patch("app.services.document_processor.async_session_maker") as mock_maker_cls, \
         patch("app.services.document_processor.fetch_storage_file", new_callable=AsyncMock) as mock_fetch, \
         patch("app.services.document_processor.extract_text_from_pdf") as mock_extract, \
         patch("app.services.document_processor.chunk_text") as mock_chunk, \
         patch("app.services.document_processor.get_embeddings") as mock_embed:

        mock_maker_cls.return_value.__aenter__.return_value = mock_session
        mock_fetch.return_value = b"%PDF-1.4 test bytes"
        mock_extract.return_value = "Sample PDF document text for chunking and embedding."
        mock_chunk.return_value = ["Sample PDF document text", "for chunking and embedding."]
        mock_embed.return_value = [[0.1] * 768, [0.2] * 768]

        await process_material(101)

        # Verify storage, text extraction, chunking, and embedding calls
        mock_fetch.assert_called_once_with("materials/test_doc.pdf")
        mock_extract.assert_called_once_with(b"%PDF-1.4 test bytes")
        mock_chunk.assert_called_once_with("Sample PDF document text for chunking and embedding.")
        mock_embed.assert_called_once_with(["Sample PDF document text", "for chunking and embedding."])

        # Verify DB session committed and add_all was called for 2 embeddings
        assert mock_session.add_all.call_count == 1
        inserted_embeddings = mock_session.add_all.call_args[0][0]
        assert len(inserted_embeddings) == 2
        assert inserted_embeddings[0].material_id == 101
        assert inserted_embeddings[0].classroom_id == 1
        assert inserted_embeddings[0].topic_id == 10

        # Verify commit count (status -> PROCESSING, insert embeddings, status -> READY)
        assert mock_session.commit.call_count >= 3


@pytest.mark.asyncio
async def test_process_material_idempotent_reprocessing_deletes_old_embeddings():
    """
    Confirms that re-processing the same material_id explicitly issues a DELETE statement
    for existing material_id embeddings before inserting the new set, guaranteeing no duplicates.
    """
    fake_record = (101, 10, "materials/test_doc.pdf", "pdf", "READY", 1)

    mock_db_result = MagicMock()
    mock_db_result.first.return_value = fake_record

    mock_session = AsyncMock()
    mock_session.add_all = MagicMock()
    mock_session.execute.return_value = mock_db_result

    with patch("app.services.document_processor.async_session_maker") as mock_maker_cls, \
         patch("app.services.document_processor.fetch_storage_file", new_callable=AsyncMock) as mock_fetch, \
         patch("app.services.document_processor.extract_text_from_pdf") as mock_extract, \
         patch("app.services.document_processor.chunk_text") as mock_chunk, \
         patch("app.services.document_processor.get_embeddings") as mock_embed:

        mock_maker_cls.return_value.__aenter__.return_value = mock_session
        mock_fetch.return_value = b"%PDF-1.4 test bytes"
        mock_extract.return_value = "Updated document text"
        mock_chunk.return_value = ["Updated document text"]
        mock_embed.return_value = [[0.3] * 768]

        # Execute re-processing call for material_id 101
        await process_material(101)

        # Inspect all calls to session.execute
        executed_statements = [call[0][0] for call in mock_session.execute.call_args_list]

        # Verify that a delete statement targeting Embedding.material_id == 101 was executed
        delete_calls = [
            stmt for stmt in executed_statements
            if hasattr(stmt, "is_delete") and stmt.is_delete
        ]
        assert len(delete_calls) == 1, "Expected exactly 1 DELETE query to clear pre-existing embeddings."

        # Verify that exactly 1 fresh embedding record set was added
        assert mock_session.add_all.call_count == 1
        inserted_embeddings = mock_session.add_all.call_args[0][0]
        assert len(inserted_embeddings) == 1
        assert inserted_embeddings[0].material_id == 101


@pytest.mark.asyncio
async def test_process_material_failure_mid_pipeline_rollback():
    fake_record = (
        102,
        10,
        "materials/unsupported_file.docx",
        "docx",
        "UPLOADED",
        1,
    )

    mock_db_result = MagicMock()
    mock_db_result.first.return_value = fake_record

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_db_result

    with patch("app.services.document_processor.async_session_maker") as mock_maker_cls:
        mock_maker_cls.return_value.__aenter__.return_value = mock_session

        await process_material(102)

        # Rollback must be called when exception occurs (unsupported file type)
        assert mock_session.rollback.call_count == 1
        # add_all should NOT be called since processing failed before embedding insert
        assert mock_session.add_all.call_count == 0


@pytest.mark.asyncio
async def test_process_material_embedding_failure_triggers_rollback():
    fake_record = (
        103,
        10,
        "materials/test_doc.pdf",
        "pdf",
        "UPLOADED",
        1,
    )

    mock_db_result = MagicMock()
    mock_db_result.first.return_value = fake_record

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_db_result

    with patch("app.services.document_processor.async_session_maker") as mock_maker_cls, \
         patch("app.services.document_processor.fetch_storage_file", new_callable=AsyncMock) as mock_fetch, \
         patch("app.services.document_processor.extract_text_from_pdf") as mock_extract, \
         patch("app.services.document_processor.chunk_text") as mock_chunk, \
         patch("app.services.document_processor.get_embeddings") as mock_embed:

        mock_maker_cls.return_value.__aenter__.return_value = mock_session
        mock_fetch.return_value = b"%PDF-1.4 test bytes"
        mock_extract.return_value = "Sample text"
        mock_chunk.return_value = ["Sample text"]
        mock_embed.side_effect = RuntimeError("Gemini API Rate Limit Exceeded")

        await process_material(103)

        # Rollback called, no embeddings committed
        assert mock_session.rollback.call_count == 1
        assert mock_session.add_all.call_count == 0
