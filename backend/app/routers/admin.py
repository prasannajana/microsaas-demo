"""Admin endpoints (all require an admin user)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_admin, get_db
from app.models.scan import ScanStatus
from app.models.user import User
from app.schemas.admin import AdminScan, AdminStats, AdminUserUpdate
from app.schemas.common import Page
from app.schemas.user import UserOut
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=Page[UserOut])
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=255),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> Page[UserOut]:
    """List / search users, newest first."""
    return admin_service.list_users(db, page, size, q)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> User:
    """Update a user's is_active / is_admin flags (not allowed on yourself)."""
    return admin_service.update_user(db, admin, user_id, data)


@router.get("/stats", response_model=AdminStats)
def get_stats(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> AdminStats:
    """Return system-wide counters."""
    return admin_service.get_stats(db)


@router.get("/scans", response_model=Page[AdminScan])
def list_scans(
    status: ScanStatus | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> Page[AdminScan]:
    """List recent scans across all users, newest first."""
    return admin_service.list_scans(db, page, size, status)
