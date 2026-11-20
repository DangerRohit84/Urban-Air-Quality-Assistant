"""Tests for register, login and the authenticated ``/auth/me`` endpoint."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend.app.auth.tokens import create_token

INVALID = {"detail": "invalid credentials"}


def test_register_returns_201_with_token(client: TestClient) -> None:
    """A new account returns a token and public user fields."""
    response = client.post(
        "/auth/register",
        json={"email": "new@example.com", "password": "TestPass123"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["id"]
    assert body["user"]["created_at"]
    assert body["token"]


def test_duplicate_email_is_409(client: TestClient) -> None:
    """Registering the same email twice conflicts."""
    payload = {"email": "dup@example.com", "password": "TestPass123"}
    assert client.post("/auth/register", json=payload).status_code == 201

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 409


def test_concurrent_duplicate_registration_conflicts(client: TestClient) -> None:
    """Parallel signups with one email yield one 201 and the rest 409."""
    payload = {"email": "race@example.com", "password": "TestPass123"}

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(
            pool.map(lambda _: client.post("/auth/register", json=payload), range(8))
        )

    codes = sorted(response.status_code for response in responses)

    assert codes == [201] + [409] * 7


def test_weak_password_is_422(client: TestClient) -> None:
    """A short password is rejected with 422."""
    response = client.post(
        "/auth/register",
        json={"email": "weak@example.com", "password": "short"},
    )

    assert response.status_code == 422


def test_malformed_email_is_422(client: TestClient) -> None:
    """A malformed email is rejected with 422."""
    response = client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "TestPass123"},
    )

    assert response.status_code == 422


def test_oversized_email_is_422(client: TestClient) -> None:
    """An email above 254 characters is rejected."""
    response = client.post(
        "/auth/register",
        json={"email": "a" * 250 + "@x.com", "password": "TestPass123"},
    )

    assert response.status_code == 422


def test_oversized_password_is_422(client: TestClient) -> None:
    """A password above 128 characters is rejected."""
    response = client.post(
        "/auth/register",
        json={"email": "long@example.com", "password": "A" * 120 + "1" * 10},
    )

    assert response.status_code == 422


def test_login_correct_returns_200(client: TestClient) -> None:
    """A correct login returns a fresh token."""
    client.post(
        "/auth/register",
        json={"email": "login@example.com", "password": "TestPass123"},
    )

    response = client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "TestPass123"},
    )

    assert response.status_code == 200
    assert response.json()["token"]
    assert response.json()["user"]["email"] == "login@example.com"


def test_login_wrong_password_is_generic_401(client: TestClient) -> None:
    """A wrong password returns the generic 401 body."""
    client.post(
        "/auth/register",
        json={"email": "wrong@example.com", "password": "TestPass123"},
    )

    response = client.post(
        "/auth/login",
        json={"email": "wrong@example.com", "password": "BadPass123"},
    )

    assert response.status_code == 401
    assert response.json() == INVALID


def test_login_unknown_email_matches_wrong_password_body(
    client: TestClient,
) -> None:
    """Unknown-email and wrong-password logins are indistinguishable."""
    client.post(
        "/auth/register",
        json={"email": "known@example.com", "password": "TestPass123"},
    )
    unknown = client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "TestPass123"},
    )
    wrong = client.post(
        "/auth/login",
        json={"email": "known@example.com", "password": "BadPass123"},
    )

    assert unknown.status_code == 401
    assert wrong.status_code == 401
    assert unknown.json() == INVALID
    assert unknown.json() == wrong.json()


def test_me_with_token_returns_user(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An authenticated ``/auth/me`` returns the caller's fields."""
    response = client.get("/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"
    assert response.json()["id"]


def test_me_without_token_is_401(client: TestClient) -> None:
    """A missing token yields the generic 401 body."""
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == INVALID


def test_me_with_garbage_token_is_401(client: TestClient) -> None:
    """A garbage token yields the generic 401 body."""
    response = client.get("/auth/me", headers={"Authorization": "Bearer garbage"})

    assert response.status_code == 401
    assert response.json() == INVALID


def test_me_with_tampered_token_is_401(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A tampered token yields the generic 401 body."""
    token = auth_headers["Authorization"].split(" ", 1)[1]
    payload, signature = token.split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {payload}.{flipped}"},
    )

    assert response.status_code == 401
    assert response.json() == INVALID


def test_me_with_expired_token_is_401(client: TestClient) -> None:
    """An expired token yields the generic 401 body."""
    registered = client.post(
        "/auth/register",
        json={"email": "exp@example.com", "password": "TestPass123"},
    ).json()
    expired = create_token(registered["user"]["id"], ttl_seconds=-1)

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired}"},
    )

    assert response.status_code == 401
    assert response.json() == INVALID


def test_health_is_public(client: TestClient) -> None:
    """``/health`` responds without a token."""
    response = client.get("/health")

    assert response.status_code == 200
