"""Tests for the ``/export`` route in JSON and Markdown."""

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


def test_export_json_returns_owner_payload(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The JSON export carries all three sections."""
    assert client.put("/profile", headers=auth_headers, json=PROFILE).status_code == 200

    response = client.get("/export?format=json", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["routines"]
    assert body["hacks"]
    assert body["alternatives"]


def test_export_markdown_has_headings_and_note(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The Markdown export renders the sections and the profile note."""
    response = client.get("/export?format=md", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    text = response.text
    assert "Routines" in text
    assert "Indoor hacks" in text
    assert "Alternatives" in text
    assert "set your profile" in text.lower()


def test_export_is_owner_scoped(client: TestClient) -> None:
    """Another user's export differs when their profile differs."""
    owner = client.post(
        "/auth/register",
        json={"email": "export-owner@example.com", "password": "TestPass123"},
    ).json()
    other = client.post(
        "/auth/register",
        json={"email": "export-other@example.com", "password": "TestPass123"},
    ).json()
    owner_headers = {"Authorization": f"Bearer {owner['token']}"}
    other_headers = {"Authorization": f"Bearer {other['token']}"}
    assert (
        client.put("/profile", headers=owner_headers, json=PROFILE).status_code == 200
    )
    assert (
        client.put(
            "/profile",
            headers=other_headers,
            json={**PROFILE, "commute_mode": "walk", "city": "Mumbai"},
        ).status_code
        == 200
    )

    owner_body = client.get("/export?format=json", headers=owner_headers).json()
    other_body = client.get("/export?format=json", headers=other_headers).json()

    assert [item["key"] for item in owner_body["routines"]] != [
        item["key"] for item in other_body["routines"]
    ]


def test_export_without_token_is_401(client: TestClient) -> None:
    """The export route requires a bearer token."""
    response = client.get("/export?format=json")

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


def test_export_unknown_format_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An unknown export format is rejected."""
    response = client.get("/export?format=pdf", headers=auth_headers)

    assert response.status_code == 422
