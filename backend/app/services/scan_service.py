"""Scan orchestration: create queued scans and run them on a dedicated bounded executor.

Deployment assumption: a SINGLE backend process (uvicorn --workers 1). The executor, the
startup `fail_interrupted_scans` reset and the startup workdir purge are all process-local;
running several workers would let one worker's startup fail/delete another's live scans.
"""

import logging
import shutil
import tempfile
import threading
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import SessionLocal
from app.exceptions import ConflictError, NotFoundError, RateLimitError
from app.models.finding import Finding
from app.models.project import Project
from app.models.scan import Scan, ScanStatus
from app.models.scan_request import ScanRequest
from app.scanner import cloner, context, language, registry, scoring

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (ScanStatus.queued, ScanStatus.running)
INTERNAL_ERROR_MESSAGE = "Scan failed due to an internal error"
INTERRUPTED_MESSAGE = "Scan interrupted, please retry"
BUSY_MESSAGE = "The scanner is busy, please try again in a few minutes"
SHUTTING_DOWN_MESSAGE = "The server is restarting, please retry the scan"
WORKDIR_PREFIX = "scan-"
MAX_LISTED_SCANS = 50
MAX_TITLE_LENGTH = 200
MAX_FILE_PATH_LENGTH = 500
ELLIPSIS = "\u2026"

_executor: Executor | None = None
_executor_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(UTC)


def start_scan(db: Session, project: Project) -> Scan:
    """
    Create a queued scan for a project.

    Args:
        db: Database session
        project: Project to scan (must belong to the current user)

    Returns:
        Created Scan object with status "queued"

    Raises:
        ConflictError: A scan for this project is already queued or running.
        RateLimitError: SCAN_MAX_QUEUED scans are already queued/running across all users,
            or the owner started SCANS_PER_HOUR_PER_USER scans in the last hour.
    """
    # Lock the project row so two concurrent requests cannot both pass the active check.
    db.execute(select(Project.id).where(Project.id == project.id).with_for_update())

    active = db.scalar(
        select(func.count(Scan.id)).where(
            Scan.project_id == project.id, Scan.status.in_(ACTIVE_STATUSES)
        )
    )
    if active:
        db.rollback()
        raise ConflictError("A scan is already in progress for this project")

    in_flight = db.scalar(select(func.count(Scan.id)).where(Scan.status.in_(ACTIVE_STATUSES)))
    if (in_flight or 0) >= settings.SCAN_MAX_QUEUED:
        db.rollback()
        raise RateLimitError(BUSY_MESSAGE)

    # Counted from scan_requests (not scans) so deleting projects cannot reset the quota.
    since = _now() - timedelta(hours=1)
    recent = db.scalar(
        select(func.count(ScanRequest.id)).where(
            ScanRequest.user_id == project.user_id, ScanRequest.created_at >= since
        )
    )
    if (recent or 0) >= settings.SCANS_PER_HOUR_PER_USER:
        db.rollback()
        raise RateLimitError(
            f"Scan limit reached ({settings.SCANS_PER_HOUR_PER_USER} per hour). "
            "Please try again later."
        )

    scan = Scan(project_id=project.id, status=ScanStatus.queued)
    db.add(scan)
    db.add(ScanRequest(user_id=project.user_id))
    db.commit()
    db.refresh(scan)
    logger.info("Queued scan %s for project %s", scan.id, project.id)
    return scan


def list_scans(db: Session, project_id: int, limit: int = MAX_LISTED_SCANS) -> list[Scan]:
    """Return a project's newest `limit` scans, newest first (findings not loaded)."""
    return list(
        db.scalars(
            select(Scan)
            .where(Scan.project_id == project_id)
            .order_by(Scan.created_at.desc(), Scan.id.desc())
            .limit(limit)
        ).all()
    )


def get_scan_for_user(db: Session, scan_id: int, user_id: int) -> Scan:
    """
    Return a scan with its findings, if its project belongs to the user.

    Raises:
        NotFoundError: If the scan does not exist or belongs to another user.
    """
    scan = db.scalar(
        select(Scan)
        .join(Project, Project.id == Scan.project_id)
        .where(Scan.id == scan_id, Project.user_id == user_id)
        .options(selectinload(Scan.findings))
    )
    if scan is None:
        raise NotFoundError("Scan not found")
    return scan


def truncate(text: str, limit: int) -> str:
    """Truncate `text` to `limit` characters, ending with an ellipsis when shortened."""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + ELLIPSIS


def truncate_path(path: str | None, limit: int = MAX_FILE_PATH_LENGTH) -> str | None:
    """Truncate a repository path to `limit` characters, keeping its (most informative) tail."""
    if path is None or len(path) <= limit:
        return path
    return ELLIPSIS + path[-(limit - 1) :]


def _mark_failed(db: Session, scan_id: int, message: str) -> None:
    db.rollback()
    scan = db.get(Scan, scan_id)
    if scan is None:
        return
    scan.status = ScanStatus.failed
    scan.error_message = message
    scan.completed_at = _now()
    db.commit()


