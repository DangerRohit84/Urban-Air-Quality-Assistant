"""Tests for profile validation, persistence and owner-scoped access."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import load_profile_or_default
from backend.app.profile import DEFAULT_PROFILE, normalize_profile
from backend.app.storage.store import get_repo

VALID: dict[str, object] = {
    "city": "Delhi",
    "climate_zone": "north",
    "children": True,
    "elderly": False,
    "respiratory": True,
    "commute_mode": "car",
    "commute_km": 12.5,
    "cooking_fuel": "lpg",
    "heating_type": "none",
    "budget_level": "medium",
}


def test_put_and_get_round_trip(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A valid PUT is stored and every field survives the GET."""
    response = client.put("/profile", headers=auth_headers, json=VALID)

    assert response.status_code == 200
    body = response.json()
    for key, value in VALID.items():
        assert body[key] == value
    assert body["user_id"]

    fetched = client.get("/profile", headers=auth_headers)
    assert fetched.status_code == 200
    for key, value in VALID.items():
        assert fetched.json()[key] == value


def test_invalid_commute_mode_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An unknown commute mode is rejected."""
    response = client.put(
        "/profile",
        headers=auth_headers,
        json={**VALID, "commute_mode": "rocket"},
    )

    assert response.status_code == 422


def test_negative_commute_km_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A negative commute distance is rejected."""
    response = client.put(
        "/profile",
        headers=auth_headers,
        json={**VALID, "commute_km": -1},
    )

    assert response.status_code == 422


def test_commute_km_above_200_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A commute distance above 200 km is rejected."""
    response = client.put(
        "/profile",
        headers=auth_headers,
        json={**VALID, "commute_km": 201},
    )

    assert response.status_code == 422


def test_empty_city_is_422(client: TestClient, auth_headers: dict[str, str]) -> None:
    """An empty city is rejected."""
    response = client.put(
        "/profile",
        headers=auth_headers,
        json={**VALID, "city": ""},
    )

    assert response.status_code == 422


def test_city_too_long_is_422(client: TestClient, auth_headers: dict[str, str]) -> None:
    """A city longer than 80 characters is rejected."""
    response = client.put(
        "/profile",
        headers=auth_headers,
        json={**VALID, "city": "x" * 81},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "field",
    ["climate_zone", "commute_mode", "cooking_fuel", "heating_type", "budget_level"],
)
def test_oversized_profile_text_fields_are_422(
    client: TestClient, auth_headers: dict[str, str], field: str
) -> None:
    """Every short profile text field is bounded at 40 characters."""
    response = client.put(
        "/profile",
        headers=auth_headers,
        json={**VALID, field: "x" * 41},
    )

    assert response.status_code == 422


def test_invalid_budget_level_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An unknown budget level is rejected."""
    response = client.put(
        "/profile",
        headers=auth_headers,
        json={**VALID, "budget_level": "gold"},
    )

    assert response.status_code == 422


def test_invalid_climate_zone_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An unknown climate zone is rejected."""
    response = client.put(
        "/profile",
        headers=auth_headers,
        json={**VALID, "climate_zone": "arctic"},
    )

    assert response.status_code == 422


def test_invalid_cooking_fuel_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An unknown cooking fuel is rejected."""
    response = client.put(
        "/profile",
        headers=auth_headers,
        json={**VALID, "cooking_fuel": "plasma"},
    )

    assert response.status_code == 422


def test_invalid_heating_type_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An unknown heating type is rejected."""
    response = client.put(
        "/profile",
        headers=auth_headers,
        json={**VALID, "heating_type": "dragon"},
    )

    assert response.status_code == 422


def test_get_before_put_is_404(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A caller without a stored profile gets a 404."""
    response = client.get("/profile", headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "profile not found"}


def test_profile_is_owner_scoped(client: TestClient) -> None:
    """One user cannot see another user's profile."""
    owner = client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "TestPass123"},
    ).json()
    other = client.post(
        "/auth/register",
        json={"email": "other@example.com", "password": "TestPass123"},
    ).json()
    owner_headers = {"Authorization": f"Bearer {owner['token']}"}
    other_headers = {"Authorization": f"Bearer {other['token']}"}
    assert client.put("/profile", headers=owner_headers, json=VALID).status_code == 200

    response = client.get("/profile", headers=other_headers)

    assert response.status_code == 404
    assert owner["user"]["id"] not in response.text


def test_load_profile_or_default_returns_default() -> None:
    """A user without a row gets the default profile with their id."""
    repo = get_repo()
    user = repo.create_user("default@example.com", "hash")

    profile = load_profile_or_default(repo, user.id)

    assert profile.user_id == user.id
    assert profile.city == DEFAULT_PROFILE.city == ""
    assert profile.climate_zone == "north"
    assert profile.commute_mode == "bus"
    assert profile.commute_km == 0.0
    assert profile.cooking_fuel == "lpg"
    assert profile.heating_type == "none"
    assert profile.budget_level == "medium"


def test_normalize_profile_sets_updated_at() -> None:
    """Normalization stamps a non-empty update timestamp."""
    profile = normalize_profile({**VALID, "user_id": "u1"})

    assert profile.user_id == "u1"
    assert profile.updated_at


def test_missing_profile_is_404_and_defaults_are_safe(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A missing profile 404s and the defaults keep dependent routes safe."""
    response = client.get("/profile", headers=auth_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "profile not found"}

    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]
    default = load_profile_or_default(get_repo(), user_id)
    assert default.city == ""
    assert default.children is False

    # ``/plans`` and ``/ask`` land in later tasks; assert their
    # missing-profile behaviour once the routes exist.
    plans = client.get("/plans", headers=auth_headers)
    if plans.status_code != 404:
        assert plans.status_code == 200
        assert "set your profile" in plans.json()["profile_note"].lower()

    ask = client.post(
        "/ask",
        headers=auth_headers,
        json={"question": "indoor air purifier"},
    )
    if ask.status_code != 404:
        assert ask.status_code == 200
        assert "set your profile" in ask.json()["answer"].lower()
