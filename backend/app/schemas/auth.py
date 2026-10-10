"""Request/response schemas for the auth module (see PRPs/api-contract.md)."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

# bcrypt only uses the first 72 *bytes* of a password; longer input would be silently
# truncated (or rejected by newer bcrypt releases), so enforce the byte limit up front.
PASSWORD_MAX_BYTES = 72
PASSWORD_TOO_LONG = f"Password must be at most {PASSWORD_MAX_BYTES} bytes when UTF-8 encoded"


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _check_password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(PASSWORD_TOO_LONG)
    return value


class RegisterRequest(BaseModel):
    """Body of POST /auth/register."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str | None = Field(default=None, max_length=100)

    _email = field_validator("email")(_normalize_email)
    _password = field_validator("password")(_check_password_bytes)


class LoginRequest(BaseModel):
    """Body of POST /auth/login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    _email = field_validator("email")(_normalize_email)


class RefreshRequest(BaseModel):
    """Body of POST /auth/refresh and POST /auth/logout."""

    refresh_token: str = Field(min_length=1, max_length=512)


class UpdateMeRequest(BaseModel):
    """Body of PUT /auth/me."""

    full_name: str | None = Field(default=None, max_length=100)


class TokenPair(BaseModel):
    """Access + refresh token pair returned by register/login/refresh."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth token type, not a secret
