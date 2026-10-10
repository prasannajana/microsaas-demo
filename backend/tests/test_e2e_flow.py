"""End-to-end API flow through the real routers and the real background task.

register -> create project -> POST scan (202) -> BackgroundTasks runs ``run_scan``
-> GET scan completed -> project.latest_score -> analytics -> rescan -> trend.

Only the network clone is faked (fixture repo copied into ``dest``); ``run_scan``
itself is the real implementation, bound to the per-test DB transaction.

Note on BackgroundTasks: Starlette's TestClient drives the full ASGI call, and
background tasks run after the response is sent but *before* ``client.post``
returns. The 202 body still says ``queued`` (proving the API answered before the
work ran) while the DB already shows ``completed`` when the call returns.
"""

import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.scanner import cloner
from app.services import scan_service

FIXTURES = Path(__file__).parent / "fixtures" / "repos"
REPO_URL = "https://github.com/octocat/Hello-World"


@pytest.fixture
def e2e_env(db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict]:
    """Bind run_scan's own sessions to the test transaction and fake the clone."""
    connection = db.connection()
    state: dict = {"fixture": "empty", "clones": []}

    def _session() -> Session:
        return Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    def _clone(url: str, branch: str | None, dest: Path) -> cloner.CloneResult:
        assert url == REPO_URL
        state["clones"].append(dest)
        shutil.copytree(FIXTURES / state["fixture"], dest)
        return cloner.CloneResult(commit_sha="e" * 40, size_bytes=1)

    workdir = tmp_path / "work"
    monkeypatch.setattr(scan_service, "SessionLocal", _session)
    monkeypatch.setattr(settings, "SCAN_WORKDIR", str(workdir))
    monkeypatch.setattr(cloner, "clone_repo", _clone)
    state["workdir"] = workdir
    state["clone"] = _clone
    yield state


def _register(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "flow@example.com", "password": "password123", "full_name": "Flow"},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _start_scan(client: TestClient, headers: dict[str, str], project_id: int) -> dict:
    resp = client.post(f"/api/v1/projects/{project_id}/scans", headers=headers)
    assert resp.status_code == 202, resp.text
    return resp.json()


