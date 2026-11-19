"""Upload boundaries: PDF magic, size and content type."""

from __future__ import annotations

from backend.app.config import settings

PDF_MAGIC = b"%PDF-"
ALLOWED_CONTENT_TYPES = frozenset({"application/pdf", "application/octet-stream"})


def validate_pdf_magic(raw: bytes | bytearray) -> bool:
    """Return True when ``raw`` starts with the PDF magic.

    Args:
        raw: The uploaded bytes.

    Returns:
        True when the magic matches.

    Raises:
        TypeError: When ``raw`` is not bytes-like.
    """
    if not isinstance(raw, bytes | bytearray):
        raise TypeError("raw must be bytes")
    return bytes(raw).startswith(PDF_MAGIC)


def validate_pre_parse(
    filename: str, content_type: str, size: int, data: bytes
) -> bool:
    """Validate an upload before parsing.

    Args:
        filename: The uploaded filename.
        content_type: The declared content type.
        size: The byte length.
        data: The uploaded bytes.

    Returns:
        True when the upload is acceptable.

    Raises:
        ValueError: When any boundary is violated.
    """
    if size > settings.max_upload_bytes:
        raise ValueError("file too large")
    if not filename.strip().lower().endswith(".pdf"):
        raise ValueError("only .pdf files are accepted")
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("unsupported content type")
    if not validate_pdf_magic(data):
        raise ValueError("invalid PDF magic bytes")
    return True
