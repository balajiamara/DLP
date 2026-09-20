"""
Unit tests for Gemini embedding client service (app/services/embeddings_client.py)
All Gemini API client calls are mocked; no real API calls or quota usage.
"""

from unittest.mock import MagicMock, patch
import pytest
from app.services.embeddings_client import (
    get_embeddings,
    GeminiEmbeddingError,
    EXPECTED_DIMENSION,
)


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setattr("app.services.embeddings_client.settings.GEMINI_API_KEY", "test-fake-gemini-key")


def _create_mock_embedding_item(dim: int = 768):
    item = MagicMock()
    item.values = [0.1] * dim
    return item


def test_get_embeddings_success(mock_settings):
    fake_response = MagicMock()
    fake_response.embeddings = [
        _create_mock_embedding_item(768),
        _create_mock_embedding_item(768),
    ]

    with patch("app.services.embeddings_client.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_instance.models.embed_content.return_value = fake_response
        mock_client_cls.return_value = mock_client_instance

        vectors = get_embeddings(["Chunk text 1", "Chunk text 2"])

        assert len(vectors) == 2
        assert len(vectors[0]) == 768
        assert len(vectors[1]) == 768
        assert mock_client_instance.models.embed_content.call_count == 1


def test_get_embeddings_dimension_mismatch(mock_settings):
    # API returns 512 dimensions instead of 768
    fake_response = MagicMock()
    fake_response.embeddings = [_create_mock_embedding_item(512)]

    with patch("app.services.embeddings_client.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_instance.models.embed_content.return_value = fake_response
        mock_client_cls.return_value = mock_client_instance

        with pytest.raises(GeminiEmbeddingError, match="Vector dimension mismatch"):
            get_embeddings(["Test chunk text"])


def test_get_embeddings_retry_then_succeed(mock_settings):
    fake_response = MagicMock()
    fake_response.embeddings = [_create_mock_embedding_item(768)]

    with patch("app.services.embeddings_client.genai.Client") as mock_client_cls, \
         patch("app.services.embeddings_client.time.sleep") as mock_sleep:
        mock_client_instance = MagicMock()
        # First call fails with transient exception, second call succeeds
        mock_client_instance.models.embed_content.side_effect = [
            Exception("Transient API rate limit (429)"),
            fake_response,
        ]
        mock_client_cls.return_value = mock_client_instance

        vectors = get_embeddings(["Test chunk text"])

        assert len(vectors) == 1
        assert len(vectors[0]) == 768
        assert mock_client_instance.models.embed_content.call_count == 2
        assert mock_sleep.call_count == 1


def test_get_embeddings_retry_exhausted_then_fail(mock_settings):
    with patch("app.services.embeddings_client.genai.Client") as mock_client_cls, \
         patch("app.services.embeddings_client.time.sleep") as mock_sleep:
        mock_client_instance = MagicMock()
        mock_client_instance.models.embed_content.side_effect = Exception("Persistent API failure (500)")
        mock_client_cls.return_value = mock_client_instance

        with pytest.raises(GeminiEmbeddingError, match="Gemini embedding API failed after 3 attempts"):
            get_embeddings(["Test chunk text"])

        assert mock_client_instance.models.embed_content.call_count == 3
        assert mock_sleep.call_count == 2  # slept between retries


def test_get_embeddings_missing_api_key(monkeypatch):
    monkeypatch.setattr("app.services.embeddings_client.settings.GEMINI_API_KEY", "")

    with pytest.raises(GeminiEmbeddingError, match="GEMINI_API_KEY is not configured"):
        get_embeddings(["Some text"])
