"""Text chunking with bounded overlap."""

from __future__ import annotations


def chunk_text(text: str, size: int = 400, overlap: int = 80) -> list[str]:
    """Split ``text`` into overlapping chunks.

    Args:
        text: The raw text.
        size: The maximum chunk length.
        overlap: The number of characters shared between neighbours.

    Returns:
        The chunks.

    Raises:
        ValueError: When ``size`` or ``overlap`` is invalid.
    """
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be between 0 and size")
    stripped = text.strip()
    if not stripped:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(stripped):
        end = start + size
        chunks.append(stripped[start:end])
        if end >= len(stripped):
            break
        start = end - overlap
    return chunks
