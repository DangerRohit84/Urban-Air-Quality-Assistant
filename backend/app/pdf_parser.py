"""Bounded pypdf text extraction (runs inside the worker process)."""

from __future__ import annotations

import io
import time
from typing import Any

from backend.app.security import MAX_DOCUMENT_CHARS

MAX_PAGES = 20
MAX_STREAM_BYTES = 1_000_000
EXTRACTION_BUDGET_SECONDS = 4.0
VISITOR_CHAR_SLACK = 10_000


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


def parse_pdf_text(data: bytes) -> str:
    """Extract text within page, stream, character and time bounds.

    Args:
        data: The PDF bytes.

    Returns:
        The extracted text, capped at ``MAX_DOCUMENT_CHARS + 1`` characters
        including page separators.

    Raises:
        PdfTooComplexError: When the PDF exceeds a resource limit.
    """
    from pypdf import PdfReader, apply_configuration
    from pypdf.errors import LimitReachedError

    deadline = time.monotonic() + EXTRACTION_BUDGET_SECONDS
    visited = 0

    def visit(text: str, *_args: object) -> None:
        """Abort once the character or time budget is spent.

        Args:
            text: The text chunk reported by pypdf.
            *_args: Ignored visitor context arguments.

        Raises:
            PdfTooComplexError: When the budget is exhausted.
        """
        nonlocal visited
        visited += len(text)
        if visited > MAX_DOCUMENT_CHARS + VISITOR_CHAR_SLACK:
            raise PdfTooComplexError("PDF too complex")
        if time.monotonic() > deadline:
            raise PdfTooComplexError("PDF too complex")

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
                raise PdfTooComplexError(f"PDF has more than {MAX_PAGES} pages")
            parts: list[str] = []
            total = 0
            for page in pages:
                if time.monotonic() > deadline:
                    raise PdfTooComplexError("PDF too complex")
                text = page.extract_text(visitor_text=visit) or ""
                if not text:
                    continue
                separator = 1 if parts else 0
                remaining = MAX_DOCUMENT_CHARS + 1 - total - separator
                if remaining <= 0:
                    break
                parts.append(text[:remaining])
                total += len(parts[-1]) + separator
                if total > MAX_DOCUMENT_CHARS:
                    break
            return "\n".join(parts).strip()
    except LimitReachedError as exc:
        raise PdfTooComplexError("PDF too complex") from exc
