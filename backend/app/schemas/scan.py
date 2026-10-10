"""Scan and finding response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.finding import FindingCategory, Severity
from app.models.scan import ScanStatus


class FindingOut(BaseModel):
    """A single finding (missing item) in a scan report."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    check_id: str
    category: FindingCategory
    severity: Severity
    title: str
    recommendation: str
    file_path: str | None


class ScanSummary(BaseModel):
    """Scan status and score without findings."""

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


class ScanDetail(ScanSummary):
    """Scan with its findings."""

    findings: list[FindingOut]
