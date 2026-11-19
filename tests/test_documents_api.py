"""Tests for the owner-scoped document API and PDF upload."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend.app import retrieval
from backend.app.config import settings


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


def test_delete_own_document(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Deleting an owned document removes it."""
    doc_id = client.post(
        "/documents",
        headers=auth_headers,
        json={"title": "Delete me", "text": "temporary"},
    ).json()["id"]

    deleted = client.delete(f"/documents/{doc_id}", headers=auth_headers)

    assert deleted.status_code == 204
    assert all(doc["id"] != doc_id for doc in client.get("/documents", headers=auth_headers).json())


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
