"""Security regression tests for the auth module (findings M1, M6, M7, L6, L7, L9, deps).

* M1  - Google linking to an unverified account drops its password and sessions.
* M6  - /auth/refresh has its own, looser rate limit; register/login stay at 5/minute.
* M7  - Refresh tokens are stored hashed, rotated under a row lock, and reuse of a
        revoked token revokes the whole token family.
* L6  - The Google callback is a sync endpoint (runs in the threadpool).
* L7  - Login-CSRF nonce is validated, bound to the state cookie and echoed back.
* L9  - Passwords are limited to 72 UTF-8 bytes.
* JWT - PyJWT decoding pins HS256 and requires exp/type.
"""

import hashlib
import inspect
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth import google
from app.auth.google import GoogleUserInfo
from app.auth.jwt import JWT_ALGORITHM, create_refresh_token, decode_token
from app.auth.passwords import hash_password
from app.config import settings
from app.exceptions import UnauthorizedError
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.rate_limit import AUTH_RATE_LIMIT, REFRESH_RATE_LIMIT
from app.routers import auth as auth_router
from app.services import auth_service
from app.services.auth_service import hash_refresh_token

API = "/api/v1/auth"
UserFactory = Callable[..., User]
NONCE = "n0nce_-ABCDEFGHIJKLMNOP"


def _fragment(location: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(location).fragment).items()}


