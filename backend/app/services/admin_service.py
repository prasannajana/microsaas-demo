"""Admin operations across all users: user management, system stats, scan listing."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.exceptions import BadRequestError, NotFoundError
from app.models.project import Project
from app.models.scan import Scan, ScanStatus
from app.models.user import User
from app.schemas.admin import AdminScan, AdminStats, AdminUserUpdate
from app.schemas.common import Page
from app.schemas.user import UserOut

logger = logging.getLogger(__name__)


def list_users(db: Session, page: int, size: int, q: str | None = None) -> Page[UserOut]:
    """
    List users newest first, optionally filtered by email / full name.

    Args:
        db: Database session
        page: 1-based page number
        size: Page size
        q: Case-insensitive substring matched against email and full_name

    Returns:
        Page of UserOut.
    """
    stmt = select(User)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.email.ilike(pattern), User.full_name.ilike(pattern)))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    users = db.scalars(
        stmt.order_by(User.created_at.desc(), User.id.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in users], total=total, page=page, size=size
    )


def update_user(db: Session, admin: User, user_id: int, data: AdminUserUpdate) -> User:
    """
    Update a user's is_active / is_admin flags.

    Args:
        db: Database session
        admin: The admin performing the change
        user_id: Target user id
        data: Fields to change (unset fields are left as-is)

    Returns:
        The updated User.

    Raises:
        BadRequestError: If the admin targets their own account.
        NotFoundError: If the user does not exist.
    """
    if user_id == admin.id:
        raise BadRequestError("You cannot change your own account")
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")

    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    logger.info("Admin %s updated user %s: %s", admin.id, user.id, changes)
    return user


def get_stats(db: Session) -> AdminStats:
    """
    Compute system-wide counters.

    Args:
        db: Database session

    Returns:
        AdminStats; failure_rate = failed / (completed + failed), 0.0 when none finished.
    """
    since = datetime.now(UTC) - timedelta(hours=24)
    user_count = db.scalar(select(func.count(User.id))) or 0
    project_count = db.scalar(select(func.count(Project.id))) or 0
    scan_count, last_24h, completed, failed = db.execute(
        select(
            func.count(Scan.id),
            func.count(Scan.id).filter(Scan.created_at >= since),
            func.count(Scan.id).filter(Scan.status == ScanStatus.completed),
            func.count(Scan.id).filter(Scan.status == ScanStatus.failed),
        )
    ).one()
    finished = (completed or 0) + (failed or 0)
    return AdminStats(
        user_count=user_count,
        project_count=project_count,
        scan_count=scan_count or 0,
        scans_last_24h=last_24h or 0,
        failure_rate=(failed / finished) if finished else 0.0,
    )


def list_scans(
    db: Session, page: int, size: int, status: ScanStatus | None = None
) -> Page[AdminScan]:
    """
    List scans across all users, newest first, with project name and owner email.

    Args:
        db: Database session
        page: 1-based page number
        size: Page size
        status: Optional status filter

    Returns:
        Page of AdminScan.
    """
    filters = [Scan.status == status] if status is not None else []
    total = db.scalar(select(func.count(Scan.id)).where(*filters)) or 0
    rows = db.execute(
        select(
            Scan.id,
            Scan.project_id,
            Scan.status,
            Scan.score,
            Scan.commit_sha,
            Scan.error_message,
            Scan.started_at,
            Scan.completed_at,
            Scan.created_at,
            Project.name.label("project_name"),
            User.email.label("user_email"),
        )
        .join(Project, Project.id == Scan.project_id)
        .join(User, User.id == Project.user_id)
        .where(*filters)
        .order_by(Scan.created_at.desc(), Scan.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return Page[AdminScan](
        items=[AdminScan.model_validate(row._mapping) for row in rows],
        total=total,
        page=page,
        size=size,
    )


def make_admin(db: Session, email: str) -> User | None:
    """
    Grant admin rights to the user with the given email (case-insensitive).

    Args:
        db: Database session
        email: Email of the user to promote

    Returns:
        The promoted User, or None if no such user exists.
    """
    user = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if user is None:
        return None
    user.is_admin = True
    db.commit()
    db.refresh(user)
    return user
