"""Tests for the personalized plans engine and the ``/plans`` route."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.models import AqiContext, Profile
from backend.app.plans import build_plans
from backend.app.profile import DEFAULT_PROFILE

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

CONTEXT = {"city": "Delhi", "band": "Poor", "season": "winter"}


def _store(client: TestClient, headers: dict[str, str]) -> None:
    """PUT the test profile and its Poor-band context."""
    assert client.put("/profile", headers=headers, json=PROFILE).status_code == 200
    assert (
        client.post("/air/context", headers=headers, json=CONTEXT).status_code
        == 200
    )


def test_plans_sections_mentions_and_ranking(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A tailored profile yields three ranked, cited sections."""
    _store(client, auth_headers)

    response = client.get("/plans", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["routines"]) >= 3
    assert len(body["hacks"]) >= 3
    assert len(body["alternatives"]) >= 3

    assert any(
        "car" in (item["title"] + item["detail"]).lower()
        for item in body["routines"]
    )
    assert any(
        "children" in (item["title"] + item["detail"]).lower()
        or "respiratory" in (item["title"] + item["detail"]).lower()
        for item in body["hacks"]
    )
    assert any(
        "wood" in (item["title"] + item["detail"]).lower()
        for item in body["alternatives"]
    )

    for section in ("routines", "hacks", "alternatives"):
        values = [item["impact"]["co2e_kg_week"] for item in body[section]]
        assert values == sorted(values, reverse=True)
        for item in body[section]:
            assert item["impact"]["co2e_kg_week"] is not None
            assert item["citations"]


def test_build_plans_default_profile_has_note() -> None:
    """A default profile still produces a well-shaped payload."""
    payload = build_plans(DEFAULT_PROFILE, None, [])

    assert "set your profile" in payload.profile_note.lower()
    assert isinstance(payload.routines, list)
    assert isinstance(payload.hacks, list)
    assert isinstance(payload.alternatives, list)


def test_unknown_area_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An unknown area filter is rejected."""
    response = client.get("/plans?area=rocket", headers=auth_headers)

    assert response.status_code == 422


def test_area_filter_returns_one_section(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """``area=routines`` populates only the routines section."""
    _store(client, auth_headers)

    body = client.get("/plans?area=routines", headers=auth_headers).json()

    assert body["routines"]
    assert body["hacks"] == []
    assert body["alternatives"] == []


def test_plans_without_token_is_401(client: TestClient) -> None:
    """The plans route requires a bearer token."""
    response = client.get("/plans")

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


def test_plans_are_owner_scoped(client: TestClient) -> None:
    """Two profiles produce different recommendations."""
    owner = client.post(
        "/auth/register",
        json={"email": "plans-owner@example.com", "password": "TestPass123"},
    ).json()
    other = client.post(
        "/auth/register",
        json={"email": "plans-other@example.com", "password": "TestPass123"},
    ).json()
    owner_headers = {"Authorization": f"Bearer {owner['token']}"}
    other_headers = {"Authorization": f"Bearer {other['token']}"}
    _store(client, owner_headers)
    assert client.put(
        "/profile",
        headers=other_headers,
        json={**PROFILE, "commute_mode": "walk", "city": "Mumbai"},
    ).status_code == 200

    owner_body = client.get("/plans", headers=owner_headers).json()
    other_body = client.get("/plans", headers=other_headers).json()

    assert [item["key"] for item in owner_body["routines"]] != [
        item["key"] for item in other_body["routines"]
    ]


def test_build_plans_uses_context_for_exposure() -> None:
    """The AQI context scales the exposure reduction."""
    profile = Profile(
        user_id="u1",
        city="Delhi",
        climate_zone="north",
        children=True,
        elderly=False,
        respiratory=True,
        commute_mode="car",
        commute_km=10.0,
        cooking_fuel="wood",
        heating_type="none",
        budget_level="low",
        updated_at="t",
    )
    context = AqiContext(
        user_id="u1",
        city="Delhi",
        band="Poor",
        value=None,
        pm25=None,
        pm10=None,
        season="winter",
        observed_at="t",
        source="user",
    )

    payload = build_plans(profile, context, [])

    assert payload.routines[0].impact.exposure_reduction_pct > 0
