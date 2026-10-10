"""Auth endpoints: email/password, token rotation, profile and Google OAuth."""

import logging
import re
import secrets
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import google
from app.config import settings
from app.dependencies import get_current_user, get_db
from app.exceptions import BadRequestError, UnauthorizedError
from app.models.user import User
from app.rate_limit import AUTH_RATE_LIMIT, REFRESH_RATE_LIMIT, limiter
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UpdateMeRequest,
)
from app.schemas.user import UserOut
from app.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_STATE_MAX_AGE = 600
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
# Client-generated login-CSRF nonce (see google_login): URL-safe base64 alphabet only.
# No "." so it can be packed into the state cookie as ``<state>.<nonce>``.
NONCE_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,128}")


def _cookie_secure() -> bool:
    """Mark the state cookie Secure unless the backend runs on localhost."""
    return urlparse(settings.GOOGLE_REDIRECT_URI).hostname not in _LOCAL_HOSTS


def _frontend_redirect(fragment: dict[str, str]) -> RedirectResponse:
    """Redirect to the frontend OAuth callback page with data in the URL fragment."""
    url = f"{settings.FRONTEND_URL.rstrip('/')}/auth/callback#{urlencode(fragment)}"
    response = RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    response.delete_cookie(OAUTH_STATE_COOKIE, httponly=True, samesite="lax")
    return response


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
@limiter.limit(AUTH_RATE_LIMIT)
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)) -> TokenPair:
    """Create an email/password account and return a token pair (409 if email exists)."""
    return auth_service.register(db, body.email, body.password, body.full_name)


@router.post("/login", response_model=TokenPair)
@limiter.limit(AUTH_RATE_LIMIT)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    """Exchange email/password for a token pair (401 on bad credentials)."""
    return auth_service.login(db, body.email, body.password)


@router.post("/refresh", response_model=TokenPair)
@limiter.limit(REFRESH_RATE_LIMIT)
def refresh(request: Request, body: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    """Rotate a refresh token: revoke it and return a new pair (401 if invalid)."""
    return auth_service.refresh(db, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout(body: RefreshRequest, db: Session = Depends(get_db)) -> Response:
    """Revoke a refresh token. Always 204."""
    auth_service.logout(db, body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)) -> User:
    """Return the current user."""
    return user


@router.put("/me", response_model=UserOut)
def update_me(
    body: UpdateMeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Update the current user's full name."""
    return auth_service.update_profile(db, user, body.full_name)


def _split_state_cookie(value: str | None) -> tuple[str | None, str | None]:
    """Split the ``<state>[.<nonce>]`` cookie; returns (None, None) if malformed."""
    if not value:
        return None, None
    state, sep, nonce = value.partition(".")
    if not sep:
        return state, None
    if not NONCE_PATTERN.fullmatch(nonce):
        return None, None
    return state, nonce


@router.get("/google", status_code=status.HTTP_302_FOUND, response_class=RedirectResponse)
def google_login(
    nonce: str | None = Query(
        default=None,
        description=(
            "Optional client-generated login-CSRF nonce (URL-safe, 16-128 chars). It is bound "
            "to the OAuth state cookie and echoed back as ``nonce`` in the callback fragment "
            "so the SPA can reject tokens from a flow it did not start."
        ),
    ),
) -> RedirectResponse:
    """Redirect to Google's consent screen, storing an anti-CSRF state in a cookie."""
    if not google.is_configured():
        # Browser navigation, not an XHR: send the user back to the SPA with a readable error.
        return _frontend_redirect({"error": "google_not_configured"})
    if nonce is not None and not NONCE_PATTERN.fullmatch(nonce):
        raise BadRequestError("Invalid nonce")
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(
        google.build_authorization_url(state), status_code=status.HTTP_302_FOUND
    )
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        f"{state}.{nonce}" if nonce else state,
        max_age=OAUTH_STATE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
    )
    return response


@router.get("/google/callback", response_class=RedirectResponse)
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Handle Google's redirect: verify state, exchange the code, upsert the user
    and redirect to the frontend with tokens (or ``#error=...``) in the fragment.

    A sync ``def`` on purpose: FastAPI runs it in the threadpool, so the blocking
    Google HTTP calls and SQLAlchemy work never stall the event loop.
    """
    expected, nonce = _split_state_cookie(request.cookies.get(OAUTH_STATE_COOKIE))
    if not expected or not state or not secrets.compare_digest(expected, state):
        logger.warning("Google OAuth callback with invalid state")
        return _frontend_redirect({"error": "invalid_state"})
    extra = {"nonce": nonce} if nonce else {}
    if error:
        return _frontend_redirect({"error": "access_denied", **extra})
    if not code:
        return _frontend_redirect({"error": "oauth_failed", **extra})
    try:
        google_token = google.exchange_code(code)
        info = google.fetch_userinfo(google_token)
    except google.GoogleOAuthError:
        logger.exception("Google OAuth exchange failed")
        return _frontend_redirect({"error": "oauth_failed", **extra})
    if not info.email_verified:
        return _frontend_redirect({"error": "email_not_verified", **extra})
    try:
        user = auth_service.upsert_google_user(db, info)
    except UnauthorizedError:
        db.rollback()
        return _frontend_redirect({"error": "account_disabled", **extra})
    tokens = auth_service.issue_tokens(db, user)
    return _frontend_redirect(
        {"access_token": tokens.access_token, "refresh_token": tokens.refresh_token, **extra}
    )
