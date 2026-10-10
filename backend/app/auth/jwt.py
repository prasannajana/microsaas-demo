"""JWT creation and decoding for access and refresh tokens."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt

from app.config import settings

TokenType = Literal["access", "refresh"]

# Pinned explicitly (not read from settings) so a misconfigured ALGORITHM can never
# enable "none" or an asymmetric/confused algorithm on decode.
JWT_ALGORITHM = "HS256"
_REQUIRED_CLAIMS = ["exp", "iat", "sub", "type"]


def _encode(subject: str, token_type: TokenType, expires_at: datetime) -> str:
    """Encode a signed JWT with standard claims plus a unique ``jti``."""
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "exp": expires_at,
        "iat": datetime.now(UTC),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    """
    Create a short-lived access token.

    Args:
        user_id: ID of the user the token is issued to (stored as ``sub``)

    Returns:
        Encoded JWT with ``type="access"``
    """
    expires = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _encode(str(user_id), "access", expires)


def create_refresh_token(user_id: int) -> tuple[str, datetime]:
    """
    Create a long-lived refresh token.

    Args:
        user_id: ID of the user the token is issued to (stored as ``sub``)

    Returns:
        Tuple of (encoded JWT with ``type="refresh"``, expiry datetime)
    """
    expires = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _encode(str(user_id), "refresh", expires), expires


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any] | None:
    """
    Decode and validate a JWT.

    Args:
        token: Encoded JWT
        expected_type: Required value of the ``type`` claim

    Returns:
        The payload if the signature, expiry and type are valid, otherwise None
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": _REQUIRED_CLAIMS},
        )
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != expected_type or not isinstance(payload.get("sub"), str):
        return None
    return payload


def user_id_from_payload(payload: dict[str, Any]) -> int | None:
    """Return the integer user id from a payload's ``sub`` claim, or None if malformed."""
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
