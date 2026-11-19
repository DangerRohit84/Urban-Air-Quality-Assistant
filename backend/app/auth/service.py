"""Registration and authentication use cases."""

from __future__ import annotations

from backend.app.auth.passwords import (
    dummy_hash,
    hash_password,
    normalize_email,
    validate_password,
    verify_password,
)
from backend.app.auth.tokens import create_token
from backend.app.models import User
from backend.app.storage.store import get_repo


def register_user(email: str, password: str) -> tuple[User, str]:
    """Register a new user and return it with a bearer token.

    Args:
        email: The raw email address.
        password: The plaintext password.

    Returns:
        The created user and its token.

    Raises:
        ValueError: On a malformed email, a weak password, or a duplicate.
    """
    normalized = normalize_email(email)
    validate_password(password)
    repo = get_repo()
    if repo.get_user_by_email(normalized) is not None:
        raise ValueError("email already registered")
    user = repo.create_user(normalized, hash_password(password))
    return user, create_token(user.id)


def authenticate(email: str, password: str) -> tuple[User, str] | None:
    """Authenticate a user and return it with a token.

    Args:
        email: The raw email address.
        password: The plaintext password.

    Returns:
        The user and token, or None when the credentials are invalid.
    """
    try:
        normalized = normalize_email(email)
    except ValueError:
        return None
    user = get_repo().get_user_by_email(normalized)
    if user is None:
        verify_password(password, dummy_hash())
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user, create_token(user.id)
