"""Response schemas for the analytics module (see PRPs/api-contract.md)."""

import datetime as dt

from pydantic import BaseModel

from app.models.finding import Severity


class AnalyticsSummary(BaseModel):
    """Headline numbers for the current user's dashboard."""

    project_count: int
    scan_count: int
    avg_latest_score: float | None
    open_critical_findings: int


class ScorePoint(BaseModel):
    """One completed scan's score on a given day."""

    date: dt.date
    score: int


class ScoreTrendSeries(BaseModel):
    """Score history of a single project."""

    project_id: int
    name: str
    points: list[ScorePoint]


class CommonFinding(BaseModel):
    """A check that fails frequently across the user's projects."""

    check_id: str
    title: str
    severity: Severity
    count: int
