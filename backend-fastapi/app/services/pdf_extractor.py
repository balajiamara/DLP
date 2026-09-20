"""
PDF Text Extractor Service

Justification for library choice:
`pypdf` is chosen over `pdfplumber` because it is lightweight, pure-Python (no native C dependencies like pdfminer or poppler),
well-maintained, fast, and fully sufficient for page-by-page text extraction from vector PDFs.
"""

import io
from pypdf import PdfReader


class PDFExtractionError(Exception):
    """Raised when text cannot be extracted from a PDF (e.g., corrupt file or image-only scanned PDF)."""
    pass


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extracts and concatenates all text from a PDF file byte stream.

    Args:
        file_bytes: Raw bytes of the PDF file.

    Returns:
        Concatenated text content of all pages.

    Raises:
        PDFExtractionError: If the PDF has no pages, is corrupt/invalid, or contains no extractable text layer.
    """
    if not file_bytes:
        raise PDFExtractionError("PDF file content is empty.")

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as e:
        raise PDFExtractionError(f"Failed to parse PDF document: {e}") from e

    if not reader.pages:
        raise PDFExtractionError("PDF document contains no pages.")

    page_texts = []
    for idx, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
            if text:
                page_texts.append(text.strip())
        except Exception as e:
            raise PDFExtractionError(f"Failed to extract text from PDF page {idx + 1}: {e}") from e

    full_text = "\n\n".join(page_texts).strip()

    if not full_text:
        raise PDFExtractionError("PDF contains no extractable text layer (scanned image or empty document).")

    return full_text
