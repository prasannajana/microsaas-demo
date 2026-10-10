"""User response schema shared by the auth and admin modules."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    """Public representation of a user (matches `User` in PRPs/api-contract.md)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None
    is_active: bool
    is_verified: bool
    is_admin: bool
    oauth_provider: str | None
    avatar_url: str | None
    created_at: datetime
