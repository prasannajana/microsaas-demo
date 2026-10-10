"""Analytics endpoints: dashboard summary, score trend, common findings."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.analytics import AnalyticsSummary, CommonFinding, ScoreTrendSeries
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def get_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalyticsSummary:
    """Return headline counters for the current user's dashboard."""
    return analytics_service.get_summary(db, user.id)


@router.get("/score-trend", response_model=list[ScoreTrendSeries])
def get_score_trend(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ScoreTrendSeries]:
    """Return per-project score history over the last `days` days."""
    return analytics_service.get_score_trend(db, user.id, days)


@router.get("/common-findings", response_model=list[CommonFinding])
def get_common_findings(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CommonFinding]:
    """Return the most frequent findings across each project's latest completed scan."""
    return analytics_service.get_common_findings(db, user.id, limit)
