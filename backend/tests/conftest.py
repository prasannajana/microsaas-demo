"""Shared pytest fixtures (real PostgreSQL, per-test transactional isolation).

Database:
    Uses ``TEST_DATABASE_URL`` (default ``postgresql://test:test@localhost:5433/test_db``;
    start it with ``scripts/test-db.sh start``). ``DATABASE_URL`` is pointed at the same
    database before the app is imported. All tables are dropped and re-created once per
    session; each test runs inside an outer connection-level transaction that is rolled
    back afterwards (``join_transaction_mode="create_savepoint"``), so ``db.commit()``
    in app code only releases a SAVEPOINT and nothing leaks between tests.

Scanner isolation (autouse):
    ``scan_service`` uses an inline executor, so a scan handed off by the POST endpoint's
    background task has finished before ``client.post`` returns (deterministic tests).
    ``github_api.fetch_repo_metadata`` is replaced by a fake returning public, small
    metadata — tests never touch the network. Tests of the real function use
    ``REAL_FETCH_REPO_METADATA`` with an ``httpx.MockTransport``.

Rate limiting:
    The shared slowapi ``limiter`` is disabled for every test (autouse fixture).
    Request the ``enable_rate_limit`` fixture to turn it on (storage is reset).

Fixtures (names are stable — other test modules depend on them):
    db -> sqlalchemy.orm.Session
        Session bound to the per-test transaction.
    client -> fastapi.testclient.TestClient
        App client with ``get_db`` overridden to yield ``db``.
    user_factory -> Callable[..., User]
        ``user_factory(email=None, password="password123", full_name="Test User",
        is_active=True, is_admin=False, is_verified=False, **fields) -> User``.
        Email defaults to a unique ``user<N>@example.com``. Pass ``password=None``
        for an OAuth-only user.
    user -> User
        A regular active user created with ``user_factory()`` (password "password123").
    admin_user -> User
        An active admin user (password "password123").
    auth_headers -> Callable[[User], dict[str, str]]
        ``auth_headers(user)`` returns ``{"Authorization": "Bearer <access token>"}``.
    enable_rate_limit -> None
        Opt-in: enables the slowapi limiter for the test.
"""

import itertools
import os
import uuid
from collections.abc import Callable, Generator, Iterator
from concurrent.futures import Executor, Future
from functools import lru_cache
from typing import Any

import pytest

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://test:test@localhost:5433/test_db"
)
TEST_SCHEMA = f"test_{uuid.uuid4().hex[:12]}"
_SEP = "&" if "?" in TEST_DATABASE_URL else "?"
SCHEMA_DATABASE_URL = f"{TEST_DATABASE_URL}{_SEP}options=-csearch_path%3D{TEST_SCHEMA}"
os.environ["DATABASE_URL"] = SCHEMA_DATABASE_URL
os.environ.setdefault("ENV", "test")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402,F401 - register all tables on Base.metadata
from app.auth.jwt import create_access_token  # noqa: E402
from app.auth.passwords import hash_password  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.database import engine as app_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402
from app.rate_limit import limiter  # noqa: E402
from app.scanner import github_api  # noqa: E402
from app.services import scan_service  # noqa: E402

REAL_FETCH_REPO_METADATA = github_api.fetch_repo_metadata

DEFAULT_PASSWORD = "password123"
_email_counter = itertools.count(1)


@lru_cache(maxsize=32)
def _cached_hash(password: str) -> str:
    """bcrypt is slow; hash each distinct test password only once per session."""
    return hash_password(password)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Session-wide engine bound to a private, freshly created schema."""
    admin = create_engine(TEST_DATABASE_URL)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{TEST_SCHEMA}"'))
    eng = create_engine(SCHEMA_DATABASE_URL, pool_pre_ping=True)
    try:
        Base.metadata.create_all(eng)
        yield eng
    finally:
        eng.dispose()
        app_engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE'))
        admin.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A Session wrapped in a transaction that is rolled back after the test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


class InlineExecutor(Executor):
    """Executor that runs submitted callables synchronously (deterministic tests)."""

    def __init__(self) -> None:
        self.submitted: list[tuple[Any, tuple[Any, ...]]] = []

    def submit(self, fn: Any, /, *args: Any, **kwargs: Any) -> Future[Any]:
        self.submitted.append((fn, args))
        future: Future[Any] = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # pragma: no cover - run_scan never raises
            future.set_exception(exc)
        return future


@pytest.fixture(autouse=True)
def inline_executor(monkeypatch: pytest.MonkeyPatch) -> InlineExecutor:
    """Run scans submitted to the scan executor synchronously."""
    executor = InlineExecutor()
    monkeypatch.setattr(scan_service, "_executor", executor)
    return executor


def fake_metadata(
    owner: str = "octocat",
    repo: str = "Hello-World",
    *,
    private: bool = False,
    size_kb: int = 10,
    default_branch: str | None = "main",
) -> github_api.RepoMetadata:
    """Build RepoMetadata for tests."""
    return github_api.RepoMetadata(
        full_name=f"{owner}/{repo}", private=private, size_kb=size_kb, default_branch=default_branch
    )


@pytest.fixture(autouse=True)
def github_metadata(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Fake the pre-clone GitHub API lookup (public, 10 KB, default branch "main")."""
    calls: list[tuple[str, str]] = []

    def _fake(owner: str, repo: str, **_kw: Any) -> github_api.RepoMetadata:
        calls.append((owner, repo))
        return fake_metadata(owner, repo)

    monkeypatch.setattr(github_api, "fetch_repo_metadata", _fake)
    return calls


@pytest.fixture(autouse=True)
def _disable_rate_limit() -> Iterator[None]:
    """Disable slowapi rate limiting for every test by default."""
    previous = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = previous


@pytest.fixture
def enable_rate_limit() -> Iterator[None]:
    """Enable the slowapi limiter (with fresh counters) for a single test."""
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """TestClient whose ``get_db`` dependency yields the per-test ``db`` session."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def user_factory(db: Session) -> Callable[..., User]:
    """Factory creating and persisting users (see module docstring for the signature)."""

    def _create(
        email: str | None = None,
        password: str | None = DEFAULT_PASSWORD,
        full_name: str | None = "Test User",
        is_active: bool = True,
        is_admin: bool = False,
        is_verified: bool = False,
        **fields: Any,
    ) -> User:
        user = User(
            email=(email or f"user{next(_email_counter)}@example.com").lower(),
            hashed_password=_cached_hash(password) if password else None,
            full_name=full_name,
            is_active=is_active,
            is_admin=is_admin,
            is_verified=is_verified,
            **fields,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _create


@pytest.fixture
def user(user_factory: Callable[..., User]) -> User:
    """A regular active user (password ``password123``)."""
    return user_factory()


@pytest.fixture
def admin_user(user_factory: Callable[..., User]) -> User:
    """An active admin user (password ``password123``)."""
    return user_factory(is_admin=True, full_name="Admin User")


@pytest.fixture
def auth_headers() -> Callable[[User], dict[str, str]]:
    """Return a function building Bearer auth headers for a given user."""

    def _headers(user: User) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return _headers
