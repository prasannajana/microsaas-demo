"""Google OAuth 2.0 (authorization code flow) helpers.

Tests monkeypatch ``exchange_code`` and ``fetch_userinfo``; callers must access
them via the module (``google.exchange_code``) rather than importing the names.

The helpers are synchronous (``httpx.Client``): the callback endpoint is a plain
``def`` that FastAPI runs in its threadpool, so neither these blocking HTTP calls nor
the SQLAlchemy work that follows ever runs on the event loop.
"""

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - public endpoint URL
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
HTTP_TIMEOUT_SECONDS = 10.0


class GoogleOAuthError(Exception):
    """Raised when the Google token exchange or userinfo request fails."""


@dataclass(frozen=True)
class GoogleUserInfo:
    """The subset of Google's OpenID userinfo we use."""

    sub: str
    email: str
    email_verified: bool
    name: str | None = None
    picture: str | None = None


def is_configured() -> bool:
    """Return True if Google OAuth credentials are configured."""
    return bool(settings.GOOGLE_CLIENT_ID)


def build_authorization_url(state: str) -> str:
    """
    Build the Google consent-screen URL.

    Args:
        state: Random anti-CSRF value echoed back on the callback

    Returns:
        Absolute URL to redirect the browser to
    """
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> str:
    """
    Exchange an authorization code for a Google access token.

    Args:
        code: Authorization code from the callback query string

    Returns:
        Google access token

    Raises:
        GoogleOAuthError: On network errors or a non-success response
    """
    data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
    }
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = client.post(GOOGLE_TOKEN_URL, data=data)
    except httpx.HTTPError as exc:
        raise GoogleOAuthError("Token exchange request failed") from exc
    if response.status_code != 200:
        logger.warning("Google token exchange failed with status %s", response.status_code)
        raise GoogleOAuthError("Token exchange rejected")
    token = response.json().get("access_token")
    if not isinstance(token, str) or not token:
        raise GoogleOAuthError("Token exchange returned no access token")
    return token


def fetch_userinfo(access_token: str) -> GoogleUserInfo:
    """
    Fetch the signed-in user's profile from Google.

    Args:
        access_token: Google access token from ``exchange_code``

    Returns:
        Parsed GoogleUserInfo

    Raises:
        GoogleOAuthError: On network errors, non-success response or missing fields
    """
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = client.get(
                GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
    except httpx.HTTPError as exc:
        raise GoogleOAuthError("Userinfo request failed") from exc
    if response.status_code != 200:
        logger.warning("Google userinfo failed with status %s", response.status_code)
        raise GoogleOAuthError("Userinfo rejected")
    data: dict[str, Any] = response.json()
    sub, email = data.get("sub"), data.get("email")
    if not isinstance(sub, str) or not isinstance(email, str):
        raise GoogleOAuthError("Userinfo missing sub/email")
    verified = data.get("email_verified")
    return GoogleUserInfo(
        sub=sub,
        email=email.strip().lower(),
        email_verified=verified is True or verified == "true",
        name=data.get("name") if isinstance(data.get("name"), str) else None,
        picture=data.get("picture") if isinstance(data.get("picture"), str) else None,
    )
