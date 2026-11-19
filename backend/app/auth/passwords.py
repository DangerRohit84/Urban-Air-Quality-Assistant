"""PBKDF2-HMAC-SHA256 password hashing and validation."""

from __future__ import annotations

import hashlib
import hmac
import os
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ITERATIONS = 120_000
SALT_BYTES = 16


def normalize_email(email: str) -> str:
    """Normalize an email address for storage and lookup.

    Args:
        email: The raw email address.

    Returns:
        The trimmed, lowercased address.

    Raises:
        ValueError: When the address is malformed.
    """
    candidate = email.strip().lower()
    if not EMAIL_RE.match(candidate):
        raise ValueError("invalid email address")
    return candidate


def validate_password(password: str) -> None:
    """Validate a password's length and character classes.

    Args:
        password: The candidate password.

    Raises:
        ValueError: When the password is too short/long or lacks a letter
            or a digit.
    """
    if not 8 <= len(password) <= 128:
        raise ValueError("password must be 8-128 characters")
    if not any(char.isalpha() for char in password):
        raise ValueError("password must contain a letter")
    if not any(char.isdigit() for char in password):
        raise ValueError("password must contain a digit")


def hash_password(password: str) -> str:
    """Hash a password with a fresh 16-byte salt.

    Args:
        password: The plaintext password.

    Returns:
        The ``<32 hex salt>$<64 hex digest>`` string.
    """
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored hash in constant time.

    Args:
        password: The plaintext password.
        stored: The stored ``salt$digest`` string.

    Returns:
        True when the password matches, False otherwise or when the stored
        value is malformed.
    """
    try:
        salt_hex, digest_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return hmac.compare_digest(actual, expected)


def dummy_hash() -> str:
    """Return a well-formed hash used to equalize unknown-email lookups.

    Returns:
        A hash string in the same format as :func:`hash_password`.
    """
    return hash_password("dummy-password-123")