def _login(
    client: TestClient,
    email: str,
    password: str = "password123",  # noqa: S107 - test fixture password
) -> dict[str, str]:
    resp = client.post(f"{API}/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    data: dict[str, str] = resp.json()
    return data


def _refresh(client: TestClient, token: str) -> int:
    return client.post(f"{API}/refresh", json={"refresh_token": token}).status_code


@pytest.fixture
def google_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://frontend.test")


def _mock_google(monkeypatch: pytest.MonkeyPatch, info: GoogleUserInfo) -> None:
    monkeypatch.setattr(google, "exchange_code", lambda code: "google-access-token")
    monkeypatch.setattr(google, "fetch_userinfo", lambda token: info)


def _google_flow(client: TestClient, nonce: str | None = None, **params: str) -> dict[str, str]:
    start = client.get(
        f"{API}/google", params={"nonce": nonce} if nonce else {}, follow_redirects=False
    )
    assert start.status_code == 302
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    query = {"code": "c", "state": state, **params}
    resp = client.get(f"{API}/google/callback", params=query, follow_redirects=False)
    assert resp.status_code == 302
    return _fragment(resp.headers["location"])


# --------------------------------------------------------------------------- M1 pre-hijack


@pytest.mark.usefixtures("google_configured")
def test_google_link_unverified_account_drops_password_and_sessions(
    client: TestClient, db: Session, user_factory: UserFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Attacker pre-registers the victim's email (never verified) and keeps a session.
    squatter = user_factory(email="victim@example.com", is_verified=False)
    attacker_tokens = _login(client, squatter.email)

    # Victim signs in with Google for the first time.
    _mock_google(
        monkeypatch, GoogleUserInfo(sub="g-victim", email=squatter.email, email_verified=True)
    )
    frag = _google_flow(client)
    assert "access_token" in frag

    db.refresh(squatter)
    assert squatter.google_id == "g-victim"
    assert squatter.is_verified is True
    assert squatter.hashed_password is None
    # The attacker's password and refresh token no longer work ...
    bad_login = client.post(
        f"{API}/login", json={"email": squatter.email, "password": "password123"}
    )
    assert bad_login.status_code == 401
    assert _refresh(client, attacker_tokens["refresh_token"]) == 401
    # ... but the victim's fresh Google session does.
    assert _refresh(client, frag["refresh_token"]) == 200


def test_upsert_google_unverified_link_revokes_all_tokens(
    db: Session, user_factory: UserFactory
) -> None:
    u = user_factory(email="pre@example.com", is_verified=False)
    pairs = [auth_service.issue_tokens(db, u) for _ in range(2)]
    other = auth_service.issue_tokens(db, user_factory())
    auth_service.upsert_google_user(
        db, GoogleUserInfo(sub="g-pre", email=u.email, email_verified=True)
    )
    db.commit()
    # Squatter sessions are deleted (not just flagged) so a replay is merely "unknown".
    assert db.scalars(select(RefreshToken).where(RefreshToken.user_id == u.id)).all() == []
    assert u.hashed_password is None
    for pair in pairs:
        with pytest.raises(UnauthorizedError):
            auth_service.refresh(db, pair.refresh_token)
    assert auth_service.refresh(db, other.refresh_token).access_token  # other users untouched


def test_upsert_google_verified_link_keeps_password_and_sessions(
    db: Session, user_factory: UserFactory
) -> None:
    u = user_factory(email="ok@example.com", is_verified=True)
    pair = auth_service.issue_tokens(db, u)
    auth_service.upsert_google_user(
        db, GoogleUserInfo(sub="g-ok", email=u.email, email_verified=True)
    )
    db.commit()
    assert u.hashed_password is not None
    assert auth_service.refresh(db, pair.refresh_token).access_token


def test_upsert_google_existing_google_user_is_not_wiped(
    db: Session, user_factory: UserFactory
) -> None:
    """Matching by google_id is a returning user, not a link: sessions survive."""
    u = user_factory(email="ret@example.com", password=None, google_id="g-ret")
    pair = auth_service.issue_tokens(db, u)
    auth_service.upsert_google_user(
        db, GoogleUserInfo(sub="g-ret", email=u.email, email_verified=True)
    )
    db.commit()
    assert auth_service.refresh(db, pair.refresh_token).access_token


# --------------------------------------------------------------------------- M6 rate limits


def test_rate_limit_values() -> None:
    assert AUTH_RATE_LIMIT == "5/minute"
    assert REFRESH_RATE_LIMIT == "30/minute"


@pytest.mark.usefixtures("enable_rate_limit")
def test_refresh_has_separate_looser_limit(client: TestClient) -> None:
    statuses = [_refresh(client, "garbage") for _ in range(31)]
    assert statuses[:30] == [401] * 30
    assert statuses[30] == 429
    # The refresh bucket is independent of the login bucket.
    login = client.post(f"{API}/login", json={"email": "x@example.com", "password": "nope"})
    assert login.status_code == 401


@pytest.mark.usefixtures("enable_rate_limit")
def test_register_still_limited_to_five_per_minute(client: TestClient) -> None:
    statuses = [
        client.post(
            f"{API}/register", json={"email": f"rl{i}@example.com", "password": "password123"}
        ).status_code
        for i in range(6)
    ]
    assert statuses == [201] * 5 + [429]


# --------------------------------------------------------------------------- M7 refresh tokens


def test_refresh_token_stored_as_sha256_hash(client: TestClient, db: Session, user: User) -> None:
    tokens = _login(client, user.email)
    row = db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)).one()
    assert row.token != tokens["refresh_token"]
    assert row.token == hashlib.sha256(tokens["refresh_token"].encode()).hexdigest()
    assert len(row.token) == 64
    raw = db.scalars(
        select(RefreshToken).where(RefreshToken.token == tokens["refresh_token"])
    ).first()
    assert raw is None


def test_raw_token_in_db_is_not_accepted(db: Session, user: User) -> None:
    """A legacy/leaked row holding the raw JWT can't be used (lookups hash the input)."""
    token, expires = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token=token, expires_at=expires))
    db.commit()
    with pytest.raises(UnauthorizedError):
        auth_service.refresh(db, token)


def test_double_refresh_second_use_fails_and_revokes_family(
    client: TestClient, db: Session, user: User
) -> None:
    tokens = _login(client, user.email)
    first = client.post(f"{API}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    # Second (racing) use of the same token: rejected ...
    assert _refresh(client, tokens["refresh_token"]) == 401
    # ... and the token issued to the first caller is revoked too.
    assert _refresh(client, first.json()["refresh_token"]) == 401
    rows = db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)).all()
    for row in rows:
        db.refresh(row)
    assert rows and all(r.revoked for r in rows)


