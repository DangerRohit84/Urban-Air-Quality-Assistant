"""Tests for the grounded ``/ask`` route."""

from __future__ import annotations

from fastapi.testclient import TestClient

PROFILE: dict[str, object] = {
    "city": "Delhi",
    "climate_zone": "north",
    "children": True,
    "elderly": False,
    "respiratory": True,
    "commute_mode": "car",
    "commute_km": 10.0,
    "cooking_fuel": "wood",
    "heating_type": "none",
    "budget_level": "low",
}


def _user(client: TestClient, email: str) -> dict[str, str]:
    """Register a user and return its bearer header."""
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "TestPass123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_ask_without_token_is_401(client: TestClient) -> None:
    """The ask route requires a bearer token."""
    response = client.post("/ask", json={"question": "indoor air purifier"})

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


def test_grounded_question_returns_citations(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A grounded question returns a cited answer."""
    assert client.put("/profile", headers=auth_headers, json=PROFILE).status_code == 200

    response = client.post(
        "/ask",
        headers=auth_headers,
        json={"question": "indoor air purifier"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is True
    assert body["citations"]
    assert any(citation in body["answer"] for citation in body["citations"])
    assert body["mode"] == "standard"


def test_plain_language_is_shorter(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Plain mode is shorter than standard mode."""
    standard = client.post(
        "/ask",
        headers=auth_headers,
        json={"question": "indoor air purifier"},
    ).json()
    plain = client.post(
        "/ask",
        headers=auth_headers,
        json={"question": "indoor air purifier", "plain_language": True},
    ).json()

    assert plain["mode"] == "plain"
    assert len(plain["answer"]) < len(standard["answer"])


def test_out_of_domain_refuses_without_citations(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A question with no retrieved support is refused."""
    response = client.post(
        "/ask",
        headers=auth_headers,
        json={"question": "quantum entanglement"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is False
    assert body["citations"] == []
    assert body["answer"]


def test_natural_out_of_domain_refuses_without_citations(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A natural out-of-domain question is refused, not grounded."""
    response = client.post(
        "/ask",
        headers=auth_headers,
        json={"question": "What is the best pizza topping in Naples?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is False
    assert body["citations"] == []
    assert body["answer"]


def test_empty_question_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An empty question is rejected."""
    response = client.post("/ask", headers=auth_headers, json={"question": ""})

    assert response.status_code == 422


def test_owner_scope_for_ask(client: TestClient) -> None:
    """Another user's documents never ground the answer."""
    owner = _user(client, "ask-owner@example.com")
    other = _user(client, "ask-other@example.com")
    assert (
        client.post(
            "/documents",
            headers=owner,
            json={"title": "Private", "text": "zyloflux guideline for clean rooms"},
        ).status_code
        == 201
    )

    foreign = client.post(
        "/ask",
        headers=other,
        json={"question": "zyloflux guideline"},
    )
    mine = client.post(
        "/ask",
        headers=owner,
        json={"question": "zyloflux guideline"},
    )

    assert foreign.json()["grounded"] is False
    assert foreign.json()["citations"] == []
    assert mine.json()["grounded"] is True
