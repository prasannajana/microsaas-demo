"""Project CRUD, always scoped to the owning user."""

import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.project import Project
from app.models.scan import Scan
from app.scanner.urls import InvalidRepoUrlError, is_valid_branch, normalize_github_url
from app.schemas.project import ProjectCreate, ProjectUpdate

logger = logging.getLogger(__name__)

INVALID_URL_MESSAGE = (
    "Invalid repository URL. Use a public GitHub URL like https://github.com/owner/repo"
)
INVALID_BRANCH_MESSAGE = "Invalid branch name"
MAX_URL_LENGTH = 500


def validate_repo_url(raw: str) -> str:
    """
    Normalize and validate a GitHub repository URL.

    Raises:
        BadRequestError: If the URL is not a valid https://github.com/<owner>/<repo> URL.
    """
    if len(raw) > MAX_URL_LENGTH:
        raise BadRequestError(INVALID_URL_MESSAGE)
    try:
        return normalize_github_url(raw)
    except InvalidRepoUrlError as exc:
        raise BadRequestError(INVALID_URL_MESSAGE) from exc


def validate_branch(raw: str | None) -> str | None:
    """
    Normalize an optional branch name (blank → None).

    Raises:
        BadRequestError: If the branch name contains unsafe characters.
    """
    if raw is None:
        return None
    branch = raw.strip()
    if not branch:
        return None
    if not is_valid_branch(branch):
        raise BadRequestError(INVALID_BRANCH_MESSAGE)
    return branch


def list_projects(db: Session, user_id: int, page: int, size: int) -> tuple[list[Project], int]:
    """
    Return one page of the user's projects (newest first) and the total count.

    Args:
        db: Database session
        user_id: Owner id
        page: 1-based page number
        size: Page size
    """
    total = db.scalar(select(func.count(Project.id)).where(Project.user_id == user_id)) or 0
    items = db.scalars(
        select(Project)
        .where(Project.user_id == user_id)
        .order_by(Project.created_at.desc(), Project.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return list(items), total


def create_project(db: Session, user_id: int, data: ProjectCreate) -> Project:
    """
    Create a project for the user.

    Raises:
        BadRequestError: Invalid repo URL or branch.
        ConflictError: The user already has a project for this repository, or has
            reached MAX_PROJECTS_PER_USER projects.
    """
    repo_url = validate_repo_url(data.repo_url)
    branch = validate_branch(data.default_branch)
    owned = db.scalar(select(func.count(Project.id)).where(Project.user_id == user_id)) or 0
    if owned >= settings.MAX_PROJECTS_PER_USER:
        raise ConflictError(
            f"Project limit reached ({settings.MAX_PROJECTS_PER_USER}). "
            "Delete a project before adding another one."
        )
    project = Project(user_id=user_id, name=data.name, repo_url=repo_url, default_branch=branch)
    db.add(project)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("You already have a project for this repository") from exc
    db.refresh(project)
    logger.info("User %s created project %s (%s)", user_id, project.id, repo_url)
    return project


def get_project(db: Session, project_id: int, user_id: int) -> Project:
    """
    Return the user's project.

    Raises:
        NotFoundError: If it does not exist or belongs to another user.
    """
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user_id))
    if project is None:
        raise NotFoundError("Project not found")
    return project


def get_latest_scan(db: Session, project_id: int) -> Scan | None:
    """Return the project's most recent scan with findings eagerly loaded, or None."""
    return db.scalar(
        select(Scan)
        .where(Scan.project_id == project_id)
        .options(selectinload(Scan.findings))
        .order_by(Scan.created_at.desc(), Scan.id.desc())
        .limit(1)
    )


def update_project(db: Session, project: Project, data: ProjectUpdate) -> Project:
    """
    Apply a partial update (name / default_branch) to a project.

    Sending `default_branch: null` (or "") resets it to the remote default branch.
    """
    fields = data.model_fields_set
    if "name" in fields and data.name is not None:
        project.name = data.name
    if "default_branch" in fields:
        project.default_branch = validate_branch(data.default_branch)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: Project) -> None:
    """Delete a project and (via cascade) its scans and findings."""
    db.delete(project)
    db.commit()
    logger.info("Deleted project %s", project.id)