def test_reuse_detection_revokes_all_user_sessions(
    client: TestClient, user_factory: UserFactory
) -> None:
    victim, bystander = user_factory(), user_factory()
    session_a = _login(client, victim.email)
    session_b = _login(client, victim.email)  # e.g. another device
    other = _login(client, bystander.email)
    stolen = session_a["refresh_token"]
    assert _refresh(client, stolen) == 200  # legitimate rotation
    assert _refresh(client, stolen) == 401  # replay -> reuse detected
    assert _refresh(client, session_b["refresh_token"]) == 401
    assert _refresh(client, other["refresh_token"]) == 200  # other users unaffected


def test_refresh_uses_select_for_update(db: Session, user: User) -> None:
    pair = auth_service.issue_tokens(db, user)
    statements: list[str] = []
    real_scalars = db.scalars

    def _spy(stmt: Any, *args: Any, **kwargs: Any) -> Any:
        statements.append(str(stmt.compile(dialect=db.get_bind().dialect)))
        return real_scalars(stmt, *args, **kwargs)

    db.scalars = _spy  # type: ignore[method-assign]
    try:
        auth_service.refresh(db, pair.refresh_token)
    finally:
        del db.scalars
    assert any("FOR UPDATE" in s for s in statements)


def test_concurrent_refresh_only_one_succeeds(engine: Engine) -> None:
    """Two real connections race the same token: the row lock lets exactly one win."""
    with Session(engine) as setup:
        u = User(email="race@example.com", hashed_password=hash_password("password123"))
        setup.add(u)
        setup.commit()
        user_id = u.id
        token = auth_service.issue_tokens(setup, u).refresh_token
    barrier = threading.Barrier(2)
    results: list[str] = []
    lock = threading.Lock()

    def _worker() -> None:
        with Session(engine) as s:
            barrier.wait()
            try:
                auth_service.refresh(s, token)
                outcome = "ok"
            except UnauthorizedError:
                outcome = "401"
            with lock:
                results.append(outcome)

    try:
        threads = [threading.Thread(target=_worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert sorted(results) == ["401", "ok"]
        with Session(engine) as check:
            rows = check.scalars(select(RefreshToken).where(RefreshToken.user_id == user_id))
            assert all(r.revoked for r in rows)  # loser triggered family revocation
    finally:
        with Session(engine) as cleanup:
            cleanup.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
            cleanup.execute(delete(User).where(User.id == user_id))
            cleanup.commit()


def test_login_deletes_expired_refresh_rows(client: TestClient, db: Session, user: User) -> None:
    token, _ = create_refresh_token(user.id)
    expired = RefreshToken(
        user_id=user.id,
        token=hash_refresh_token(token),
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db.add(expired)
    db.commit()
    expired_id = expired.id
    _login(client, user.email)
    db.expire_all()
    assert db.get(RefreshToken, expired_id) is None
    assert db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)).one()


def test_logout_matches_hashed_token(client: TestClient, db: Session, user: User) -> None:
    tokens = _login(client, user.email)
    resp = client.post(f"{API}/logout", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 204
    row = db.scalars(
        select(RefreshToken).where(
            RefreshToken.token == hash_refresh_token(tokens["refresh_token"])
        )
    ).one()
    db.refresh(row)
    assert row.revoked is True


# --------------------------------------------------------------------------- L6 sync callback


def test_google_callback_runs_in_threadpool() -> None:
    assert not inspect.iscoroutinefunction(auth_router.google_callback)
    assert not inspect.iscoroutinefunction(google.exchange_code)
    assert not inspect.iscoroutinefunction(google.fetch_userinfo)


# --------------------------------------------------------------------------- L7 OAuth nonce


@pytest.mark.usefixtures("google_configured")
@pytest.mark.parametrize(
    "nonce", ["short", "x" * 129, "has.dot-aaaaaaaaaaaa", "spaces are bad!!!", "a/b+c=d" * 4]
)
def test_google_login_rejects_malformed_nonce(client: TestClient, nonce: str) -> None:
    resp = client.get(f"{API}/google", params={"nonce": nonce}, follow_redirects=False)
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid nonce"}


@pytest.mark.usefixtures("google_configured")
def test_google_nonce_bound_to_state_cookie_and_returned(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    resp = client.get(f"{API}/google", params={"nonce": NONCE}, follow_redirects=False)
    state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]
    cookie = resp.headers["set-cookie"]
    assert f"oauth_state={state}.{NONCE}" in cookie
    assert "HttpOnly" in cookie
    _mock_google(monkeypatch, GoogleUserInfo(sub="g-n", email="n@example.com", email_verified=True))
    cb = client.get(
        f"{API}/google/callback", params={"code": "c", "state": state}, follow_redirects=False
    )
    frag = _fragment(cb.headers["location"])
    assert frag["nonce"] == NONCE
    assert decode_token(frag["access_token"], "access") is not None


@pytest.mark.usefixtures("google_configured")
def test_google_nonce_echoed_on_error(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_google(monkeypatch, GoogleUserInfo(sub="g-e", email="e@example.com", email_verified=True))
    frag = _google_flow(client, NONCE, error="access_denied")
    assert frag == {"error": "access_denied", "nonce": NONCE}


@pytest.mark.usefixtures("google_configured")
def test_google_without_nonce_has_no_nonce_in_fragment(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_google(monkeypatch, GoogleUserInfo(sub="g-0", email="z@example.com", email_verified=True))
    frag = _google_flow(client)
    assert "nonce" not in frag and "access_token" in frag


@pytest.mark.usefixtures("google_configured")
def test_google_callback_tampered_nonce_cookie(client: TestClient) -> None:
    client.cookies.set("oauth_state", "abc.bad nonce!")
    resp = client.get(
        f"{API}/google/callback", params={"code": "c", "state": "abc"}, follow_redirects=False
    )
    assert _fragment(resp.headers["location"]) == {"error": "invalid_state"}


# --------------------------------------------------------------------------- L9 password bytes


def test_register_rejects_password_over_72_bytes(client: TestClient) -> None:
    password = "é" * 37  # 37 characters, 74 UTF-8 bytes
    resp = client.post(f"{API}/register", json={"email": "mb@example.com", "password": password})
    assert resp.status_code == 422
    assert "at most 72 bytes" in resp.text


def test_register_accepts_password_of_exactly_72_bytes(client: TestClient) -> None:
    password = "é" * 36  # 72 bytes
    resp = client.post(f"{API}/register", json={"email": "mb2@example.com", "password": password})
    assert resp.status_code == 201
    _login(client, "mb2@example.com", password)


# --------------------------------------------------------------------------- JWT (PyJWT)


def _forge(payload: dict[str, Any], algorithm: str = JWT_ALGORITHM) -> str:
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=algorithm)


def _claims(**overrides: Any) -> dict[str, Any]:
    now = datetime.now(UTC)
    base: dict[str, Any] = {
        "sub": "1",
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def test_jwt_valid_token_decodes() -> None:
    assert decode_token(_forge(_claims()), "access") is not None


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda: _forge(_claims(exp=None)),  # no exp
        lambda: _forge(_claims(type=None)),  # no type
        lambda: _forge(_claims(type="refresh")),  # wrong type
        lambda: _forge(_claims(), algorithm="HS512"),  # algorithm not allowed
        lambda: pyjwt.encode(_claims(), key=None, algorithm="none"),  # alg=none
        lambda: _forge(_claims(exp=datetime.now(UTC) - timedelta(seconds=5))),  # expired
    ],
)
def test_jwt_rejects_invalid_tokens(token_factory: Callable[[], str]) -> None:
    assert decode_token(token_factory(), "access") is None
