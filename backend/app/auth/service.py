"""Registration and authentication use cases."""

from __future__ import annotations

from backend.app.auth.passwords import (
    dummy_hash,
    hash_password,
    needs_rehash,
    normalize_email,
    validate_password,
    verify_password,
)
from backend.app.auth.tokens import create_token
from backend.app.models import User
from backend.app.storage.store import get_repo


class DuplicateEmailError(ValueError):
    """Raised when the normalized email already has an account."""


def register_user(email: str, password: str) -> tuple[User, str]:
    """Register a new user and return it with a bearer token.

    Args:
        email: The raw email address.
        password: The plaintext password.

    Returns:
        The created user and its token.

    Raises:
        DuplicateEmailError: When the email is already registered.
        ValueError: On a malformed email or a weak password.
    """
    normalized = normalize_email(email)
    validate_password(password)
    repo = get_repo()
    if repo.get_user_by_email(normalized) is not None:
        raise DuplicateEmailError("email already registered")
    try:
        user = repo.create_user(normalized, hash_password(password))
    except ValueError as exc:
        # A concurrent signup can win the unique constraint between the
        # pre-check above and the insert; surface the same domain error.
        raise DuplicateEmailError("email already registered") from exc
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
    repo = get_repo()
    user = repo.get_user_by_email(normalized)
    if user is None:
        verify_password(password, dummy_hash())
        return None
    if not verify_password(password, user.password_hash):
        return None
    if needs_rehash(user.password_hash):
        upgraded = hash_password(password)
        repo.update_user_password_hash(user.id, upgraded)
        user.password_hash = upgraded
    return user, create_token(user.id)
