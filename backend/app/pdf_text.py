"""Bounded PDF text extraction."""

from __future__ import annotations

import io

MAX_PAGES = 20


def extract_pdf_text(data: bytes) -> str:
    """Extract text from a PDF, bounded to ``MAX_PAGES``.

    Args:
        data: The PDF bytes.

    Returns:
        The extracted text.
    """
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = reader.pages[:MAX_PAGES]
    return "\n".join(page.extract_text() or "" for page in pages).strip()
