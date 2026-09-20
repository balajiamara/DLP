"""
Text Chunker Service

Note on Chunking Strategy:
chunk_size and overlap are measured in WORDS (whitespace-separated strings).
While token-based chunking (e.g. using tiktoken or model tokenizers) would better match LLM context budgeting,
word-based chunking is a simpler, deterministic starting point for this pass of the document pipeline.
"""


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Splits text into sliding-window chunks based on word counts.

    Args:
        text: Raw input text string.
        chunk_size: Maximum number of words per chunk (default 500).
        overlap: Number of overlapping words between consecutive chunks (default 50).

    Returns:
        List of chunk text strings. Zero chunks returned for empty/whitespace input.
        The index of each item in the returned list corresponds to its chunk_index (0-indexed).
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be strictly less than chunk_size.")

    if not text or not text.strip():
        return []

    words = text.split()
    if not words:
        return []

    if len(words) <= chunk_size:
        return [" ".join(words)]

    step = chunk_size - overlap
    chunks = []

    for i in range(0, len(words), step):
        chunk_words = words[i : i + chunk_size]
        chunks.append(" ".join(chunk_words))
        if i + chunk_size >= len(words):
            break

    return chunks
