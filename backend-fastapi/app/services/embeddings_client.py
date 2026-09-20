"""
Gemini Embedding Client Service

Model Decision Rationale:
`gemini-embedding-001` is selected as Google's active embedding model for GenAI API endpoints.
It natively supports custom output dimensions via `output_dimensionality=768`, matching our production pgvector VECTOR(768) schema.
"""

import time
import logging
from google import genai
from google.genai import types
from app.core.config import settings

logger = logging.getLogger(__name__)

# Hardcoded model choice per Decision 1
GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
EXPECTED_DIMENSION = 768
MAX_BATCH_SIZE = 50
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0  # seconds
BATCH_THROTTLE_DELAY = 1.0  # seconds between batches to respect free tier (15 RPM)


class GeminiEmbeddingError(Exception):
    """Raised when embedding generation fails or returns an invalid vector dimension."""
    pass


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Generates 768-dimensional embeddings for a list of text strings using Google Gemini text-embedding-004.

    Args:
        texts: List of chunk text strings.

    Returns:
        List of 768-dim float lists, in the exact same order as `texts`.

    Raises:
        GeminiEmbeddingError: If API key is missing, API calls fail after retries,
                              or returned vectors do not match 768 dimensions.
    """
    if not texts:
        return []

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise GeminiEmbeddingError("GEMINI_API_KEY is not configured in settings.")

    client = genai.Client(api_key=api_key)
    all_embeddings: list[list[float]] = []

    # Process in batches to respect API limits
    for batch_idx in range(0, len(texts), MAX_BATCH_SIZE):
        batch = texts[batch_idx : batch_idx + MAX_BATCH_SIZE]

        if batch_idx > 0:
            time.sleep(BATCH_THROTTLE_DELAY)

        batch_embeddings = _embed_batch_with_retry(client, batch)
        all_embeddings.extend(batch_embeddings)

    if len(all_embeddings) != len(texts):
        raise GeminiEmbeddingError(
            f"Embedding count mismatch: sent {len(texts)} texts, received {len(all_embeddings)} embeddings."
        )

    return all_embeddings


def _embed_batch_with_retry(client: genai.Client, batch_texts: list[str]) -> list[list[float]]:
    """Helper to embed a single batch of texts with exponential backoff retries."""
    delay = INITIAL_RETRY_DELAY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.embed_content(
                model=GEMINI_EMBEDDING_MODEL,
                contents=batch_texts,
                config=types.EmbedContentConfig(output_dimensionality=EXPECTED_DIMENSION),
            )

            if not response or not response.embeddings:
                raise GeminiEmbeddingError("Gemini API returned an empty embedding response.")

            vectors = []
            for idx, item in enumerate(response.embeddings):
                val = item.values if hasattr(item, "values") else getattr(item, "embedding", None)
                if val is None:
                    raise GeminiEmbeddingError(f"Missing embedding values for index {idx} in batch.")

                dim = len(val)
                if dim != EXPECTED_DIMENSION:
                    raise GeminiEmbeddingError(
                        f"Vector dimension mismatch at index {idx}: expected {EXPECTED_DIMENSION}, got {dim}."
                    )
                vectors.append(list(val))

            return vectors

        except GeminiEmbeddingError:
            raise
        except Exception as e:
            logger.warning(
                f"Gemini API embed call failed (attempt {attempt}/{MAX_RETRIES}): {e}"
            )
            if attempt == MAX_RETRIES:
                raise GeminiEmbeddingError(
                    f"Gemini embedding API failed after {MAX_RETRIES} attempts: {e}"
                ) from e
            time.sleep(delay)
            delay *= 2.0

    raise GeminiEmbeddingError("Failed to generate embeddings: retries exhausted.")
