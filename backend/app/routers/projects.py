"""Project CRUD and scan-start endpoints (all scoped to the current user)."""

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.common import Page
from app.schemas.project import ProjectCreate, ProjectDetail, ProjectOut, ProjectUpdate
from app.schemas.scan import ScanDetail, ScanSummary
from app.services import project_service, scan_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=Page[ProjectOut])
def list_projects(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Page[ProjectOut]:
    """List the current user's projects, newest first."""
    items, total = project_service.list_projects(db, user.id, page, size)
    return Page[ProjectOut](
        items=[ProjectOut.model_validate(p) for p in items], total=total, page=page, size=size
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    """Register a GitHub repository (400 invalid URL, 409 duplicate or project limit)."""
    project = project_service.create_project(db, user.id, payload)
    return ProjectOut.model_validate(project)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectDetail:
    """Return a project with its latest scan and that scan's findings."""
    project = project_service.get_project(db, project_id, user.id)
    latest = project_service.get_latest_scan(db, project.id)
    out = ProjectOut.model_validate(project)
    return ProjectDetail(
        **out.model_dump(),
        latest_scan=ScanDetail.model_validate(latest) if latest is not None else None,
    )


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    """Update a project's name and/or default branch."""
    project = project_service.get_project(db, project_id, user.id)
    return ProjectOut.model_validate(project_service.update_project(db, project, payload))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Delete a project and all its scans."""
    project = project_service.get_project(db, project_id, user.id)
    project_service.delete_project(db, project)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{project_id}/scans", response_model=ScanSummary, status_code=status.HTTP_202_ACCEPTED
)
def start_scan(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScanSummary:
    """
    Queue a scan; it runs on the bounded scan executor after the response is sent.

    409 if a scan is active; 429 if over the hourly quota or the scanner is busy.
    """
    project = project_service.get_project(db, project_id, user.id)
    scan = scan_service.start_scan(db, project)
    # The background task only hands the id to the dedicated executor (non-blocking).
    background_tasks.add_task(scan_service.submit_scan, scan.id)
    return ScanSummary.model_validate(scan)


@router.get("/{project_id}/scans", response_model=list[ScanSummary])
def list_scans(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ScanSummary]:
    """Return the project's newest 50 scans, newest first (no findings)."""
    project = project_service.get_project(db, project_id, user.id)
    return [ScanSummary.model_validate(s) for s in scan_service.list_scans(db, project.id)]
