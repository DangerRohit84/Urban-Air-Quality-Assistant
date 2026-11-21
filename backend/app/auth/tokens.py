"""HMAC-SHA256 signed bearer tokens."""

from __future__ import annotations

import secrets
import threading
import time
import uuid
import warnings

from backend.app.auth.claims import TokenClaims, decode_token, encode_claims
from backend.app.config import settings

_ephemeral_secret: str | None = None
_last_exp_ns = 0
_token_lock = threading.Lock()


def get_secret() -> str:
    """Return the token signing secret.

    Returns:
        ``AUTH_SECRET`` when set, otherwise a stable per-boot random secret.
    """
    env_secret = settings.auth_secret
    if env_secret:
        return env_secret
    global _ephemeral_secret
    if _ephemeral_secret is None:
        _ephemeral_secret = secrets.token_urlsafe(32)
        warnings.warn(
            "AUTH_SECRET is not set; using an ephemeral token secret",
            RuntimeWarning,
            stacklevel=2,
        )
    return _ephemeral_secret


def create_token(user_id: str, ttl_seconds: int = 86_400) -> str:
    """Sign a bearer token for ``user_id``.

    Args:
        user_id: The subject claim.
        ttl_seconds: Token lifetime in seconds.

    Returns:
        The encoded ``payload.signature`` token.
    """
    global _last_exp_ns
    with _token_lock:
        expires = time.time_ns() + ttl_seconds * 1_000_000_000
        if ttl_seconds >= 0:
            expires = max(expires, _last_exp_ns + 1)
            _last_exp_ns = expires
    return encode_claims(user_id, expires, uuid.uuid4().hex, get_secret())


def verify_claims(token: str) -> TokenClaims | None:
    """Verify a bearer token and return its claims.

    Args:
        token: The token to verify.

    Returns:
        The verified claims, or None when the token is invalid or expired.
    """
    return decode_token(token, get_secret())


def verify_token(token: str) -> str | None:
    """Verify a bearer token and return its subject.

    Args:
        token: The token to verify.

    Returns:
        The subject when the token is valid and unexpired, otherwise None.
    """
    claims = verify_claims(token)
    return claims.subject if claims is not None else None
