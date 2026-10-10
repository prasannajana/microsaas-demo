"""Shared FastAPI dependencies: DB session, current user and admin guards."""

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_token, user_id_from_payload
from app.database import get_db
from app.exceptions import ForbiddenError, UnauthorizedError
from app.models.user import User

__all__ = ["get_db", "get_current_user", "get_current_admin", "oauth2_scheme"]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve the authenticated user from the Bearer access token.

    Raises:
        UnauthorizedError: If the token is missing/invalid/not an access token,
            or the user does not exist or is inactive
    """
    if not token:
        raise UnauthorizedError("Not authenticated")
    payload = decode_token(token, "access")
    user_id = user_id_from_payload(payload) if payload else None
    if user_id is None:
        raise UnauthorizedError("Invalid or expired token")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired token")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """
    Require the current user to be an admin.

    Raises:
        ForbiddenError: If the user is not an admin
    """
    if not user.is_admin:
        raise ForbiddenError("Admin privileges required")
    return user
