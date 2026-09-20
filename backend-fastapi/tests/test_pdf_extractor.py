"""
Unit tests for PDF text extractor service (app/services/pdf_extractor.py)
"""

import io
import pytest
from fpdf import FPDF
from pypdf import PdfWriter
from app.services.pdf_extractor import extract_text_from_pdf, PDFExtractionError


@pytest.fixture
def sample_text_pdf_bytes() -> bytes:
    """Generates a valid PDF with real text content."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(text="Hello World, this is a test PDF document for DLP pipeline.")
    pdf.add_page()
    pdf.cell(text="Second page content for vector text extraction.")
    return bytes(pdf.output())


@pytest.fixture
def sample_no_text_pdf_bytes() -> bytes:
    """Generates a PDF with blank pages (no text layer / image-only representation)."""
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_extract_text_from_pdf_success(sample_text_pdf_bytes):
    extracted_text = extract_text_from_pdf(sample_text_pdf_bytes)
    assert "Hello World, this is a test PDF document for DLP pipeline." in extracted_text
    assert "Second page content for vector text extraction." in extracted_text


def test_extract_text_from_pdf_no_text_layer(sample_no_text_pdf_bytes):
    with pytest.raises(PDFExtractionError, match="PDF contains no extractable text layer"):
        extract_text_from_pdf(sample_no_text_pdf_bytes)


def test_extract_text_from_pdf_empty_bytes():
    with pytest.raises(PDFExtractionError, match="PDF file content is empty"):
        extract_text_from_pdf(b"")


def test_extract_text_from_pdf_corrupt_bytes():
    with pytest.raises(PDFExtractionError, match="Failed to parse PDF document"):
        extract_text_from_pdf(b"NOT_A_VALID_PDF_STREAM_12345")
