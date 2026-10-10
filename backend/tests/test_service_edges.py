"""Failure / cleanup paths of scan_service, scanner context/limits, config validation,
and edge cases of auth_service."""

import itertools
import os
import shutil
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.google import GoogleUserInfo
from app.auth.jwt import create_refresh_token
from app.config import Settings, settings
from app.exceptions import ConflictError, UnauthorizedError
from app.models.finding import Finding, FindingCategory, Severity
from app.models.project import Project
from app.models.refresh_token import RefreshToken
from app.models.scan import Scan, ScanStatus
from app.models.user import User
from app.scanner import cloner, context, fs, registry
from app.scanner.types import CheckResult
from app.services import auth_service, scan_service

FIXTURES = Path(__file__).parent / "fixtures" / "repos"
URL = "https://github.com/octocat/Hello-World"
_n = itertools.count(1)


# --------------------------------------------------------------------------- helpers


@pytest.fixture
def session_factory(db: Session) -> Callable[..., Session]:
    connection = db.connection()

    def _make(cls: type[Session] = Session) -> Session:
        return cls(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    return _make


@pytest.fixture
def scan_env(
    session_factory: Callable[..., Session], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    workdir = tmp_path / "work"
    monkeypatch.setattr(scan_service, "SessionLocal", session_factory)
    monkeypatch.setattr(settings, "SCAN_WORKDIR", str(workdir))
    yield workdir


def _queued(db: Session, user: User, status: ScanStatus = ScanStatus.queued) -> Scan:
    project = Project(user_id=user.id, name="p", repo_url=f"{URL}-{next(_n)}")
    db.add(project)
    db.commit()
    scan = Scan(project_id=project.id, status=status)
    db.add(scan)
    db.commit()
    return scan


def _copy_fixture(name: str) -> Callable[[str, str | None, Path], cloner.CloneResult]:
    def _clone(url: str, branch: str | None, dest: Path) -> cloner.CloneResult:
        shutil.copytree(FIXTURES / name, dest)
        return cloner.CloneResult(commit_sha="d" * 40, size_bytes=1)

    return _clone


# --------------------------------------------------------------------------- run_scan


@pytest.mark.parametrize("status", [ScanStatus.running, ScanStatus.completed, ScanStatus.failed])
def test_run_scan_ignores_non_queued(
    db: Session,
    user: User,
    scan_env: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: ScanStatus,
) -> None:
    called: list[Any] = []
    monkeypatch.setattr(cloner, "clone_repo", lambda *a: called.append(a))
    scan = _queued(db, user, status)
    scan_service.run_scan(scan.id)
    db.expire_all()
    assert db.get(Scan, scan.id).status is status  # type: ignore[union-attr]
    assert called == []
    assert not scan_env.exists()  # no temp dir ever created


def test_run_scan_unknown_id_is_noop(scan_env: Path) -> None:
    scan_service.run_scan(987654321)
    assert not scan_env.exists()


def test_run_scan_project_missing_is_noop(
    db: Session,
    user: User,
    session_factory: Callable[..., Session],
    scan_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the project vanished between queueing and running, run_scan returns quietly."""

    class _NoProjectSession(Session):
        def get(self, entity: Any, ident: Any, **kw: Any) -> Any:  # type: ignore[override]
            if entity is Project:
                return None
            return super().get(entity, ident, **kw)

    monkeypatch.setattr(scan_service, "SessionLocal", lambda: session_factory(_NoProjectSession))
    scan = _queued(db, user)
    scan_service.run_scan(scan.id)
    db.expire_all()
    assert db.get(Scan, scan.id).status is ScanStatus.queued  # type: ignore[union-attr]


def test_run_scan_check_crash_marks_failed_and_cleans_up(
    db: Session, user: User, scan_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cloner, "clone_repo", _copy_fixture("complete"))

    def _explode(root: Path) -> Any:
        raise ValueError("internal detail /etc/passwd")

    monkeypatch.setattr(registry, "run_all_checks", _explode)
    scan = _queued(db, user)
    scan_service.run_scan(scan.id)
    db.expire_all()
    refreshed = db.get(Scan, scan.id)
    assert refreshed is not None
    assert refreshed.status is ScanStatus.failed
    assert refreshed.error_message == scan_service.INTERNAL_ERROR_MESSAGE
    assert "/etc/passwd" not in (refreshed.error_message or "")
    assert refreshed.completed_at is not None
    assert list(scan_env.iterdir()) == []  # clone deleted on failure
    assert db.scalars(select(Finding).where(Finding.scan_id == scan.id)).all() == []
    project = db.get(Project, refreshed.project_id)
    assert project is not None and project.latest_score is None


def test_run_scan_clone_dir_removed_after_success(
    db: Session, user: User, scan_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Path] = []
    inner = _copy_fixture("complete")

    def _clone(url: str, branch: str | None, dest: Path) -> cloner.CloneResult:
        seen.append(dest)
        assert dest.parent.parent == scan_env  # clone lives under SCAN_WORKDIR
        return inner(url, branch, dest)

    monkeypatch.setattr(cloner, "clone_repo", _clone)
    scan = _queued(db, user)
    scan_service.run_scan(scan.id)
    assert seen and not seen[0].exists()
    assert list(scan_env.iterdir()) == []
    db.expire_all()
    done = db.get(Scan, scan.id)
    assert done is not None and done.status is ScanStatus.completed and done.score == 100


def test_safe_mark_failed_swallows_errors(
    db: Session, user: User, scan_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _bad_clone(*a: Any) -> cloner.CloneResult:
        raise cloner.CloneError("nope")

    def _bad_mark(*a: Any) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(cloner, "clone_repo", _bad_clone)
    monkeypatch.setattr(scan_service, "_mark_failed", _bad_mark)
    scan = _queued(db, user)
    scan_service.run_scan(scan.id)  # must not raise
    assert list(scan_env.iterdir()) == []


def test_mark_failed_missing_scan_is_noop(session_factory: Callable[..., Session]) -> None:
    s = session_factory()
    try:
        scan_service._mark_failed(s, 123456789, "x")  # no exception
    finally:
        s.close()


def test_start_scan_conflict_while_running(db: Session, user: User) -> None:
    scan = _queued(db, user, ScanStatus.running)
    project = db.get(Project, scan.project_id)
    assert project is not None
    with pytest.raises(ConflictError):
        scan_service.start_scan(db, project)


def test_start_scan_allowed_after_failure(db: Session, user: User) -> None:
    scan = _queued(db, user, ScanStatus.failed)
    project = db.get(Project, scan.project_id)
    assert project is not None
    new = scan_service.start_scan(db, project)
    assert new.status is ScanStatus.queued


def test_fail_interrupted_ignores_finished(db: Session, user: User, scan_env: Path) -> None:
    done = _queued(db, user, ScanStatus.completed)
    running = _queued(db, user, ScanStatus.running)
    assert scan_service.fail_interrupted_scans() >= 1
    db.expire_all()
    assert db.get(Scan, done.id).status is ScanStatus.completed  # type: ignore[union-attr]
    assert db.get(Scan, running.id).status is ScanStatus.failed  # type: ignore[union-attr]


# --------------------------------------------------------------------------- auth


def test_register_integrity_race_maps_to_conflict(
    db: Session, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concurrent registration: the pre-check misses, the unique index catches it."""
    monkeypatch.setattr(auth_service, "get_user_by_email", lambda db, email: None)
    with pytest.raises(ConflictError, match="Email already registered"):
        auth_service.register(db, user.email, "password123", None)


def test_register_normalizes_email(db: Session) -> None:
    auth_service.register(db, "  MiXeD@Example.COM ", "password123", "N")
    assert auth_service.get_user_by_email(db, "mixed@example.com") is not None


def test_refresh_row_belongs_to_other_user(db: Session, user_factory: Callable[..., User]) -> None:
    a, b = user_factory(), user_factory()
    token, expires = create_refresh_token(a.id)
    db.add(
        RefreshToken(user_id=b.id, token=auth_service.hash_refresh_token(token), expires_at=expires)
    )
    db.commit()
    with pytest.raises(UnauthorizedError):
        auth_service.refresh(db, token)


def test_refresh_naive_expiry_is_treated_as_utc(db: Session, user: User) -> None:
    token, _ = create_refresh_token(user.id)
    past_naive = (datetime.now(UTC) - timedelta(minutes=1)).replace(tzinfo=None)
    row = RefreshToken(
        user_id=user.id, token=auth_service.hash_refresh_token(token), expires_at=past_naive
    )
    db.add(row)
    db.commit()
    # Force the attribute to a naive value regardless of DB column tz handling.
    row.expires_at = past_naive
    with pytest.raises(UnauthorizedError):
        auth_service._get_valid_refresh_row(db, token)


def test_refresh_revoked_token_cannot_be_reused(db: Session, user: User) -> None:
    pair = auth_service.issue_tokens(db, user)
    auth_service.refresh(db, pair.refresh_token)
    with pytest.raises(UnauthorizedError):
        auth_service.refresh(db, pair.refresh_token)


def test_refresh_deleted_user(db: Session, user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    pair = auth_service.issue_tokens(db, user)
    real_get = db.get

    def _get(entity: Any, ident: Any, **kw: Any) -> Any:
        return None if entity is User else real_get(entity, ident, **kw)

    monkeypatch.setattr(db, "get", _get)
    with pytest.raises(UnauthorizedError):
        auth_service.refresh(db, pair.refresh_token)


def test_logout_twice_is_idempotent(db: Session, user: User) -> None:
    pair = auth_service.issue_tokens(db, user)
    auth_service.logout(db, pair.refresh_token)
    auth_service.logout(db, pair.refresh_token)
    stored = auth_service.hash_refresh_token(pair.refresh_token)
    row = db.scalars(select(RefreshToken).where(RefreshToken.token == stored)).one()
    assert row.revoked is True


@pytest.mark.parametrize(("raw", "expected"), [("  Ann  ", "Ann"), ("   ", None), (None, None)])
def test_update_profile_trims(
    db: Session, user: User, raw: str | None, expected: str | None
) -> None:
    assert auth_service.update_profile(db, user, raw).full_name == expected


def _info(**kw: Any) -> GoogleUserInfo:
    base: dict[str, Any] = {
        "sub": "g-1",
        "email": "g@example.com",
        "email_verified": True,
        "name": "G User",
        "picture": None,
    }
    base.update(kw)
    return GoogleUserInfo(**base)


def test_upsert_google_keeps_existing_name_and_skips_empty_picture(
    db: Session, user_factory: Callable[..., User]
) -> None:
    existing = user_factory(email="g@example.com", full_name="Original", avatar_url="old.png")
    out = auth_service.upsert_google_user(db, _info(picture=None, name="Google Name"))
    assert out.id == existing.id
    assert out.full_name == "Original"
    assert out.avatar_url == "old.png"
    assert out.google_id == "g-1"
    assert out.is_verified is True


def test_upsert_google_fills_missing_name(db: Session, user_factory: Callable[..., User]) -> None:
    user_factory(email="g@example.com", full_name=None)
    out = auth_service.upsert_google_user(db, _info(picture="https://x/p.png"))
    assert out.full_name == "G User"
    assert out.avatar_url == "https://x/p.png"


def test_upsert_google_unverified_rejected(db: Session) -> None:
    with pytest.raises(UnauthorizedError):
        auth_service.upsert_google_user(db, _info(email_verified=False))


def test_authenticate_unknown_email_still_runs_hash(db: Session) -> None:
    with pytest.raises(UnauthorizedError, match="Invalid email or password"):
        auth_service.authenticate(db, "nobody@example.com", "whatever")


# --------------------------------------------------------------------------- M4 truncation


def test_run_scan_truncates_attacker_controlled_strings(
    db: Session, user: User, scan_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 600-char path / 300-char title from a hostile repo must not crash the insert."""
    long_path = "/".join(["d" * 49] * 12) + "/.env"  # 600+ chars
    assert len(long_path) > 600
    monkeypatch.setattr(cloner, "clone_repo", _copy_fixture("complete"))
    monkeypatch.setattr(
        registry,
        "run_all_checks",
        lambda root: [
            CheckResult(
                check_id="committed_env_file",
                category=FindingCategory.configuration,
                severity=Severity.critical,
                title="Environment file committed: " + long_path,
                recommendation="remove it",
                file_path=long_path,
            )
        ],
    )
    scan = _queued(db, user)
    scan_service.run_scan(scan.id)
    db.expire_all()
    refreshed = db.get(Scan, scan.id)
    assert refreshed is not None and refreshed.status is ScanStatus.completed
    finding = db.scalars(select(Finding).where(Finding.scan_id == scan.id)).one()
    assert finding.file_path is not None and len(finding.file_path) == 500
    assert finding.file_path.startswith("\u2026") and finding.file_path.endswith("/.env")
    assert long_path.endswith(finding.file_path[1:])
    assert len(finding.title) == 200 and finding.title.endswith("\u2026")


def test_truncate_helpers_leave_short_values() -> None:
    assert scan_service.truncate("abc", 200) == "abc"
    assert scan_service.truncate_path(None) is None
    assert scan_service.truncate_path("a/b") == "a/b"
    assert scan_service.truncate_path("x" * 10, 5) == "\u2026xxxx"


# --------------------------------------------------------------------------- L5 deadline / walk


def test_run_scan_total_timeout_marks_failed(
    db: Session, user: User, scan_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "SCAN_TOTAL_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(cloner, "clone_repo", _copy_fixture("complete"))
    scan = _queued(db, user)
    scan_service.run_scan(scan.id)
    db.expire_all()
    refreshed = db.get(Scan, scan.id)
    assert refreshed is not None
    assert refreshed.status is ScanStatus.failed
    assert refreshed.error_message is not None and "timed out" in refreshed.error_message
    assert list(scan_env.iterdir()) == []


def test_run_scan_walks_repository_once(
    db: Session, user: User, scan_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L5: all checks + language detection share a single os.walk of the clone."""
    walked: list[str] = []
    real_walk = os.walk

    def _counting_walk(top: Any, *a: Any, **kw: Any) -> Any:
        walked.append(str(top))
        return real_walk(top, *a, **kw)

    monkeypatch.setattr(fs.os, "walk", _counting_walk)
    monkeypatch.setattr(cloner, "clone_repo", _copy_fixture("complete"))
    scan = _queued(db, user)
    scan_service.run_scan(scan.id)
    db.expire_all()
    refreshed = db.get(Scan, scan.id)
    assert refreshed is not None and refreshed.status is ScanStatus.completed
    assert len(walked) == 1


def test_walk_cache_is_scoped_to_context(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x")
    root = tmp_path.resolve()
    with context.scan_context(60) as ctx:
        assert [p.name for p in fs.walk_files(root)] == ["a.py"]
        (tmp_path / "b.py").write_text("x")
        assert [p.name for p in fs.walk_files(root)] == ["a.py"]  # cached
        assert root in ctx.walk_cache
    assert [p.name for p in fs.walk_files(root)] == ["a.py", "b.py"]  # fresh outside


def test_walk_dirs_capped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("a", "b", "c"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(fs, "MAX_WALK_DIRS", 2)
    assert len(list(fs.walk_dirs(tmp_path.resolve()))) == 2


def test_walk_stops_at_deadline(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x")
    with context.scan_context(0), pytest.raises(context.ScanTimeoutError):
        list(fs.walk_files(tmp_path.resolve()))


def test_context_clamp_timeout() -> None:
    assert context.remaining() is None
    assert context.clamp_timeout(7) == 7
    with context.scan_context(None):
        assert context.clamp_timeout(7) == 7
        context.check_deadline()
    with context.scan_context(3):
        assert context.clamp_timeout(60) <= 3
        assert context.clamp_timeout(1) == 1
    with context.scan_context(0), pytest.raises(context.ScanTimeoutError):
        context.clamp_timeout(5)


# --------------------------------------------------------------------------- M2 executor


def test_submit_scan_uses_bounded_thread_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scan_service, "_executor", None)
    monkeypatch.setattr(settings, "SCAN_CONCURRENCY", 3)
    ran: list[int] = []
    monkeypatch.setattr(scan_service, "run_scan", ran.append)
    try:
        executor = scan_service.get_executor()
        assert isinstance(executor, ThreadPoolExecutor)
        assert executor._max_workers == 3
        assert scan_service.get_executor() is executor
        future = scan_service.submit_scan(42)
        assert future is not None
        future.result(timeout=10)
        assert ran == [42]
    finally:
        scan_service.shutdown_executor()
    assert scan_service._executor is None
    scan_service.shutdown_executor()  # idempotent


def test_submit_scan_after_shutdown_marks_failed(
    db: Session, user: User, scan_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dead = ThreadPoolExecutor(max_workers=1)
    dead.shutdown()
    monkeypatch.setattr(scan_service, "_executor", dead)
    scan = _queued(db, user)
    assert scan_service.submit_scan(scan.id) is None
    db.expire_all()
    refreshed = db.get(Scan, scan.id)
    assert refreshed is not None
    assert refreshed.status is ScanStatus.failed
    assert refreshed.error_message == scan_service.SHUTTING_DOWN_MESSAGE


# --------------------------------------------------------------------------- L4 workdir purge


def test_purge_stale_workdirs_only_removes_scan_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "SCAN_WORKDIR", str(tmp_path))
    (tmp_path / "scan-1-abc" / "repo").mkdir(parents=True)
    (tmp_path / "scan-1-abc" / "repo" / "f").write_text("x")
    (tmp_path / "scan-stray-file").write_text("x")
    (tmp_path / "keep-me").mkdir()
    (tmp_path / "unrelated.txt").write_text("x")
    assert scan_service.purge_stale_workdirs() == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keep-me", "unrelated.txt"]


def test_purge_stale_workdirs_missing_dir_and_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "SCAN_WORKDIR", str(tmp_path / "missing"))
    assert scan_service.purge_stale_workdirs() == 0
    monkeypatch.setattr(settings, "SCAN_WORKDIR", str(tmp_path))
    (tmp_path / "scan-9-x").mkdir()

    def _fail(*_a: Any, **_k: Any) -> None:
        raise OSError("busy")

    monkeypatch.setattr(scan_service.shutil, "rmtree", _fail)
    assert scan_service.purge_stale_workdirs() == 0


def test_startup_purges_workdir_and_survives_errors(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.main import app

    monkeypatch.setattr(settings, "SCAN_WORKDIR", str(tmp_path))
    (tmp_path / "scan-5-old").mkdir()
    with TestClient(app):
        pass
    assert not (tmp_path / "scan-5-old").exists()

    def _boom() -> int:
        raise RuntimeError("db down")

    monkeypatch.setattr(scan_service, "purge_stale_workdirs", _boom)
    monkeypatch.setattr(scan_service, "fail_interrupted_scans", _boom)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200


# --------------------------------------------------------------------------- H3 config


GOOD_KEY = "k" * 48


@pytest.mark.parametrize(
    "key",
    [
        "dev-secret-key-change-in-production",
        "your-secret-key-change-in-production",
        "your-secret-key",
        "changeme",
        "CHANGEME",
        "short-but-random-31-characters!",
    ],
)
def test_production_refuses_placeholder_or_short_secret(key: str) -> None:
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(_env_file=None, ENV="production", SECRET_KEY=key)  # type: ignore[call-arg]


def test_production_accepts_strong_secret() -> None:
    cfg = Settings(_env_file=None, ENV="production", SECRET_KEY=GOOD_KEY)  # type: ignore[call-arg]
    assert cfg.ENV == "production"
    assert cfg.ALGORITHM == "HS256"


def test_development_allows_default_secret() -> None:
    cfg = Settings(_env_file=None, ENV="development")  # type: ignore[call-arg]
    assert cfg.SECRET_KEY == "dev-secret-key-change-in-production"


@pytest.mark.parametrize("algorithm", ["none", "HS512", "RS256"])
def test_algorithm_pinned_to_hs256(algorithm: str) -> None:
    with pytest.raises(ValueError, match="ALGORITHM must be HS256"):
        Settings(_env_file=None, ALGORITHM=algorithm)  # type: ignore[call-arg]


@pytest.mark.parametrize("field", ["SCAN_CONCURRENCY", "SCAN_MAX_QUEUED", "SCAN_MAX_FILES"])
def test_scanner_limits_must_be_positive(field: str) -> None:
    with pytest.raises(ValueError, match="must be >= 1"):
        Settings(_env_file=None, **{field: 0})  # type: ignore[arg-type]


def test_invalid_env_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, ENV="staging")  # type: ignore[arg-type]
