"""API + scan_service integration tests for projects and scans (no network).

The background `run_scan` is replaced by a no-op for endpoint tests; `run_scan` itself
is exercised directly with a patched cloner and a SessionLocal bound to the test
transaction.
"""

import shutil
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.finding import Finding
from app.models.project import Project
from app.models.scan import Scan, ScanStatus
from app.models.scan_request import ScanRequest
from app.models.user import User
from app.scanner import cloner
from app.services import scan_service
from tests.conftest import InlineExecutor

FIXTURES = Path(__file__).parent / "fixtures" / "repos"
URL = "https://github.com/octocat/Hello-World"

# Captured before the autouse fixture replaces scan_service.run_scan with a recorder.
_real_run_scan = scan_service.run_scan

Headers = Callable[[User], dict[str, str]]


@pytest.fixture(autouse=True)
def _no_background_scan(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Record scheduled scans instead of running them."""
    scheduled: list[int] = []
    monkeypatch.setattr(scan_service, "run_scan", scheduled.append)
    return scheduled


@pytest.fixture
def headers(user: User, auth_headers: Headers) -> dict[str, str]:
    return auth_headers(user)


@pytest.fixture
def other_headers(user_factory: Callable[..., User], auth_headers: Headers) -> dict[str, str]:
    return auth_headers(user_factory())


def _create(client: TestClient, headers: dict[str, str], url: str = URL, **extra: str) -> dict:
    resp = client.post(
        "/api/v1/projects", json={"name": "Hello", "repo_url": url, **extra}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- projects


def test_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/projects").status_code == 401


def test_create_normalizes_url(client: TestClient, headers: dict[str, str]) -> None:
    body = _create(
        client, headers, "  https://GITHUB.com/octocat/Hello-World.git/ ", default_branch="main"
    )
    assert body["repo_url"] == URL
    assert body["default_branch"] == "main"
    assert body["latest_score"] is None
    assert set(body) == {
        "id",
        "name",
        "repo_url",
        "default_branch",
        "primary_language",
        "latest_score",
        "last_scanned_at",
        "created_at",
        "updated_at",
    }


@pytest.mark.parametrize(
    "url", ["https://gitlab.com/a/b", "not a url", "https://github.com/a", "x" * 600]
)
def test_create_invalid_url_400(client: TestClient, headers: dict[str, str], url: str) -> None:
    resp = client.post("/api/v1/projects", json={"name": "x", "repo_url": url}, headers=headers)
    assert resp.status_code == 400
    assert "Invalid repository URL" in resp.json()["detail"]


def test_create_invalid_branch_400(client: TestClient, headers: dict[str, str]) -> None:
    resp = client.post(
        "/api/v1/projects",
        json={"name": "x", "repo_url": URL, "default_branch": "--upload-pack=x"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_create_duplicate_409(
    client: TestClient, headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    _create(client, headers)
    resp = client.post(
        "/api/v1/projects", json={"name": "y", "repo_url": URL + ".git"}, headers=headers
    )
    assert resp.status_code == 409
    # A different user may register the same repo.
    _create(client, other_headers)


def test_list_paginates_own_projects(
    client: TestClient, headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    for i in range(3):
        _create(client, headers, f"https://github.com/o/r{i}")
    _create(client, other_headers, "https://github.com/o/other")
    resp = client.get("/api/v1/projects?page=1&size=2", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3 and body["page"] == 1 and body["size"] == 2
    assert len(body["items"]) == 2
    page2 = client.get("/api/v1/projects?page=2&size=2", headers=headers).json()
    assert len(page2["items"]) == 1


def test_get_update_delete(client: TestClient, headers: dict[str, str]) -> None:
    pid = _create(client, headers, default_branch="main")["id"]
    detail = client.get(f"/api/v1/projects/{pid}", headers=headers).json()
    assert detail["latest_scan"] is None

    resp = client.put(f"/api/v1/projects/{pid}", json={"name": " New "}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"
    assert resp.json()["default_branch"] == "main"  # untouched
    resp = client.put(f"/api/v1/projects/{pid}", json={"default_branch": None}, headers=headers)
    assert resp.json()["default_branch"] is None

    assert client.delete(f"/api/v1/projects/{pid}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/projects/{pid}", headers=headers).status_code == 404


def test_other_users_project_is_404(
    client: TestClient, headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    pid = _create(client, headers)["id"]
    base = f"/api/v1/projects/{pid}"
    assert client.get(base, headers=other_headers).status_code == 404
    assert client.put(base, json={"name": "x"}, headers=other_headers).status_code == 404
    assert client.delete(base, headers=other_headers).status_code == 404
    assert client.post(f"{base}/scans", headers=other_headers).status_code == 404
    assert client.get(f"{base}/scans", headers=other_headers).status_code == 404


# --------------------------------------------------------------------------- scans API


def test_start_scan_202_then_409(
    client: TestClient, headers: dict[str, str], _no_background_scan: list[int]
) -> None:
    pid = _create(client, headers)["id"]
    resp = client.post(f"/api/v1/projects/{pid}/scans", headers=headers)
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued" and body["project_id"] == pid
    assert _no_background_scan == [body["id"]]

    assert client.post(f"/api/v1/projects/{pid}/scans", headers=headers).status_code == 409

    history = client.get(f"/api/v1/projects/{pid}/scans", headers=headers).json()
    assert [s["id"] for s in history] == [body["id"]]
    assert "findings" not in history[0]


def test_start_scan_rate_limited_429(
    client: TestClient, headers: dict[str, str], db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "SCANS_PER_HOUR_PER_USER", 2)
    p1 = _create(client, headers, "https://github.com/o/a")["id"]
    p2 = _create(client, headers, "https://github.com/o/b")["id"]
    assert client.post(f"/api/v1/projects/{p1}/scans", headers=headers).status_code == 202
    assert client.post(f"/api/v1/projects/{p2}/scans", headers=headers).status_code == 202
    for scan in db.scalars(select(Scan)):
        scan.status = ScanStatus.completed
    db.commit()
    assert client.post(f"/api/v1/projects/{p1}/scans", headers=headers).status_code == 429


def test_start_scan_hands_off_to_scan_executor(
    client: TestClient,
    headers: dict[str, str],
    inline_executor: InlineExecutor,
    _no_background_scan: list[int],
) -> None:
    """M2: the endpoint submits to the dedicated executor, not Starlette's threadpool."""
    pid = _create(client, headers)["id"]
    sid = client.post(f"/api/v1/projects/{pid}/scans", headers=headers).json()["id"]
    assert [args for _fn, args in inline_executor.submitted] == [(sid,)]
    assert _no_background_scan == [sid]


def test_scan_quota_survives_project_deletion(
    client: TestClient, headers: dict[str, str], db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M3: deleting projects (which cascades to scans) must not reset the hourly quota."""
    monkeypatch.setattr(settings, "SCANS_PER_HOUR_PER_USER", 2)
    for name in ("a", "b"):
        pid = _create(client, headers, f"https://github.com/o/{name}")["id"]
        assert client.post(f"/api/v1/projects/{pid}/scans", headers=headers).status_code == 202
        assert client.delete(f"/api/v1/projects/{pid}", headers=headers).status_code == 204
    assert db.scalar(select(Scan.id)) is None  # scans are gone ...
    assert len(db.scalars(select(ScanRequest.id)).all()) == 2  # ... the quota log is not
    pid = _create(client, headers, "https://github.com/o/c")["id"]
    resp = client.post(f"/api/v1/projects/{pid}/scans", headers=headers)
    assert resp.status_code == 429
    assert "Scan limit reached" in resp.json()["detail"]


def test_old_scan_requests_do_not_count(
    client: TestClient,
    headers: dict[str, str],
    db: Session,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SCANS_PER_HOUR_PER_USER", 1)
    db.add(ScanRequest(user_id=user.id, created_at=datetime.now(UTC) - timedelta(hours=2)))
    db.commit()
    pid = _create(client, headers)["id"]
    assert client.post(f"/api/v1/projects/{pid}/scans", headers=headers).status_code == 202


def test_scanner_busy_global_cap_429(
    client: TestClient,
    headers: dict[str, str],
    other_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M2: queued+running scans across ALL users are capped by SCAN_MAX_QUEUED."""
    monkeypatch.setattr(settings, "SCAN_MAX_QUEUED", 1)
    other_pid = _create(client, other_headers)["id"]
    assert (
        client.post(f"/api/v1/projects/{other_pid}/scans", headers=other_headers).status_code == 202
    )
    pid = _create(client, headers)["id"]
    resp = client.post(f"/api/v1/projects/{pid}/scans", headers=headers)
    assert resp.status_code == 429
    assert resp.json() == {"detail": "The scanner is busy, please try again in a few minutes"}


def test_project_limit_per_user_409(
    client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MAX_PROJECTS_PER_USER", 2)
    _create(client, headers, "https://github.com/o/a")
    _create(client, headers, "https://github.com/o/b")
    resp = client.post(
        "/api/v1/projects",
        json={"name": "c", "repo_url": "https://github.com/o/c"},
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"].startswith("Project limit reached (2)")


def test_list_scans_returns_newest_50(
    client: TestClient, headers: dict[str, str], db: Session
) -> None:
    """L10: history is capped at the newest 50 scans."""
    pid = _create(client, headers)["id"]
    base = datetime.now(UTC) - timedelta(days=1)
    db.add_all(
        Scan(project_id=pid, status=ScanStatus.completed, created_at=base + timedelta(minutes=i))
        for i in range(60)
    )
    db.commit()
    history = client.get(f"/api/v1/projects/{pid}/scans", headers=headers).json()
    assert len(history) == 50
    stamps = [h["created_at"] for h in history]
    assert stamps == sorted(stamps, reverse=True)
    newest = db.scalars(select(Scan.id).order_by(Scan.created_at.desc()).limit(50)).all()
    assert [h["id"] for h in history] == list(newest)


def test_rate_limit_429_uses_detail_shape(client: TestClient, enable_rate_limit: None) -> None:
    """INFO: slowapi's 429 body matches the contract's {"detail": ...} error shape."""
    body = {"email": "nobody@example.com", "password": "wrong-password"}
    statuses = [client.post("/api/v1/auth/login", json=body) for _ in range(6)]
    last = statuses[-1]
    assert last.status_code == 429
    assert last.json() == {"detail": "Too many requests, please try again later"}


def test_cors_does_not_allow_credentials(client: TestClient) -> None:
    resp = client.options(
        "/api/v1/projects",
        headers={
            "Origin": settings.ALLOWED_ORIGINS[0],
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == settings.ALLOWED_ORIGINS[0]
    assert "access-control-allow-credentials" not in resp.headers


def test_get_scan_ownership(
    client: TestClient, headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    pid = _create(client, headers)["id"]
    sid = client.post(f"/api/v1/projects/{pid}/scans", headers=headers).json()["id"]
    resp = client.get(f"/api/v1/scans/{sid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["findings"] == []
    assert client.get(f"/api/v1/scans/{sid}", headers=other_headers).status_code == 404
    assert client.get("/api/v1/scans/999999", headers=headers).status_code == 404


# --------------------------------------------------------------------------- run_scan


@pytest.fixture
def scan_env(db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Bind run_scan's SessionLocal to the test transaction; use a tmp SCAN_WORKDIR."""
    connection = db.connection()

    def _session() -> Session:
        return Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    workdir = tmp_path / "work"
    monkeypatch.setattr(scan_service, "SessionLocal", _session)
    monkeypatch.setattr(settings, "SCAN_WORKDIR", str(workdir))
    yield workdir


def _queued_scan(db: Session, user: User, branch: str | None = None) -> Scan:
    project = Project(user_id=user.id, name="p", repo_url=URL, default_branch=branch)
    db.add(project)
    db.commit()
    scan = Scan(project_id=project.id, status=ScanStatus.queued)
    db.add(scan)
    db.commit()
    return scan


def _fake_clone(fixture: str) -> Callable[[str, str | None, Path], cloner.CloneResult]:
    def _clone(url: str, branch: str | None, dest: Path) -> cloner.CloneResult:
        assert url == URL
        shutil.copytree(FIXTURES / fixture, dest)
        return cloner.CloneResult(commit_sha="b" * 40, size_bytes=1)

    return _clone


def test_run_scan_completed(
    db: Session,
    user: User,
    scan_env: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    headers: dict[str, str],
) -> None:
    monkeypatch.setattr(cloner, "clone_repo", _fake_clone("empty"))
    scan = _queued_scan(db, user)
    _real_run_scan(scan.id)

    db.expire_all()
    scan = db.get(Scan, scan.id)
    assert scan is not None
    assert scan.status is ScanStatus.completed
    assert scan.score == 1
    assert scan.commit_sha == "b" * 40
    assert scan.started_at is not None and scan.completed_at is not None
    findings = db.scalars(select(Finding.check_id).where(Finding.scan_id == scan.id)).all()
    assert len(findings) == 7
    project = db.get(Project, scan.project_id)
    assert project is not None
    assert project.latest_score == 1
    assert project.primary_language == "Python"
    assert project.last_scanned_at is not None
    assert list(scan_env.iterdir()) == []  # clone removed

    detail = client.get(f"/api/v1/projects/{project.id}", headers=headers).json()
    assert detail["latest_scan"]["id"] == scan.id
    assert len(detail["latest_scan"]["findings"]) == 7


def test_run_scan_clone_error(
    db: Session, user: User, scan_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail(url: str, branch: str | None, dest: Path) -> cloner.CloneResult:
        dest.mkdir(parents=True)
        raise cloner.CloneError("Repository not found or is private")

    monkeypatch.setattr(cloner, "clone_repo", _fail)
    scan = _queued_scan(db, user)
    _real_run_scan(scan.id)
    db.expire_all()
    scan = db.get(Scan, scan.id)
    assert scan is not None
    assert scan.status is ScanStatus.failed
    assert scan.error_message == "Repository not found or is private"
    assert list(scan_env.iterdir()) == []


def test_run_scan_unexpected_error(
    db: Session, user: User, scan_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(url: str, branch: str | None, dest: Path) -> cloner.CloneResult:
        raise RuntimeError("secret internals")

    monkeypatch.setattr(cloner, "clone_repo", _boom)
    scan = _queued_scan(db, user)
    _real_run_scan(scan.id)
    db.expire_all()
    scan = db.get(Scan, scan.id)
    assert scan is not None
    assert scan.status is ScanStatus.failed
    assert scan.error_message == "Scan failed due to an internal error"


def test_fail_interrupted_scans(db: Session, user: User, scan_env: Path) -> None:
    scan = _queued_scan(db, user)
    assert scan_service.fail_interrupted_scans() >= 1
    db.expire_all()
    refreshed = db.get(Scan, scan.id)
    assert refreshed is not None
    assert refreshed.status is ScanStatus.failed
    assert refreshed.error_message == "Scan interrupted, please retry"