def test_full_user_flow(client: TestClient, e2e_env: dict) -> None:
    headers = _register(client)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["email"] == "flow@example.com"

    created = client.post(
        "/api/v1/projects",
        json={"name": "Hello", "repo_url": REPO_URL + ".git/"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["repo_url"] == REPO_URL  # normalized
    assert project["latest_score"] is None

    # --- first scan: "empty" fixture --------------------------------------------------
    accepted = _start_scan(client, headers, project["id"])
    assert accepted["status"] == "queued"  # the API answered before the work ran
    assert accepted["score"] is None

    scan = client.get(f"/api/v1/scans/{accepted['id']}", headers=headers).json()
    assert scan["status"] == "completed"  # background task already ran
    assert scan["score"] == 1
    assert scan["commit_sha"] == "e" * 40
    assert scan["error_message"] is None
    assert scan["started_at"] and scan["completed_at"]
    check_ids = {f["check_id"] for f in scan["findings"]}
    assert check_ids == {
        "missing_readme",
        "missing_license",
        "missing_gitignore",
        "missing_dependency_manifest",
        "missing_tests",
        "missing_ci",
        "missing_dockerfile",
    }
    for finding in scan["findings"]:
        assert finding["severity"] in {"critical", "high", "medium", "low"}
        assert finding["recommendation"]
    critical = sum(1 for f in scan["findings"] if f["severity"] == "critical")

    # The clone was deleted after the scan.
    assert len(e2e_env["clones"]) == 1
    assert not e2e_env["clones"][0].exists()
    assert list(e2e_env["workdir"].iterdir()) == []

    detail = client.get(f"/api/v1/projects/{project['id']}", headers=headers).json()
    assert detail["latest_score"] == 1
    assert detail["primary_language"] == "Python"
    assert detail["latest_scan"]["id"] == accepted["id"]

    summary = client.get("/api/v1/analytics/summary", headers=headers).json()
    assert summary == {
        "project_count": 1,
        "scan_count": 1,
        "avg_latest_score": 1.0,
        "open_critical_findings": critical,
    }
    common = client.get("/api/v1/analytics/common-findings", headers=headers).json()
    assert len(common) == 5 and all(c["count"] == 1 for c in common)

    # --- rescan: "complete" fixture ---------------------------------------------------
    e2e_env["fixture"] = "complete"
    second = _start_scan(client, headers, project["id"])
    assert second["id"] != accepted["id"]
    scan2 = client.get(f"/api/v1/scans/{second['id']}", headers=headers).json()
    assert scan2["status"] == "completed"
    assert scan2["score"] == 100
    assert scan2["findings"] == []

    detail = client.get(f"/api/v1/projects/{project['id']}", headers=headers).json()
    assert detail["latest_score"] == 100
    assert detail["latest_scan"]["id"] == second["id"]

    history = client.get(f"/api/v1/projects/{project['id']}/scans", headers=headers).json()
    assert [s["id"] for s in history] == [second["id"], accepted["id"]]  # newest first

    trend = client.get("/api/v1/analytics/score-trend", headers=headers).json()
    assert len(trend) == 1
    assert trend[0]["project_id"] == project["id"]
    assert [p["score"] for p in trend[0]["points"]] == [1, 100]

    summary = client.get("/api/v1/analytics/summary", headers=headers).json()
    assert summary["scan_count"] == 2
    assert summary["avg_latest_score"] == 100.0
    assert summary["open_critical_findings"] == 0
    assert client.get("/api/v1/analytics/common-findings", headers=headers).json() == []

    assert all(not p.exists() for p in e2e_env["clones"])


def test_flow_failed_clone_then_retry(
    client: TestClient, e2e_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing clone yields status=failed with a readable message; a retry is allowed."""
    headers = _register(client)
    project = client.post(
        "/api/v1/projects", json={"name": "x", "repo_url": REPO_URL}, headers=headers
    ).json()

    def _private(url: str, branch: str | None, dest: Path) -> cloner.CloneResult:
        dest.mkdir(parents=True)
        (dest / "partial").write_text("x")
        raise cloner.CloneError("Repository not found or is private")

    monkeypatch.setattr(cloner, "clone_repo", _private)
    first = _start_scan(client, headers, project["id"])
    failed = client.get(f"/api/v1/scans/{first['id']}", headers=headers).json()
    assert failed["status"] == "failed"
    assert failed["error_message"] == "Repository not found or is private"
    assert failed["score"] is None
    assert list(e2e_env["workdir"].iterdir()) == []

    detail = client.get(f"/api/v1/projects/{project['id']}", headers=headers).json()
    assert detail["latest_score"] is None

    # Not active any more -> a new scan is accepted (not 409).
    e2e_env["fixture"] = "complete"
    monkeypatch.setattr(cloner, "clone_repo", e2e_env["clone"])
    second = _start_scan(client, headers, project["id"])
    done = client.get(f"/api/v1/scans/{second['id']}", headers=headers).json()
    assert done["status"] == "completed" and done["score"] == 100


def test_flow_conflict_while_scan_active(
    client: TestClient, e2e_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the background task suppressed the scan stays queued -> second POST is 409."""
    headers = _register(client)
    project = client.post(
        "/api/v1/projects", json={"name": "x", "repo_url": REPO_URL}, headers=headers
    ).json()
    monkeypatch.setattr(scan_service, "run_scan", lambda scan_id: None)
    _start_scan(client, headers, project["id"])
    again = client.post(f"/api/v1/projects/{project['id']}/scans", headers=headers)
    assert again.status_code == 409


def test_flow_other_user_isolation(
    client: TestClient,
    e2e_env: dict,
    user_factory: Callable,
    auth_headers: Callable,
) -> None:
    headers = _register(client)
    project = client.post(
        "/api/v1/projects", json={"name": "x", "repo_url": REPO_URL}, headers=headers
    ).json()
    scan = _start_scan(client, headers, project["id"])
    intruder = auth_headers(user_factory())
    pid, sid = project["id"], scan["id"]
    assert client.get(f"/api/v1/projects/{pid}", headers=intruder).status_code == 404
    assert client.post(f"/api/v1/projects/{pid}/scans", headers=intruder).status_code == 404
    assert client.get(f"/api/v1/scans/{sid}", headers=intruder).status_code == 404
    assert client.delete(f"/api/v1/projects/{pid}", headers=intruder).status_code == 404
    summary = client.get("/api/v1/analytics/summary", headers=intruder).json()
    assert summary["project_count"] == 0 and summary["scan_count"] == 0
