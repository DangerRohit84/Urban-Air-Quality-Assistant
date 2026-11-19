"""HMAC-SHA256 signed bearer tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
import warnings

from backend.app.config import settings

_ephemeral_secret: str | None = None
_last_exp_ns = 0
_token_lock = threading.Lock()


def _b64encode(data: bytes) -> str:
    """Encode bytes as unpadded base64url text.

    Args:
        data: The raw bytes.

    Returns:
        The base64url string without ``=`` padding.
    """
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    """Decode unpadded base64url text.

    Args:
        value: The base64url string.

    Returns:
        The decoded bytes.
    """
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


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
    payload = {"sub": user_id, "exp": expires}
    encoded = _b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signature = hmac.new(
        get_secret().encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{encoded}.{_b64encode(signature)}"


def verify_token(token: str) -> str | None:
    """Verify a bearer token and return its subject.

    Args:
        token: The token to verify.

    Returns:
        The subject when the token is valid and unexpired, otherwise None.
    """
    if not token or token.count(".") != 1:
        return None
    encoded, signature_text = token.split(".")
    try:
        expected = hmac.new(
            get_secret().encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).digest()
        signature = _b64decode(signature_text)
    except (ValueError, UnicodeEncodeError):
        return None
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        payload = json.loads(_b64decode(encoded))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    subject = payload.get("sub")
    expires = payload.get("exp")
    if not isinstance(subject, str) or not isinstance(expires, int):
        return None
    if time.time_ns() > expires:
        return None
    return subject
