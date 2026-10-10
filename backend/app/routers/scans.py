"""Scan detail endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.scan import ScanDetail
from app.services import scan_service

router = APIRouter(prefix="/scans", tags=["scans"])


@router.get("/{scan_id}", response_model=ScanDetail)
def get_scan(
    scan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScanDetail:
    """Return a scan's status, score and findings (404 if not owned by the user)."""
    return ScanDetail.model_validate(scan_service.get_scan_for_user(db, scan_id, user.id))
