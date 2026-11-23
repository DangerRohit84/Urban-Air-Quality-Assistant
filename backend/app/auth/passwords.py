"""PBKDF2-HMAC-SHA256 password hashing and validation."""

from __future__ import annotations

import hashlib
import hmac
import os
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
LEGACY_ITERATIONS = 120_000
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


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    """Hash a password into a self-describing PBKDF2 record.

    Args:
        password: The plaintext password.
        iterations: The work factor to record with the hash.

    Returns:
        The ``pbkdf2_sha256$<iterations>$<salt hex>$<digest hex>`` string.
    """
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def _parse_hash(stored: str | None) -> tuple[int, bytes, bytes] | None:
    """Parse a stored record into iterations, salt and expected digest.

    A two-part ``salt$digest`` value is the pre-upgrade format and is verified
    with the historical 120,000 iterations.

    Args:
        stored: The stored hash string in either supported format.

    Returns:
        The parsed tuple, or None when the record is malformed or unsupported.
    """
    if not isinstance(stored, str) or not stored:
        return None
    parts = stored.split("$")
    if len(parts) == 2:
        iterations = LEGACY_ITERATIONS
    elif len(parts) == 4 and parts[0] == ALGORITHM:
        try:
            iterations = int(parts[1])
        except ValueError:
            return None
    else:
        return None
    if iterations <= 0:
        return None
    try:
        return iterations, bytes.fromhex(parts[-2]), bytes.fromhex(parts[-1])
    except ValueError:
        return None


def verify_password(password: str, stored: str | None) -> bool:
    """Verify a password against any supported stored hash in constant time.

    Args:
        password: The plaintext password.
        stored: A self-describing record or a legacy ``salt$digest`` record.

    Returns:
        True when the password matches, False otherwise or when the stored
        value is malformed.
    """
    parsed = _parse_hash(stored)
    if parsed is None:
        return False
    iterations, salt, expected = parsed
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    if iterations < ITERATIONS:
        # Equalize the legacy path with the current work factor so failed
        # logins do not reveal which accounts still carry an old hash.
        _ = hash_password(password)
    return hmac.compare_digest(actual, expected)


def needs_rehash(stored: str) -> bool:
    """Return whether a stored hash should be upgraded to the current cost.

    Args:
        stored: The stored hash string.

    Returns:
        True for legacy or older-iteration records, False for current records
        and for malformed values.
    """
    parsed = _parse_hash(stored)
    return False if parsed is None else parsed[0] < ITERATIONS


# Precomputed once so an unknown-email login costs exactly one PBKDF2 verify.
DUMMY_HASH = hash_password("dummy-password-123")


def dummy_hash() -> str:
    """Return the well-formed hash used to equalize unknown-email lookups.

    Returns:
        A cached hash string in the same format as :func:`hash_password`.
    """
    return DUMMY_HASH
