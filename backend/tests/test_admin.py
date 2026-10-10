"""Tests for the admin endpoints (/api/v1/admin/*) and the make-admin CLI."""

import contextlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import cli
from app.models.project import Project
from app.models.scan import Scan, ScanStatus
from app.models.user import User

BASE = "/api/v1/admin"
Headers = Callable[[User], dict[str, str]]


def make_project(db: Session, owner: User, name: str) -> Project:
    project = Project(user_id=owner.id, name=name, repo_url=f"https://github.com/acme/{name}")
    db.add(project)
    db.flush()
    return project


def make_scan(
    db: Session,
    project: Project,
    status: ScanStatus,
    created_at: datetime | None = None,
) -> Scan:
    scan = Scan(project_id=project.id, status=status)
    if created_at is not None:
        scan.created_at = created_at
    db.add(scan)
    db.flush()
    return scan


# --- access control -------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/users"), ("put", "/users/1"), ("get", "/stats"), ("get", "/scans")],
)
def test_admin_endpoints_forbidden_for_non_admin(
    client: TestClient, user: User, auth_headers: Headers, method: str, path: str
) -> None:
    kwargs: dict[str, object] = {"headers": auth_headers(user)}
    if method == "put":
        kwargs["json"] = {"is_active": False}
    resp = getattr(client, method)(BASE + path, **kwargs)
    assert resp.status_code == 403


def test_admin_endpoints_require_auth(client: TestClient) -> None:
    assert client.get(f"{BASE}/stats").status_code == 401


# --- users ----------------------------------------------------------------