def run_scan(scan_id: int) -> None:
    """
    Execute a queued scan (runs on the scan executor, see `submit_scan`).

    Opens its own session, clones the repository into a temporary directory, runs all
    checks, stores findings and score, and updates the project. Any failure marks the
    scan as failed with a user-readable message. The clone is always removed.

    Args:
        scan_id: Id of a scan in status "queued"
    """
    db = SessionLocal()
    tmp: str | None = None
    try:
        scan = db.get(Scan, scan_id)
        if scan is None or scan.status != ScanStatus.queued:
            logger.warning("run_scan: scan %s not found or not queued", scan_id)
            return
        project = db.get(Project, scan.project_id)
        if project is None:
            logger.warning("run_scan: project for scan %s no longer exists", scan_id)
            return

        scan.status = ScanStatus.running
        scan.started_at = _now()
        db.commit()

        workdir = Path(settings.SCAN_WORKDIR)
        workdir.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.mkdtemp(prefix=f"{WORKDIR_PREFIX}{scan_id}-", dir=workdir)
        repo_dir = Path(tmp) / "repo"

        with context.scan_context(settings.SCAN_TOTAL_TIMEOUT_SECONDS):
            clone = cloner.clone_repo(project.repo_url, project.default_branch, repo_dir)
            results = registry.run_all_checks(repo_dir)
            primary_language = language.detect_primary_language(repo_dir)
        score = scoring.compute_score(results)

        db.add_all(
            Finding(
                scan_id=scan.id,
                check_id=r.check_id,
                category=r.category,
                severity=r.severity,
                title=truncate(r.title, MAX_TITLE_LENGTH),
                recommendation=r.recommendation,
                file_path=truncate_path(r.file_path),
            )
            for r in results
        )
        finished = _now()
        scan.score = score
        scan.commit_sha = clone.commit_sha
        scan.status = ScanStatus.completed
        scan.completed_at = finished
        project.latest_score = score
        project.last_scanned_at = finished
        if primary_language is not None:
            project.primary_language = primary_language
        db.commit()
        logger.info("Scan %s completed: score=%s findings=%d", scan_id, score, len(results))
    except cloner.CloneError as exc:
        logger.warning("Scan %s failed to clone: %s", scan_id, exc)
        _safe_mark_failed(db, scan_id, str(exc))
    except context.ScanTimeoutError as exc:
        logger.warning("Scan %s exceeded its time budget", scan_id)
        _safe_mark_failed(db, scan_id, str(exc))
    except Exception:
        logger.exception("Scan %s failed unexpectedly", scan_id)
        _safe_mark_failed(db, scan_id, INTERNAL_ERROR_MESSAGE)
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
        db.close()


def _safe_mark_failed(db: Session, scan_id: int, message: str) -> None:
    try:
        _mark_failed(db, scan_id, message)
    except Exception:
        logger.exception("Could not mark scan %s as failed", scan_id)


def fail_interrupted_scans() -> int:
    """
    Mark scans left queued/running by a previous process as failed.

    Called once at startup. Assumes a single backend worker process: with several
    workers, one worker starting up would fail scans another worker is still running.

    Returns:
        The number of scans updated.
    """
    db = SessionLocal()
    try:
        result = db.execute(
            update(Scan)
            .where(Scan.status.in_(ACTIVE_STATUSES))
            .values(
                status=ScanStatus.failed,
                error_message=INTERRUPTED_MESSAGE,
                completed_at=_now(),
            )
        )
        db.commit()
        return int(getattr(result, "rowcount", 0) or 0)
    finally:
        db.close()


def get_executor() -> Executor:
    """Return the process-wide scan executor (created lazily, SCAN_CONCURRENCY threads)."""
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=settings.SCAN_CONCURRENCY, thread_name_prefix="scan"
            )
        return _executor


def submit_scan(scan_id: int) -> "Future[None] | None":
    """
    Hand a queued scan to the bounded scan executor (never Starlette's shared threadpool).

    If the executor is shutting down the scan is marked failed so it never stays queued.

    Args:
        scan_id: Id of a scan in status "queued"
    """
    try:
        return get_executor().submit(run_scan, scan_id)
    except RuntimeError:
        logger.warning("Scan executor unavailable; failing scan %s", scan_id)
        db = SessionLocal()
        try:
            _safe_mark_failed(db, scan_id, SHUTTING_DOWN_MESSAGE)
        finally:
            db.close()
        return None


def shutdown_executor() -> None:
    """Stop accepting scans and drop queued work (running scans finish in the background)."""
    global _executor
    with _executor_lock:
        executor, _executor = _executor, None
    if executor is not None:
        executor.shutdown(wait=False, cancel_futures=True)


def purge_stale_workdirs() -> int:
    """
    Remove leftover `scan-*` clone directories from SCAN_WORKDIR (called at startup).

    Only entries created by `run_scan` (prefix "scan-") are removed, so pointing
    SCAN_WORKDIR at a shared directory never deletes unrelated files. Assumes a single
    backend worker (no other process can be mid-scan).

    Returns:
        Number of entries removed.
    """
    workdir = Path(settings.SCAN_WORKDIR)
    if not workdir.is_dir():
        return 0
    removed = 0
    for entry in workdir.iterdir():
        if not entry.name.startswith(WORKDIR_PREFIX):
            continue
        try:
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            removed += 1
        except OSError:
            logger.warning("Could not remove stale scan directory %s", entry.name)
    return removed
