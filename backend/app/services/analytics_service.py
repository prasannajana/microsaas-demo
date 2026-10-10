"""Aggregate analytics over a single user's projects, scans and findings.

Every query here is scoped to one user and expressed as aggregate SQL (no N+1).
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import Subquery, case, func, select
from sqlalchemy.orm import Session

from app.models.finding import Finding, Severity
from app.models.project import Project
from app.models.scan import Scan, ScanStatus
from app.schemas.analytics import (
    AnalyticsSummary,
    CommonFinding,
    ScorePoint,
    ScoreTrendSeries,
)

logger = logging.getLogger(__name__)

SEVERITY_RANK: dict[Severity, int] = {
    Severity.critical: 0,
    Severity.high: 1,
    Severity.medium: 2,
    Severity.low: 3,
}


def latest_completed_scans_subquery(user_id: int) -> Subquery:
    """
    Build a subquery yielding the latest completed scan of each of a user's projects.

    Uses ``row_number()`` partitioned by project, ordered by ``completed_at`` desc
    (ties broken by scan id), keeping only row 1.

    Args:
        user_id: Owner whose projects are considered.

    Returns:
        Subquery with columns ``scan_id`` and ``project_id`` (one row per project
        that has at least one completed scan).
    """
    ranked = (
        select(
            Scan.id.label("scan_id"),
            Scan.project_id.label("project_id"),
            func.row_number()
            .over(
                partition_by=Scan.project_id,
                order_by=(Scan.completed_at.desc().nulls_last(), Scan.id.desc()),
            )
            .label("rn"),
        )
        .join(Project, Project.id == Scan.project_id)
        .where(Project.user_id == user_id, Scan.status == ScanStatus.completed)
        .subquery("ranked_scans")
    )
    return (
        select(ranked.c.scan_id, ranked.c.project_id)
        .where(ranked.c.rn == 1)
        .subquery("latest_scans")
    )


def get_summary(db: Session, user_id: int) -> AnalyticsSummary:
    """
    Compute the dashboard headline numbers for a user.

    Args:
        db: Database session
        user_id: Current user's id

    Returns:
        AnalyticsSummary with project/scan counts, average latest score (1 decimal,
        None when no project has a score) and critical findings in latest scans.
    """
    project_count, avg_score = db.execute(
        select(func.count(Project.id), func.avg(Project.latest_score)).where(
            Project.user_id == user_id
        )
    ).one()

    scan_count = db.scalar(
        select(func.count(Scan.id))
        .join(Project, Project.id == Scan.project_id)
        .where(Project.user_id == user_id)
    )

    latest = latest_completed_scans_subquery(user_id)
    open_critical = db.scalar(
        select(func.count(Finding.id))
        .join(latest, latest.c.scan_id == Finding.scan_id)
        .where(Finding.severity == Severity.critical)
    )

    return AnalyticsSummary(
        project_count=project_count or 0,
        scan_count=scan_count or 0,
        avg_latest_score=round(float(avg_score), 1) if avg_score is not None else None,
        open_critical_findings=open_critical or 0,
    )


def get_score_trend(db: Session, user_id: int, days: int) -> list[ScoreTrendSeries]:
    """
    Return per-project score history over the last ``days`` days.

    Only completed scans with a score and ``completed_at`` inside the window count;
    projects without any such scan are omitted.

    Args:
        db: Database session
        user_id: Current user's id
        days: Window size in days (1..365)

    Returns:
        List of series ordered by project name, each with points ascending by time.
    """
    since = datetime.now(UTC) - timedelta(days=days)
    rows = db.execute(
        select(Project.id, Project.name, Scan.completed_at, Scan.score)
        .join(Scan, Scan.project_id == Project.id)
        .where(
            Project.user_id == user_id,
            Scan.status == ScanStatus.completed,
            Scan.score.is_not(None),
            Scan.completed_at.is_not(None),
            Scan.completed_at >= since,
        )
        .order_by(Project.name, Project.id, Scan.completed_at, Scan.id)
    ).all()

    series: dict[int, ScoreTrendSeries] = {}
    for project_id, name, completed_at, score in rows:
        entry = series.get(project_id)
        if entry is None:
            entry = ScoreTrendSeries(project_id=project_id, name=name, points=[])
            series[project_id] = entry
        entry.points.append(ScorePoint(date=completed_at.astimezone(UTC).date(), score=score))
    return list(series.values())


def get_common_findings(db: Session, user_id: int, limit: int) -> list[CommonFinding]:
    """
    Return the most frequent checks across each project's latest completed scan.

    Args:
        db: Database session
        user_id: Current user's id
        limit: Maximum number of entries (1..20)

    Returns:
        CommonFinding list ordered by count desc, then severity (critical first),
        then check_id.
    """
    latest = latest_completed_scans_subquery(user_id)
    severity_rank = case(
        {sev: rank for sev, rank in SEVERITY_RANK.items()},
        value=Finding.severity,
    )
    min_rank = func.min(severity_rank).label("severity_rank")
    count = func.count(Finding.id).label("count")
    rows = db.execute(
        select(Finding.check_id, func.max(Finding.title), min_rank, count)
        .join(latest, latest.c.scan_id == Finding.scan_id)
        .group_by(Finding.check_id)
        .order_by(count.desc(), min_rank.asc(), Finding.check_id.asc())
        .limit(limit)
    ).all()

    rank_to_severity = {rank: sev for sev, rank in SEVERITY_RANK.items()}
    return [
        CommonFinding(
            check_id=check_id,
            title=title,
            severity=rank_to_severity[rank],
            count=n,
        )
        for check_id, title, rank, n in rows
    ]
