"""Tests for the owner-scoped document API and PDF upload."""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app import retrieval
from backend.app.config import settings
from backend.app.pdf_text import MAX_PAGES
from backend.app.security import MAX_DOCUMENT_CHARS
from backend.app.upload_slot import UPLOAD_SLOT
from tests.pdf_fixtures import (
    flate_bomb_pdf,
    many_pages_pdf,
    text_pdf,
    xobject_bomb_pdf,
)


def _pdf_bytes(text: str) -> bytes:
    """Build a minimal single-page PDF containing ``text``."""
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


def _padded_pdf(text: str, size: int) -> bytes:
    """Build a valid PDF padded with a trailing comment to exactly ``size``.

    Args:
        text: The extractable page text.
        size: The total byte length, which must fit the base PDF plus padding.

    Returns:
        The padded PDF bytes.
    """
    base = _pdf_bytes(text)
    return base + b"\n%" + b"P" * (size - len(base) - 2)


def _second_user(client: TestClient, email: str) -> dict[str, str]:
    """Register a user and return its bearer header."""
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "TestPass123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_create_returns_201_with_chunks(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A created document is returned with chunked text."""
    response = client.post(
        "/documents",
        headers=auth_headers,
        json={"title": "Kitchen note", "text": "Use the exhaust fan while cooking."},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Kitchen note"
    assert body["chunks"]
    assert body["owner_id"]


def test_list_is_owner_scoped(client: TestClient) -> None:
    """Each user sees only their own documents."""
    owner = _second_user(client, "docs-owner@example.com")
    other = _second_user(client, "docs-other@example.com")
    assert (
        client.post(
            "/documents",
            headers=owner,
            json={"title": "Mine", "text": "owner text"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/documents",
            headers=other,
            json={"title": "Theirs", "text": "other text"},
        ).status_code
        == 201
    )

    mine = client.get("/documents", headers=owner).json()
    theirs = client.get("/documents", headers=other).json()

    assert [doc["title"] for doc in mine] == ["Mine"]
    assert [doc["title"] for doc in theirs] == ["Theirs"]


def test_delete_own_document(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Deleting an owned document removes it."""
    doc_id = client.post(
        "/documents",
        headers=auth_headers,
        json={"title": "Delete me", "text": "temporary"},
    ).json()["id"]

    deleted = client.delete(f"/documents/{doc_id}", headers=auth_headers)

    assert deleted.status_code == 204
    assert all(
        doc["id"] != doc_id
        for doc in client.get("/documents", headers=auth_headers).json()
    )


def test_delete_foreign_document_is_404(client: TestClient) -> None:
    """Another owner's document id is a 404."""
    owner = _second_user(client, "del-owner@example.com")
    other = _second_user(client, "del-other@example.com")
    doc_id = client.post(
        "/documents",
        headers=owner,
        json={"title": "Foreign", "text": "not yours"},
    ).json()["id"]

    response = client.delete(f"/documents/{doc_id}", headers=other)

    assert response.status_code == 404
    assert len(client.get("/documents", headers=owner).json()) == 1


def test_empty_title_or_text_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Empty title or text is rejected."""
    title = client.post(
        "/documents", headers=auth_headers, json={"title": "", "text": "body"}
    )
    text = client.post(
        "/documents", headers=auth_headers, json={"title": "Title", "text": ""}
    )

    assert title.status_code == 422
    assert text.status_code == 422


def test_empty_text_is_422_with_clear_message(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An empty body is rejected with the documented message."""
    response = client.post(
        "/documents", headers=auth_headers, json={"title": "Empty", "text": ""}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "document text must not be empty"


@pytest.mark.parametrize("text", ["   ", "\t\n  "])
def test_whitespace_only_text_is_422(
    client: TestClient, auth_headers: dict[str, str], text: str
) -> None:
    """Whitespace-only bodies sanitize to empty and are rejected."""
    response = client.post(
        "/documents", headers=auth_headers, json={"title": "Blank", "text": text}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "document text must not be empty"


def test_pdf_without_extractable_text_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A PDF whose extraction yields no text is rejected."""
    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("blank.pdf", _pdf_bytes(""), "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "document text must not be empty"


def test_pdf_flate_bomb_is_422_quickly(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A decompression bomb is rejected as too complex without hanging."""
    started = time.monotonic()
    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("bomb.pdf", flate_bomb_pdf(), "application/pdf")},
    )

    assert response.status_code == 422
    assert "too complex" in response.json()["detail"]
    assert time.monotonic() - started < 3.0


def test_pdf_over_page_limit_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A PDF over the page limit is rejected with a clear message."""
    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={
            "file": (
                "many-pages.pdf",
                many_pages_pdf(MAX_PAGES + 1),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422
    assert "pages" in response.json()["detail"]


def test_pdf_xobject_bomb_is_422_within_a_hard_bound(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A Form-XObject bomb is killed by the worker timeout, never hangs."""
    started = time.monotonic()
    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("xobject.pdf", xobject_bomb_pdf(), "application/pdf")},
    )

    assert response.status_code == 422
    assert "too complex" in response.json()["detail"]
    assert time.monotonic() - started < 10.0


def test_pdf_text_over_the_character_cap_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Extracted text beyond the cap is rejected, never silently truncated."""
    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={
            "file": (
                "dense.pdf",
                text_pdf("A" * (MAX_DOCUMENT_CHARS + 100)),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422
    assert str(MAX_DOCUMENT_CHARS) in response.json()["detail"]


def test_upload_searchable_pdf(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An uploaded PDF is parsed and becomes searchable."""
    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={
            "file": (
                "note.pdf",
                _pdf_bytes("zyloflux pdf marker"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["kind"] == "upload"

    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]
    hits = retrieval.search("zyloflux", owner_id=user_id)
    assert hits


def test_upload_non_pdf_magic_is_400(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A non-PDF payload is rejected."""
    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("note.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 400


def test_upload_oversize_is_413(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: object,
) -> None:
    """A payload above the cap is rejected with 413."""
    monkeypatch.setattr(settings, "max_upload_bytes", 64)
    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("note.pdf", b"%PDF-" + b"x" * 128, "application/pdf")},
    )

    assert response.status_code == 413


def test_upload_at_the_cap_is_accepted(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A valid PDF exactly at the 5 MiB cap is accepted."""
    body = _padded_pdf("cap marker", settings.max_upload_bytes)

    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("cap.pdf", body, "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["text"] == "cap marker"


def test_upload_one_byte_over_the_cap_is_413(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A payload above the 5 MiB cap is rejected with 413."""
    body = b"%PDF-1.4\n" + b"x" * settings.max_upload_bytes

    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("big.pdf", body, "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "file too large"}


def test_upload_while_busy_is_503_with_retry_after(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A concurrent upload gets 503 with Retry-After and CORS headers."""
    origin = settings.allowed_origins[0]
    assert not UPLOAD_SLOT.locked()
    asyncio.run(UPLOAD_SLOT.acquire())
    try:
        response = client.post(
            "/documents/upload",
            headers={**auth_headers, "Origin": origin},
            files={"file": ("note.pdf", _pdf_bytes("busy"), "application/pdf")},
        )
    finally:
        UPLOAD_SLOT.release()

    assert response.status_code == 503
    assert response.json() == {"detail": "server busy, retry shortly"}
    assert response.headers["retry-after"] == "2"
    assert response.headers["access-control-allow-origin"] == origin


def test_upload_without_a_file_part_is_400(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A form without a file part is rejected and frees the slot."""
    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        data={"file": "not-a-file"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "file field is required"}


def test_slot_is_released_after_a_rejected_upload(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 413 releases the single-flight slot for the next upload."""
    monkeypatch.setattr(settings, "max_upload_bytes", 1024)

    rejected = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("big.pdf", b"%PDF-" + b"x" * 2048, "application/pdf")},
    )
    accepted = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("ok.pdf", _pdf_bytes("released"), "application/pdf")},
    )

    assert rejected.status_code == 413
    assert accepted.status_code == 201


def test_upload_txt_name_is_400(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A non-.pdf filename is rejected."""
    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={
            "file": (
                "notes.txt",
                _pdf_bytes("hello"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400


def test_document_limit_is_409(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: object,
) -> None:
    """Exceeding ``MAX_DOCUMENTS`` conflicts."""
    monkeypatch.setattr(settings, "max_documents", 1)
    assert (
        client.post(
            "/documents",
            headers=auth_headers,
            json={"title": "First", "text": "one"},
        ).status_code
        == 201
    )

    response = client.post(
        "/documents",
        headers=auth_headers,
        json={"title": "Second", "text": "two"},
    )

    assert response.status_code == 409


def test_oversize_document_text_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Text beyond the character cap is rejected, never silently truncated."""
    response = client.post(
        "/documents",
        headers=auth_headers,
        json={"title": "Too long", "text": "x" * (MAX_DOCUMENT_CHARS + 1)},
    )

    assert response.status_code == 422
    assert str(MAX_DOCUMENT_CHARS) in response.json()["detail"]


def test_long_pdf_text_is_indexed(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A multi-page-sized PDF text is accepted and becomes searchable."""
    body = ("zyloflux indoor filter guidance. " * 200)[:5000]

    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("long.pdf", _pdf_bytes(body), "application/pdf")},
    )

    assert response.status_code == 201
    assert len(response.json()["text"]) == 5000
    assert response.json()["chunks"]

    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]
    assert retrieval.search("zyloflux", owner_id=user_id)


def test_boundary_length_document_preserves_markup_characters(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A maximal document keeps ``&``, quotes and angle brackets intact."""
    text = ('R&D M&M\'s <keep> "quoted" & more. ' * 1600)[:MAX_DOCUMENT_CHARS]
    if text.endswith(" "):
        text = text[:-1] + "."

    assert len(text) == MAX_DOCUMENT_CHARS
    response = client.post(
        "/documents", headers=auth_headers, json={"title": "Boundary", "text": text}
    )

    assert response.status_code == 201
    assert response.json()["text"] == text


def test_create_and_delete_invalidate_cache(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Search reflects document creation and deletion."""
    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]
    doc_id = client.post(
        "/documents",
        headers=auth_headers,
        json={"title": "Cache", "text": "zyloflux cache marker"},
    ).json()["id"]
    assert retrieval.search("zyloflux", owner_id=user_id)

    client.delete(f"/documents/{doc_id}", headers=auth_headers)

    assert retrieval.search("zyloflux", owner_id=user_id) == []


def test_document_change_invalidates_only_the_owner_cache(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """One owner's change drops only that owner's cached index."""
    owner_id = client.get("/auth/me", headers=auth_headers).json()["id"]
    other = _second_user(client, "cache-isolation@example.com")
    other_id = client.get("/auth/me", headers=other).json()["id"]
    query = "indoor air purifier"
    retrieval.reset_cache()

    retrieval.search(query, owner_id=owner_id)
    retrieval.search(query, owner_id=other_id)
    assert retrieval.get_cache_stats()["size"] == 2

    hits_before = retrieval.get_cache_stats()["hits"]
    misses_before = retrieval.get_cache_stats()["misses"]
    client.post(
        "/documents",
        headers=auth_headers,
        json={"title": "Owner note", "text": "zyloflux owner cache marker"},
    )

    assert retrieval.get_cache_stats()["size"] == 1
    retrieval.search(query, owner_id=other_id)
    assert retrieval.get_cache_stats()["hits"] == hits_before + 1
    retrieval.search(query, owner_id=owner_id)
    assert retrieval.get_cache_stats()["misses"] > misses_before


def test_document_race_keeps_owner_isolation(client: TestClient) -> None:
    """Concurrent uploads by two users never cross owners."""
    owner = _second_user(client, "race-owner@example.com")
    other = _second_user(client, "race-other@example.com")

    def upload(header: dict[str, str], title: str) -> None:
        for index in range(5):
            response = client.post(
                "/documents",
                headers=header,
                json={"title": f"{title}-{index}", "text": f"{title} text"},
            )
            assert response.status_code == 201

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(upload, owner, "owner-race"),
            pool.submit(upload, other, "other-race"),
        ]
        for future in futures:
            future.result()

    mine = client.get("/documents", headers=owner).json()
    theirs = client.get("/documents", headers=other).json()

    assert len(mine) == 5
    assert len(theirs) == 5
    assert all(doc["title"].startswith("owner-race") for doc in mine)
    assert all(doc["title"].startswith("other-race") for doc in theirs)
