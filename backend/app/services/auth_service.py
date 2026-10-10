"""Authentication business logic: registration, login, token rotation, OAuth upsert."""

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.google import GoogleUserInfo
from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    user_id_from_payload,
)
from app.auth.passwords import hash_password, verify_password
from app.exceptions import ConflictError, UnauthorizedError
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenPair

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Invalid email or password"
INVALID_REFRESH = "Invalid or expired refresh token"


def hash_refresh_token(token: str) -> str:
    """
    Return the value stored in ``refresh_tokens.token`` for a raw refresh token.

    Only the SHA-256 hex digest (64 chars) is persisted, so a database leak does not
    expose usable refresh tokens. The JWT itself carries ample entropy, so an
    unsalted fast hash is appropriate here (unlike passwords).
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    """Treat naive datetimes as UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def revoke_all_refresh_tokens(db: Session, user_id: int) -> int:
    """
    Revoke every active refresh token of a user (not committed).

    Returns:
        Number of rows revoked
    """
    result = db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
        .execution_options(synchronize_session="fetch")
    )
    return int(getattr(result, "rowcount", 0) or 0)


def delete_expired_refresh_tokens(db: Session, user_id: int) -> None:
    """Delete a user's expired refresh-token rows (not committed)."""
    db.execute(
        delete(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.expires_at <= datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )


def get_user_by_email(db: Session, email: str) -> User | None:
    """Return the user with the given (normalized) email, or None."""
    return db.scalars(select(User).where(User.email == email.strip().lower())).first()


def issue_tokens(db: Session, user: User) -> TokenPair:
    """
    Create an access/refresh pair and persist the refresh token.

    Args:
        db: Database session (committed by this function)
        user: User to issue tokens for

    Returns:
        TokenPair with fresh tokens
    """
    refresh, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token=hash_refresh_token(refresh), expires_at=expires_at))
    db.commit()
    return TokenPair(access_token=create_access_token(user.id), refresh_token=refresh)


def register(db: Session, email: str, password: str, full_name: str | None) -> TokenPair:
    """
    Create a password-based account and return tokens.

    Raises:
        ConflictError: If the email is already registered
    """
    email = email.strip().lower()
    if get_user_by_email(db, email) is not None:
        raise ConflictError("Email already registered")
    user = User(email=email, hashed_password=hash_password(password), full_name=full_name)
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Email already registered") from exc
    logger.info("Registered user id=%s", user.id)
    return issue_tokens(db, user)


def authenticate(db: Session, email: str, password: str) -> User:
    """
    Validate email/password credentials.

    Raises:
        UnauthorizedError: On unknown email, wrong password, OAuth-only or inactive account
    """
    user = get_user_by_email(db, email)
    hashed = user.hashed_password if user is not None else None
    if not verify_password(password, hashed) or user is None or not user.is_active:
        raise UnauthorizedError(INVALID_CREDENTIALS)
    return user


def login(db: Session, email: str, password: str) -> TokenPair:
    """Authenticate, prune the user's expired refresh tokens and issue a token pair."""
    user = authenticate(db, email, password)
    delete_expired_refresh_tokens(db, user.id)
    return issue_tokens(db, user)


def _get_valid_refresh_row(db: Session, token: str) -> RefreshToken:
    """
    Return the active DB row for a refresh token (row-locked) or raise UnauthorizedError.

    The row is selected ``FOR UPDATE`` so two concurrent refreshes of the same token
    serialize: the second one sees ``revoked=True`` once the first commits.

    Presenting a token that is known but already revoked is treated as token theft
    (refresh-token reuse): every refresh token of that user is revoked and committed
    before the 401 is raised, forcing all sessions to log in again.
    """
    payload = decode_token(token, "refresh")
    user_id = user_id_from_payload(payload) if payload else None
    if user_id is None:
        raise UnauthorizedError(INVALID_REFRESH)
    row = db.scalars(
        select(RefreshToken)
        .where(RefreshToken.token == hash_refresh_token(token))
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if row is None or row.user_id != user_id:
        raise UnauthorizedError(INVALID_REFRESH)
    if row.revoked:
        revoked = revoke_all_refresh_tokens(db, row.user_id)
        db.commit()
        logger.warning(
            "Refresh token reuse detected for user id=%s; revoked %s token(s)",
            row.user_id,
            revoked,
        )
        raise UnauthorizedError(INVALID_REFRESH)
    if _as_utc(row.expires_at) <= datetime.now(UTC):
        raise UnauthorizedError(INVALID_REFRESH)
    return row


def refresh(db: Session, token: str) -> TokenPair:
    """
    Rotate a refresh token: revoke the presented one and issue a new pair.

    Raises:
        UnauthorizedError: If the token is unknown, revoked (which also revokes all of
            the user's tokens), expired or its user is inactive
    """
    row = _get_valid_refresh_row(db, token)
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        db.rollback()  # release the row lock
        raise UnauthorizedError(INVALID_REFRESH)
    row.revoked = True
    return issue_tokens(db, user)


def logout(db: Session, token: str) -> None:
    """Revoke a refresh token. Unknown/invalid tokens are ignored (idempotent)."""
    row = db.scalars(
        select(RefreshToken).where(RefreshToken.token == hash_refresh_token(token))
    ).first()
    if row is not None and not row.revoked:
        row.revoked = True
        db.commit()


def update_profile(db: Session, user: User, full_name: str | None) -> User:
    """Update the current user's full name."""
    user.full_name = full_name.strip() if full_name and full_name.strip() else None
    db.commit()
    db.refresh(user)
    return user


def upsert_google_user(db: Session, info: GoogleUserInfo) -> User:
    """
    Find or create the local user for a Google identity.

    Looks up by ``google_id`` first, then by email (linking an existing
    password account). Sets ``oauth_provider="google"``, avatar and verified flag.

    Account pre-hijack protection: if the email matches an existing account that was
    never verified, whoever registered it cannot be assumed to own the mailbox (an
    attacker may have pre-registered the victim's address). Before linking, that
    account's password is removed and all of its refresh tokens are deleted, so only
    the verified Google identity can sign in afterwards.

    Raises:
        UnauthorizedError: If the email is unverified or the account is inactive
    """
    if not info.email_verified:
        raise UnauthorizedError("Google email is not verified")
    user = db.scalars(select(User).where(User.google_id == info.sub)).first()
    linked_by_email = False
    if user is None:
        user = get_user_by_email(db, info.email)
        linked_by_email = user is not None
    if user is None:
        user = User(email=info.email, full_name=info.name, is_active=True)
        db.add(user)
        logger.info("Creating user from Google sign-in")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled")
    if linked_by_email and not user.is_verified:
        logger.info("Linking Google to unverified user id=%s; dropping password/sessions", user.id)
        user.hashed_password = None
        # Delete (rather than flag) the squatter's sessions: their tokens become
        # unknown, so replaying one can't trigger reuse detection and log the
        # rightful owner out of the session issued below.
        db.execute(
            delete(RefreshToken)
            .where(RefreshToken.user_id == user.id)
            .execution_options(synchronize_session="fetch")
        )
    user.google_id = info.sub
    user.oauth_provider = "google"
    user.is_verified = True
    if info.picture:
        user.avatar_url = info.picture
    if not user.full_name and info.name:
        user.full_name = info.name
    db.flush()
    return user
