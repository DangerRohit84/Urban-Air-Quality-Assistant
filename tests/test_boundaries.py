"""Tests for owner-scoped access helpers and the protected profile route."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import access
from backend.app.models import Document, Profile
from backend.app.storage.store import get_repo


def _document(owner_id: str) -> Document:
    """Build a document draft owned by ``owner_id``."""
    return Document(
        id="",
        owner_id=owner_id,
        kind="corpus",
        title="Title",
        text="body",
        chunks=["body"],
        source="seed",
        created_at="",
    )


def _profile(user_id: str) -> Profile:
    """Build a valid profile for ``user_id``."""
    return Profile(
        user_id=user_id,
        city="Delhi",
        climate_zone="north",
        children=False,
        elderly=False,
        respiratory=False,
        commute_mode="bus",
        commute_km=5.0,
        cooking_fuel="lpg",
        heating_type="none",
        budget_level="medium",
        updated_at="2026-11-18T00:00:00+00:00",
    )


def test_owner_or_404_returns_resource_for_owner() -> None:
    """The owner receives the resource unchanged."""
    repo = get_repo()
    owner = repo.create_user("owner@example.com", "hash")
    doc = repo.create_document(_document(owner.id))

    assert access.owner_or_404(repo, doc, owner.id) == doc


def test_owner_or_404_raises_404_for_another_user() -> None:
    """A non-owner gets a 404, never the resource."""
    repo = get_repo()
    owner = repo.create_user("owner@example.com", "hash")
    other = repo.create_user("other@example.com", "hash")
    doc = repo.create_document(_document(owner.id))

    with pytest.raises(HTTPException) as excinfo:
        access.owner_or_404(repo, doc, other.id)

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "not found"


def test_get_owned_document_returns_document_for_owner() -> None:
    """The owner receives their document."""
    repo = get_repo()
    owner = repo.create_user("owner@example.com", "hash")
    doc = repo.create_document(_document(owner.id))

    assert access.get_owned_document(repo, doc.id, owner.id) == doc


def test_get_owned_document_raises_404_for_another_owner() -> None:
    """Another owner's document id is a 404."""
    repo = get_repo()
    owner = repo.create_user("owner@example.com", "hash")
    other = repo.create_user("other@example.com", "hash")
    doc = repo.create_document(_document(owner.id))

    with pytest.raises(HTTPException) as excinfo:
        access.get_owned_document(repo, doc.id, other.id)

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "not found"


def test_get_owned_profile_returns_none_when_absent() -> None:
    """A user without a profile gets None."""
    repo = get_repo()
    user = repo.create_user("owner@example.com", "hash")

    assert access.get_owned_profile(repo, user.id) is None


def test_profile_without_token_is_401(client: TestClient) -> None:
    """The profile route requires a bearer token."""
    response = client.get("/profile")

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


def test_profile_absent_is_404(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A authenticated caller without a profile gets a 404."""
    response = client.get("/profile", headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "profile not found"}


def test_profile_owner_can_read_own_profile(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The owner reads back the profile they stored."""
    me = client.get("/auth/me", headers=auth_headers).json()
    get_repo().save_profile(_profile(me["id"]))

    response = client.get("/profile", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == me["id"]
    assert body["city"] == "Delhi"


def test_profile_response_does_not_leak_another_user_id(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Another user's profile is invisible and their id never leaks."""
    other = client.post(
        "/auth/register",
        json={"email": "other@example.com", "password": "TestPass123"},
    ).json()["user"]
    get_repo().save_profile(_profile(other["id"]))

    response = client.get("/profile", headers=auth_headers)

    assert response.status_code == 404
    assert other["id"] not in response.text
