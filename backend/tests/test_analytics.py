"""Tests for the analytics endpoints (/api/v1/analytics/*)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.finding import Finding, FindingCategory, Severity
from app.models.project import Project
from app.models.scan import Scan, ScanStatus
from app.models.user import User

BASE = "/api/v1/analytics"
NOW = datetime.now(UTC)


def make_project(
    db: Session, user: User, name: str = "proj", latest_score: int | None = None
) -> Project:
    project = Project(
        user_id=user.id,
        name=name,
        repo_url=f"https://github.com/acme/{name}",
        latest_score=latest_score,
    )
    db.add(project)
    db.flush()
    return project


def make_scan(
    db: Session,
    project: Project,
    status: ScanStatus = ScanStatus.completed,
    score: int | None = 50,
    completed_at: datetime | None = None,
    findings: list[tuple[str, Severity]] | None = None,
) -> Scan:
    if status == ScanStatus.completed and completed_at is None:
        completed_at = NOW
    scan = Scan(project_id=project.id, status=status, score=score, completed_at=completed_at)
    db.add(scan)
    db.flush()
    for check_id, severity in findings or []:
        db.add(
            Finding(
                scan_id=scan.id,
                check_id=check_id,
                category=FindingCategory.documentation,
                severity=severity,
                title=f"Title {check_id}",
                recommendation="Fix it",
            )
        )
    db.flush()
    return scan


# --- auth -----------------------------------------------------------------


def test_analytics_requires_auth(client: TestClient) -> None:
    for path in ("/summary", "/score-trend", "/common-findings"):
        assert client.get(BASE + path).status_code == 401


# --- summary --------------------------------------------------------------


def test_summary_empty(
    client: TestClient, user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    resp = client.get(f"{BASE}/summary", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json() == {
        "project_count": 0,
        "scan_count": 0,
        "avg_latest_score": None,
        "open_critical_findings": 0,
    }


def test_summary_math_and_latest_scan_selection(
    client: TestClient,
    db: Session,
    user: User,
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    p1 = make_project(db, user, "a", latest_score=80)
    p2 = make_project(db, user, "b", latest_score=65)
    make_project(db, user, "c", latest_score=None)  # excluded from the average

    # p1: older completed scan with 3 criticals, latest completed with 1 critical,
    # plus a newer failed and a queued scan that must be ignored.
    make_scan(
        db,
        p1,
        completed_at=NOW - timedelta(days=5),
        findings=[("x", Severity.critical)] * 3,
    )
    make_scan(
        db,
        p1,
        completed_at=NOW - timedelta(days=1),
        findings=[("x", Severity.critical), ("y", Severity.high)],
    )
    make_scan(db, p1, status=ScanStatus.failed, score=None, completed_at=NOW)
    make_scan(db, p1, status=ScanStatus.queued, score=None)
    # p2: latest completed has 2 criticals.
    make_scan(
        db,
        p2,
        completed_at=NOW - timedelta(hours=2),
        findings=[("x", Severity.critical), ("z", Severity.critical)],
    )

    # Another user's data must not leak in.
    other = user_factory()
    po = make_project(db, other, "o", latest_score=10)
    make_scan(db, po, findings=[("x", Severity.critical)])
    db.commit()

    resp = client.get(f"{BASE}/summary", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json() == {
        "project_count": 3,
        "scan_count": 5,
        "avg_latest_score": 72.5,
        "open_critical_findings": 3,
    }


def test_summary_avg_rounded_to_one_decimal(
    client: TestClient, db: Session, user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    for i, score in enumerate((70, 70, 71)):
        make_project(db, user, f"p{i}", latest_score=score)
    db.commit()
    resp = client.get(f"{BASE}/summary", headers=auth_headers(user))
    assert resp.json()["avg_latest_score"] == 70.3


# --- score trend ----------------------------------------------------------


def test_score_trend_points_window_and_scoping(
    client: TestClient,
    db: Session,
    user: User,
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    pa = make_project(db, user, "alpha")
    pb = make_project(db, user, "beta")
    pc = make_project(db, user, "gamma")  # only an out-of-window scan -> omitted
    make_project(db, user, "delta")  # no scans -> omitted

    t1 = NOW - timedelta(days=10)
    t2 = NOW - timedelta(days=3)
    make_scan(db, pa, score=70, completed_at=t2)  # inserted out of order
    make_scan(db, pa, score=50, completed_at=t1)
    make_scan(db, pa, status=ScanStatus.failed, score=None, completed_at=NOW)
    make_scan(db, pb, score=90, completed_at=NOW - timedelta(days=1))
    make_scan(db, pc, score=40, completed_at=NOW - timedelta(days=60))

    other = user_factory()
    make_scan(db, make_project(db, other, "alpha"), score=10)
    db.commit()

    resp = client.get(f"{BASE}/score-trend", headers=auth_headers(user))
    assert resp.status_code == 200
    data = resp.json()
    assert [s["name"] for s in data] == ["alpha", "beta"]
    assert data[0]["project_id"] == pa.id
    assert data[0]["points"] == [
        {"date": t1.date().isoformat(), "score": 50},
        {"date": t2.date().isoformat(), "score": 70},
    ]
    assert data[1]["points"] == [
        {"date": (NOW - timedelta(days=1)).date().isoformat(), "score": 90}
    ]

    # A 5-day window drops alpha's older point.
    resp = client.get(f"{BASE}/score-trend?days=5", headers=auth_headers(user))
    alpha = resp.json()[0]
    assert alpha["points"] == [{"date": t2.date().isoformat(), "score": 70}]

    # A 365-day window includes gamma.
    resp = client.get(f"{BASE}/score-trend?days=365", headers=auth_headers(user))
    assert [s["name"] for s in resp.json()] == ["alpha", "beta", "gamma"]


def test_score_trend_validates_days(
    client: TestClient, user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    headers = auth_headers(user)
    assert client.get(f"{BASE}/score-trend?days=0", headers=headers).status_code == 422
    assert client.get(f"{BASE}/score-trend?days=366", headers=headers).status_code == 422


# --- common findings ------------------------------------------------------


def test_common_findings_counts_latest_scans_only(
    client: TestClient,
    db: Session,
    user: User,
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    p1 = make_project(db, user, "one")
    p2 = make_project(db, user, "two")
    p3 = make_project(db, user, "three")

    # Older scan of p1 is ignored entirely.
    make_scan(
        db,
        p1,
        completed_at=NOW - timedelta(days=2),
        findings=[("old_only", Severity.critical)] * 4,
    )
    make_scan(
        db,
        p1,
        completed_at=NOW - timedelta(hours=1),
        findings=[("readme", Severity.high), ("tests", Severity.critical), ("ci", Severity.low)],
    )
    make_scan(
        db,
        p2,
        findings=[
            ("readme", Severity.high),
            ("tests", Severity.critical),
            ("env", Severity.medium),
        ],
    )
    make_scan(db, p3, findings=[("readme", Severity.high), ("ci", Severity.low)])
    # Newer failed scan with findings on p3 is ignored.
    make_scan(
        db,
        p3,
        status=ScanStatus.failed,
        score=None,
        completed_at=NOW + timedelta(minutes=1),
        findings=[("bogus", Severity.critical)],
    )

    other = user_factory()
    make_scan(db, make_project(db, other, "x"), findings=[("env", Severity.medium)] * 5)
    db.commit()

    resp = client.get(f"{BASE}/common-findings", headers=auth_headers(user))
    assert resp.status_code == 200
    data = resp.json()
    # readme 3; tests 2 (critical) before ci 2 (low); env 1.
    assert [(d["check_id"], d["count"]) for d in data] == [
        ("readme", 3),
        ("tests", 2),
        ("ci", 2),
        ("env", 1),
    ]
    assert data[0] == {
        "check_id": "readme",
        "title": "Title readme",
        "severity": "high",
        "count": 3,
    }

    resp = client.get(f"{BASE}/common-findings?limit=2", headers=auth_headers(user))
    assert [d["check_id"] for d in resp.json()] == ["readme", "tests"]


def test_common_findings_validates_limit(
    client: TestClient, user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    headers = auth_headers(user)
    assert client.get(f"{BASE}/common-findings?limit=0", headers=headers).status_code == 422
    assert client.get(f"{BASE}/common-findings?limit=21", headers=headers).status_code == 422
    assert client.get(f"{BASE}/common-findings", headers=headers).json() == []
