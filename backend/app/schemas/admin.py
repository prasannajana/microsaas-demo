"""Request/response schemas for the admin module (see PRPs/api-contract.md)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.scan import ScanStatus


class AdminUserUpdate(BaseModel):
    """Partial update of a user's flags by an admin."""

    is_active: bool | None = None
    is_admin: bool | None = None


class AdminStats(BaseModel):
    """System-wide counters for the admin dashboard."""

    user_count: int
    project_count: int
    scan_count: int
    scans_last_24h: int
    failure_rate: float


class AdminScan(BaseModel):
    """A scan across all users (`ScanSummary` fields + project name + owner email)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    status: ScanStatus
    score: int | None
    commit_sha: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    project_name: str
    user_email: str