def test_list_users_paginated_newest_first(
    client: TestClient,
    admin_user: User,
    user_factory: Callable[..., User],
    auth_headers: Headers,
) -> None:
    created = [user_factory() for _ in range(3)]
    resp = client.get(f"{BASE}/users?page=1&size=2", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4
    assert body["page"] == 1 and body["size"] == 2
    assert [u["id"] for u in body["items"]] == [created[2].id, created[1].id]
    assert set(body["items"][0]) == {
        "id",
        "email",
        "full_name",
        "is_active",
        "is_verified",
        "is_admin",
        "oauth_provider",
        "avatar_url",
        "created_at",
    }

    resp = client.get(f"{BASE}/users?page=2&size=2", headers=auth_headers(admin_user))
    assert [u["id"] for u in resp.json()["items"]] == [created[0].id, admin_user.id]


def test_list_users_search(
    client: TestClient,
    admin_user: User,
    user_factory: Callable[..., User],
    auth_headers: Headers,
) -> None:
    alice = user_factory(email="alice@corp.io", full_name="Alice Smith")
    bob = user_factory(email="bob@example.com", full_name="Bob SMITHERS")
    user_factory(email="carol@example.com", full_name="Carol")

    resp = client.get(f"{BASE}/users?q=smith", headers=auth_headers(admin_user))
    body = resp.json()
    assert body["total"] == 2
    assert {u["id"] for u in body["items"]} == {alice.id, bob.id}

    resp = client.get(f"{BASE}/users?q=CORP.IO", headers=auth_headers(admin_user))
    assert [u["id"] for u in resp.json()["items"]] == [alice.id]


def test_update_user_flags(
    client: TestClient,
    db: Session,
    admin_user: User,
    user: User,
    auth_headers: Headers,
) -> None:
    resp = client.put(
        f"{BASE}/users/{user.id}", json={"is_admin": True}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is True
    assert resp.json()["is_active"] is True

    resp = client.put(
        f"{BASE}/users/{user.id}", json={"is_active": False}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    db.refresh(user)
    assert user.is_active is False and user.is_admin is True


def test_update_self_is_rejected(
    client: TestClient, admin_user: User, auth_headers: Headers
) -> None:
    resp = client.put(
        f"{BASE}/users/{admin_user.id}", json={"is_active": False}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_update_unknown_user_404(
    client: TestClient, admin_user: User, auth_headers: Headers
) -> None:
    resp = client.put(
        f"{BASE}/users/999999", json={"is_active": False}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 404


# --- stats ----------------------------------------------------------------


def test_stats_empty_failure_rate_zero(
    client: TestClient, admin_user: User, auth_headers: Headers
) -> None:
    resp = client.get(f"{BASE}/stats", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    assert resp.json() == {
        "user_count": 1,
        "project_count": 0,
        "scan_count": 0,
        "scans_last_24h": 0,
        "failure_rate": 0.0,
    }


def test_stats_counts(
    client: TestClient,
    db: Session,
    admin_user: User,
    user: User,
    auth_headers: Headers,
) -> None:
    p1 = make_project(db, user, "one")
    p2 = make_project(db, admin_user, "two")
    old = datetime.now(UTC) - timedelta(days=2)
    make_scan(db, p1, ScanStatus.completed, created_at=old)
    make_scan(db, p1, ScanStatus.completed, created_at=old)
    make_scan(db, p1, ScanStatus.completed)
    make_scan(db, p2, ScanStatus.failed)
    make_scan(db, p2, ScanStatus.queued)
    make_scan(db, p2, ScanStatus.running)
    db.commit()

    resp = client.get(f"{BASE}/stats", headers=auth_headers(admin_user))
    assert resp.json() == {
        "user_count": 2,
        "project_count": 2,
        "scan_count": 6,
        "scans_last_24h": 4,
        "failure_rate": 0.25,
    }


# --- scans ----------------------------------------------------------------


def test_list_scans_all_users_with_filter(
    client: TestClient,
    db: Session,
    admin_user: User,
    user_factory: Callable[..., User],
    auth_headers: Headers,
) -> None:
    u1 = user_factory(email="one@example.com")
    u2 = user_factory(email="two@example.com")
    p1 = make_project(db, u1, "repo-one")
    p2 = make_project(db, u2, "repo-two")
    now = datetime.now(UTC)
    s_old = make_scan(db, p1, ScanStatus.completed, created_at=now - timedelta(hours=3))
    s_mid = make_scan(db, p2, ScanStatus.failed, created_at=now - timedelta(hours=2))
    s_new = make_scan(db, p1, ScanStatus.completed, created_at=now - timedelta(hours=1))
    db.commit()

    resp = client.get(f"{BASE}/scans", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert [s["id"] for s in body["items"]] == [s_new.id, s_mid.id, s_old.id]
    item = body["items"][1]
    assert item["project_name"] == "repo-two"
    assert item["user_email"] == "two@example.com"
    assert item["status"] == "failed"
    assert set(item) == {
        "id",
        "project_id",
        "status",
        "score",
        "commit_sha",
        "error_message",
        "started_at",
        "completed_at",
        "created_at",
        "project_name",
        "user_email",
    }

    resp = client.get(f"{BASE}/scans?status=completed&size=1", headers=auth_headers(admin_user))
    body = resp.json()
    assert body["total"] == 2
    assert [s["id"] for s in body["items"]] == [s_new.id]

    resp = client.get(f"{BASE}/scans?status=bogus", headers=auth_headers(admin_user))
    assert resp.status_code == 422


# --- CLI ------------------------------------------------------------------


@pytest.fixture
def cli_db(db: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """Point the CLI's SessionLocal at the per-test session."""
    monkeypatch.setattr(cli, "SessionLocal", lambda: contextlib.nullcontext(db))
    return db


def test_cli_make_admin(cli_db: Session, user_factory: Callable[..., User]) -> None:
    target = user_factory(email="promote@example.com")
    assert cli.main(["make-admin", "Promote@Example.com"]) == 0
    cli_db.refresh(target)
    assert target.is_admin is True


def test_cli_make_admin_unknown_user(cli_db: Session) -> None:
    assert cli.main(["make-admin", "nobody@example.com"]) == 1
