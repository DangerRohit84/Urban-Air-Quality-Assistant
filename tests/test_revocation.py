"""Tests for bearer-token revocation and the logout endpoint."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

from backend.app.auth.claims import b64encode
from backend.app.auth.tokens import get_secret, verify_claims
from backend.app.storage.store import get_repo

INVALID = {"detail": "invalid credentials"}
PASSWORD = "TestPass123"


def _register(client: TestClient, email: str) -> tuple[str, dict[str, str]]:
    """Register ``email`` and return its user id and bearer header."""
    response = client.post(
        "/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201
    body = response.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['token']}"}


def _login(client: TestClient, email: str) -> dict[str, str]:
    """Log in and return a bearer header for a fresh token."""
    response = client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _legacy_token(user_id: str) -> str:
    """Mint a pre-revocation token that carries no ``jti`` claim."""
    payload = {"sub": user_id, "exp": time.time_ns() + 86_400_000_000_000}
    encoded = b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        get_secret().encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{encoded}.{b64encode(signature)}"


def test_logout_revokes_the_presented_token(client: TestClient) -> None:
    """Logout returns 204 with no body and invalidates the token."""
    _, headers = _register(client, "logout@example.com")

    response = client.post("/auth/logout", headers=headers)

    assert response.status_code == 204
    assert response.content == b""
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 401
    assert me.json() == INVALID


def test_logout_requires_a_bearer_token(client: TestClient) -> None:
    """Logout without credentials is rejected with the generic 401."""
    response = client.post("/auth/logout")

    assert response.status_code == 401
    assert response.json() == INVALID


def test_logout_rejects_a_malformed_token(client: TestClient) -> None:
    """Logout with an invalid token returns the generic 401."""
    response = client.post(
        "/auth/logout", headers={"Authorization": "Bearer not-a-token"}
    )

    assert response.status_code == 401
    assert response.json() == INVALID


def test_revoked_token_is_rejected_on_other_routes(client: TestClient) -> None:
    """A revoked token cannot reach ask or document routes."""
    _, headers = _register(client, "blocked@example.com")
    assert client.post("/auth/logout", headers=headers).status_code == 204

    ask = client.post(
        "/ask",
        json={"question": "Which indoor air purifier should I use?"},
        headers=headers,
    )
    document = client.post(
        "/documents",
        json={"title": "Kitchen notes", "text": "Use an exhaust fan."},
        headers=headers,
    )

    assert ask.status_code == 401
    assert document.status_code == 401


def test_logout_revokes_only_the_presented_session(client: TestClient) -> None:
    """A second login session keeps working after the first logs out."""
    _register(client, "sessions@example.com")
    first = _login(client, "sessions@example.com")
    second = _login(client, "sessions@example.com")

    assert client.post("/auth/logout", headers=first).status_code == 204
    assert client.get("/auth/me", headers=first).status_code == 401
    assert client.get("/auth/me", headers=second).status_code == 200


def test_login_after_logout_issues_a_fresh_working_token(
    client: TestClient,
) -> None:
    """Logging in again after logout yields a usable token."""
    _register(client, "fresh@example.com")
    first = _login(client, "fresh@example.com")
    client.post("/auth/logout", headers=first)

    fresh = _login(client, "fresh@example.com")

    assert client.get("/auth/me", headers=fresh).status_code == 200


def test_revoked_token_cannot_be_logged_out_twice(client: TestClient) -> None:
    """Replaying a revoked token is rejected on the logout route too."""
    _, headers = _register(client, "replay@example.com")

    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.post("/auth/logout", headers=headers).status_code == 401


def test_logout_records_the_revocation(client: TestClient) -> None:
    """Logout stores the presented token's id in the repository."""
    _, headers = _register(client, "record@example.com")
    token = headers["Authorization"].removeprefix("Bearer ")
    claims = verify_claims(token)
    assert claims is not None
    assert claims.jti is not None

    assert get_repo().is_token_revoked(claims.jti) is False
    client.post("/auth/logout", headers=headers)

    assert get_repo().is_token_revoked(claims.jti) is True
    assert get_repo().count_revoked_tokens() == 1


def test_legacy_token_without_jti_remains_usable(client: TestClient) -> None:
    """Tokens minted before ``jti`` still verify but cannot be revoked."""
    user_id, _ = _register(client, "legacy@example.com")
    headers = {"Authorization": f"Bearer {_legacy_token(user_id)}"}

    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert get_repo().count_revoked_tokens() == 0
