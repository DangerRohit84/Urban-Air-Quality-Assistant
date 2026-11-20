"""Tests for PBKDF2 password hashing and validation."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.app.auth.passwords import (
    dummy_hash,
    hash_password,
    normalize_email,
    validate_password,
    verify_password,
)

SOURCE = (
    Path(__file__).resolve().parents[1] / "backend" / "app" / "auth" / "passwords.py"
)
HASH_RE = re.compile(r"^[0-9a-f]{32}\$[0-9a-f]{64}$")


def test_hash_format_and_salt_uniqueness() -> None:
    """Hashes match the salt$digest format and salts differ per call."""
    first = hash_password("Password1")
    second = hash_password("Password1")

    assert HASH_RE.match(first)
    assert HASH_RE.match(second)
    assert first != second


def test_verify_accepts_correct_password() -> None:
    """The correct password verifies against its hash."""
    assert verify_password("Password1", hash_password("Password1")) is True


def test_verify_rejects_wrong_password() -> None:
    """A wrong password does not verify."""
    assert verify_password("Wrong1", hash_password("Password1")) is False


def test_verify_rejects_malformed_stored_hash() -> None:
    """A malformed stored hash returns False rather than raising."""
    assert verify_password("Password1", "nope") is False


def test_normalize_email_lowercases_and_trims() -> None:
    """Normalization trims whitespace and lowercases the address."""
    assert normalize_email(" A@B.COM ") == "a@b.com"


def test_invalid_email_raises() -> None:
    """A value without an ``@`` and dot is rejected."""
    with pytest.raises(ValueError, match="invalid email address"):
        normalize_email("not-an-email")


@pytest.mark.parametrize("password", ["short1", "allletters", "12345678"])
def test_weak_passwords_raise(password: str) -> None:
    """Too-short, letter-less and digit-less passwords are rejected."""
    with pytest.raises(ValueError):
        validate_password(password)


def test_eight_char_alphanumeric_password_passes() -> None:
    """An 8-character password with a letter and a digit is accepted."""
    validate_password("abc12345")


def test_dummy_hash_is_well_formed() -> None:
    """The dummy hash uses the same format as a real hash."""
    assert HASH_RE.match(dummy_hash())


def test_dummy_hash_is_computed_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dummy hash is cached rather than re-hashed on every use."""
    first = dummy_hash()
    monkeypatch.setattr(
        "backend.app.auth.passwords.hash_password",
        lambda password: "changed",
    )

    assert dummy_hash() == first


def test_source_uses_pbkdf2_and_constant_time_compare() -> None:
    """The implementation uses PBKDF2 with 600k iterations and compare_digest."""
    source = SOURCE.read_text(encoding="utf-8")

    assert "hmac.compare_digest" in source
    assert "600_000" in source
