"""Bounded PDF text extraction."""

from __future__ import annotations

import io
import time
from typing import Any

from backend.app.security import MAX_DOCUMENT_CHARS

MAX_PAGES = 20
MAX_STREAM_BYTES = 1_000_000
EXTRACTION_BUDGET_SECONDS = 4.0


class PdfTooComplexError(ValueError):
    """Raised when a PDF exceeds the extraction resource limits."""


def _limits() -> dict[str, Any]:
    """Return pypdf limits sized for a 50,000-character text document."""
    return {
        "maximum_declared_stream_length": 10_000_000,
        "array_based_stream_maximum_output_length": MAX_STREAM_BYTES,
        "array_maximum_element_count": 10_000,
        "dictionary_maximum_element_count": 10_000,
        "jbig2_maximum_output_length": MAX_STREAM_BYTES,
        "lzw_maximum_output_length": MAX_STREAM_BYTES,
        "run_length_maximum_output_length": MAX_STREAM_BYTES,
        "zlib_maximum_output_length": MAX_STREAM_BYTES,
        "brotli_maximum_output_length": MAX_STREAM_BYTES,
        "image_maximum_buffer_size": 10_000_000,
        "stream_filters_maximum_length": 4,
        "stream_decoding_work_maximum_length": MAX_STREAM_BYTES * 2,
        "stream_parsing_work_maximum_count": 50_000,
        "page_tree_maximum_entries": 1_000,
        "page_tree_maximum_depth": 50,
        "page_tree_maximum_page_entries": 10_000,
        "xform_maximum_invocations_per_extraction": 50,
    }


def extract_pdf_text(data: bytes) -> str:
    """Extract text from a PDF within page, stream and time bounds.

    Args:
        data: The PDF bytes.

    Returns:
        The extracted text, capped at ``MAX_DOCUMENT_CHARS + 1`` characters.

    Raises:
        PdfTooComplexError: When the PDF exceeds the page or resource limits.
    """
    from pypdf import PdfReader, apply_configuration
    from pypdf.errors import LimitReachedError

    deadline = time.monotonic() + EXTRACTION_BUDGET_SECONDS
    try:
        with apply_configuration(**_limits()):
            reader = PdfReader(
                io.BytesIO(data),
                strict=False,
                root_object_recovery_limit=100,
                xref_stream_maximum_entries=100_000,
            )
            pages = reader.pages
            if len(pages) > MAX_PAGES:
                raise PdfTooComplexError(
                    f"PDF has more than {MAX_PAGES} pages"
                )
            if time.monotonic() > deadline:
                raise PdfTooComplexError("PDF too complex")
            parts: list[str] = []
            total = 0
            for page in pages:
                if time.monotonic() > deadline:
                    raise PdfTooComplexError("PDF too complex")
                text = page.extract_text() or ""
                remaining = MAX_DOCUMENT_CHARS + 1 - total
                parts.append(text[:remaining])
                total += len(parts[-1])
                if total > MAX_DOCUMENT_CHARS:
                    break
            return "\n".join(parts).strip()
    except LimitReachedError as exc:
        raise PdfTooComplexError("PDF too complex") from exc
