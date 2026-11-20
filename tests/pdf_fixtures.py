"""Synthetic PDF builders for upload and extraction tests."""

from __future__ import annotations

import zlib


def _assemble(objects: list[bytes]) -> bytes:
    """Assemble PDF objects with a valid xref table.

    Args:
        objects: The object bodies in object-number order.

    Returns:
        The complete PDF bytes.
    """
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_start = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    ).encode()
    return bytes(out)


def text_pdf(text: str) -> bytes:
    """Build a minimal single-page PDF containing ``text``.

    Args:
        text: The text to draw on the page.

    Returns:
        The complete PDF bytes.
    """
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    return _assemble(objects)


def flate_bomb_pdf(size: int = 8_000_000) -> bytes:
    """Build a tiny PDF whose Flate stream expands past the stream cap.

    Args:
        size: The number of bytes produced by decompression.

    Returns:
        The complete PDF bytes.
    """
    payload = b"BT /F1 12 Tf 72 720 Td (" + b"A" * size + b") Tj ET"
    stream = zlib.compress(payload)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" /Filter /FlateDecode >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    return _assemble(objects)


def many_pages_pdf(count: int) -> bytes:
    """Build a PDF with ``count`` empty text pages.

    Args:
        count: The number of pages.

    Returns:
        The complete PDF bytes.
    """
    kids = " ".join(f"{index} 0 R" for index in range(3, 3 + count))
    content_id = 3 + count
    font_id = content_id + 1
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode(),
    ]
    for _ in range(count):
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_id} 0 R "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>"
            ).encode()
        )
    objects.append(b"<< /Length 0 >>\nstream\n\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    return _assemble(objects)
