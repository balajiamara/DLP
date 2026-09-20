"""
Unit tests for text chunker service (app/services/chunker.py)
"""

import pytest
from app.services.chunker import chunk_text


def test_chunk_text_normal():
    # 600 words text
    words = [f"word{i}" for i in range(600)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_size=500, overlap=50)

    # 600 words with chunk_size=500, overlap=50 (step=450) -> 2 chunks: 0..500 and 450..600
    assert len(chunks) == 2
    assert len(chunks[0].split()) == 500
    assert len(chunks[1].split()) == 150
    # Check overlap between first and second chunk
    first_chunk_last_50 = chunks[0].split()[-50:]
    second_chunk_first_50 = chunks[1].split()[:50]
    assert first_chunk_last_50 == second_chunk_first_50


def test_chunk_text_short():
    # 50 words text (< chunk_size)
    words = [f"word{i}" for i in range(50)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_size=500, overlap=50)

    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n\t  ") == []
    assert chunk_text(None) == []


def test_chunk_text_exact_boundary():
    # Exactly 500 words text (= chunk_size)
    words = [f"word{i}" for i in range(500)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_size=500, overlap=50)

    assert len(chunks) == 1
    assert len(chunks[0].split()) == 500
    assert chunks[0] == text


def test_chunk_text_invalid_overlap():
    with pytest.raises(ValueError, match="overlap must be strictly less than chunk_size"):
        chunk_text("some test text words here", chunk_size=10, overlap=10)
