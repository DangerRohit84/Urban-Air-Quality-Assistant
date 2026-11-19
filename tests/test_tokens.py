"""Tests for HMAC-SHA256 bearer tokens."""

from __future__ import annotations

import pytest

from backend.app.auth import tokens
from backend.app.auth.tokens import create_token, get_secret, verify_token


@pytest.fixture(autouse=True)
def _auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the signing secret for every token test."""
    monkeypatch.setattr(tokens.settings, "auth_secret", "test-secret")


def test_create_and_verify_round_trip() -> None:
    """A created token verifies back to its subject."""
    token = create_token("u1")

    assert token.count(".") == 1
    assert verify_token(token) == "u1"


def test_two_tokens_for_same_user_differ() -> None:
    """Two tokens issued in the same instant are still distinct."""
    assert create_token("u1") != create_token("u1")


def test_flipped_signature_character_is_rejected() -> None:
    """A single flipped signature character invalidates the token."""
    token = create_token("u1")
    payload, signature = token.split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]

    assert verify_token(f"{payload}.{flipped}") is None


def test_flipped_payload_character_is_rejected() -> None:
    """A single flipped payload character invalidates the token."""
    token = create_token("u1")
    payload, signature = token.split(".")
    flipped = ("A" if payload[0] != "A" else "B") + payload[1:]

    assert verify_token(f"{flipped}.{signature}") is None


def test_expired_token_is_rejected() -> None:
    """A token with a negative TTL is already expired."""
    assert verify_token(create_token("u1", ttl_seconds=-1)) is None


@pytest.mark.parametrize("token", ["garbage", "", "a.b.c"])
def test_malformed_tokens_are_rejected(token: str) -> None:
    """Malformed tokens return None instead of raising."""
    assert verify_token(token) is None


def test_get_secret_prefers_auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """``AUTH_SECRET`` wins when it is set."""
    monkeypatch.setattr(tokens.settings, "auth_secret", "env-secret")

    assert get_secret() == "env-secret"


def test_get_secret_warns_and_is_stable_without_auth_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ``AUTH_SECRET`` a stable per-boot secret is used once."""
    monkeypatch.setattr(tokens.settings, "auth_secret", "")
    monkeypatch.setattr(tokens, "_ephemeral_secret", None)

    with pytest.warns(RuntimeWarning):
        first = get_secret()

    assert first
    assert get_secret() == first
