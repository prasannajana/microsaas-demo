"""Project request/response schemas.

`repo_url` and `default_branch` are intentionally *not* validated here: the service
validates and normalizes them so an invalid URL yields HTTP 400 (not 422).
Use `app.scanner.urls.normalize_github_url` for the normalization rules.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.scan import ScanDetail


def _strip_name(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("Name must not be empty")
    return stripped


class ProjectCreate(BaseModel):
    """Payload to register a GitHub repository as a project."""

    name: str = Field(min_length=1, max_length=100)
    repo_url: str
    default_branch: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _strip_name(value)


class ProjectUpdate(BaseModel):
    """Partial update of a project's name and/or default branch."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    default_branch: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _strip_name(value)


class ProjectOut(BaseModel):
    """Project as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    repo_url: str
    default_branch: str | None
    primary_language: str | None
    latest_score: int | None
    last_scanned_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class ProjectDetail(ProjectOut):
    """Project plus its latest scan (with findings)."""

    latest_scan: ScanDetail | None = None
