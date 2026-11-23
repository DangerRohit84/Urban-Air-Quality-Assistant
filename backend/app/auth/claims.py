"""Bearer-token claim encoding and signature verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class TokenClaims:
    """The verified claims carried by a bearer token."""

    subject: str
    expires_ns: int
    jti: str | None


def b64encode(data: bytes) -> str:
    """Encode bytes as unpadded base64url text.

    Args:
        data: The raw bytes.

    Returns:
        The base64url string without ``=`` padding.
    """
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64decode(value: str) -> bytes:
    """Decode unpadded base64url text.

    Args:
        value: The base64url string.

    Returns:
        The decoded bytes.
    """
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def encode_claims(subject: str, expires_ns: int, jti: str, secret: str) -> str:
    """Sign a payload carrying ``subject``, ``expires_ns`` and ``jti``.

    Args:
        subject: The subject claim.
        expires_ns: The expiry in nanoseconds since the Unix epoch.
        jti: The unique token id used for revocation.
        secret: The HMAC signing secret.

    Returns:
        The encoded ``payload.signature`` token.
    """
    payload = {"sub": subject, "exp": expires_ns, "jti": jti}
    encoded = b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{encoded}.{b64encode(signature)}"


def decode_token(token: str, secret: str) -> TokenClaims | None:
    """Verify a token's signature and expiry and return its claims.

    Tokens minted before ``jti`` existed carry no token id; they still verify
    and their ``TokenClaims.jti`` is None, so they cannot be revoked.

    Args:
        token: The token to verify.
        secret: The HMAC signing secret.

    Returns:
        The verified claims, or None when the token is malformed, tampered
        with or expired.
    """
    if not token or token.count(".") != 1:
        return None
    encoded, signature_text = token.split(".")
    try:
        expected = hmac.new(
            secret.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).digest()
        signature = b64decode(signature_text)
    except (ValueError, UnicodeEncodeError):
        return None
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        payload = json.loads(b64decode(encoded))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    subject = payload.get("sub")
    expires = payload.get("exp")
    jti = payload.get("jti")
    if not isinstance(subject, str) or not isinstance(expires, int):
        return None
    if jti is not None and not isinstance(jti, str):
        return None
    if time.time_ns() > expires:
        return None
    return TokenClaims(subject, expires, jti)
