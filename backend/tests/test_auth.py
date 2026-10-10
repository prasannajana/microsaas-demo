"""Tests for the auth module: register/login/refresh/logout, /me, Google OAuth, guards."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import google
from app.auth.google import GoogleOAuthError, GoogleUserInfo
from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.config import settings
from app.dependencies import get_current_admin, get_db
from app.exceptions import AppError, app_error_handler
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.auth_service import hash_refresh_token

API = "/api/v1/auth"
UserFactory = Callable[..., User]
AuthHeaders = Callable[[User], dict[str, str]]


def _fragment(location: str) -> dict[str, str]:
    """Parse the URL fragment of a redirect Location into a flat dict."""
    return {k: v[0] for k, v in parse_qs(urlparse(location).fragment).items()}


# --------------------------------------------------------------------------- register


def test_register_returns_token_pair(client: TestClient, db: Session) -> None:
    resp = client.post(
        f"{API}/register",
        json={"email": "New@Example.com", "password": "supersecret", "full_name": "New"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer"
    access = decode_token(body["access_token"], "access")
    assert access is not None
    user = db.scalars(select(User).where(User.email == "new@example.com")).one()
    assert access["sub"] == str(user.id)
    assert user.hashed_password and user.hashed_password != "supersecret"
    row = db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)).one()
    assert row.token == hash_refresh_token(body["refresh_token"])  # only the hash is stored
    assert row.revoked is False


def test_register_duplicate_email_conflict(client: TestClient, user: User) -> None:
    resp = client.post(f"{API}/register", json={"email": user.email, "password": "password123"})
    assert resp.status_code == 409
    assert resp.json() == {"detail": "Email already registered"}


def test_register_duplicate_email_case_insensitive(client: TestClient, user: User) -> None:
    resp = client.post(
        f"{API}/register", json={"email": user.email.upper(), "password": "password123"}
    )
    assert resp.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "a@example.com", "password": "short"},
        {"email": "not-an-email", "password": "password123"},
        {"password": "password123"},
    ],
)
def test_register_validation(client: TestClient, payload: dict[str, str]) -> None:
    assert client.post(f"{API}/register", json=payload).status_code == 422


# --------------------------------------------------------------------------- login


def test_login_success(client: TestClient, user: User) -> None:
    resp = client.post(f"{API}/login", json={"email": user.email, "password": "password123"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"access_token", "refresh_token", "token_type"}
    payload = decode_token(body["access_token"], "access")
    assert payload is not None and payload["sub"] == str(user.id)


def test_login_wrong_password(client: TestClient, user: User) -> None:
    resp = client.post(f"{API}/login", json={"email": user.email, "password": "wrongpass1"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid email or password"}


def test_login_unknown_email(client: TestClient) -> None:
    resp = client.post(
        f"{API}/login", json={"email": "ghost@example.com", "password": "password123"}
    )
    assert resp.status_code == 401


def test_login_inactive_user(client: TestClient, user_factory: UserFactory) -> None:
    u = user_factory(is_active=False)
    resp = client.post(f"{API}/login", json={"email": u.email, "password": "password123"})
    assert resp.status_code == 401


def test_login_oauth_only_user(client: TestClient, user_factory: UserFactory) -> None:
    u = user_factory(password=None, oauth_provider="google", google_id="g-1")
    resp = client.post(f"{API}/login", json={"email": u.email, "password": "password123"})
    assert resp.status_code == 401


def test_login_rejects_form_body(client: TestClient, user: User) -> None:
    resp = client.post(f"{API}/login", data={"username": user.email, "password": "password123"})
    assert resp.status_code == 422


# --------------------------------------------------------------------------- refresh / logout


def _login(client: TestClient, user: User) -> dict[str, str]:
    resp = client.post(f"{API}/login", json={"email": user.email, "password": "password123"})
    assert resp.status_code == 200
    data: dict[str, str] = resp.json()
    return data


def test_refresh_rotates_tokens(client: TestClient, db: Session, user: User) -> None:
    tokens = _login(client, user)
    resp = client.post(f"{API}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    new = resp.json()
    assert new["refresh_token"] != tokens["refresh_token"]
    old_row = db.scalars(
        select(RefreshToken).where(
            RefreshToken.token == hash_refresh_token(tokens["refresh_token"])
        )
    ).one()
    db.refresh(old_row)
    assert old_row.revoked is True
    # New one works; the old (rotated) one can't be reused.
    ok = client.post(f"{API}/refresh", json={"refresh_token": new["refresh_token"]})
    assert ok.status_code == 200
    again = client.post(f"{API}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert again.status_code == 401


def test_refresh_unknown_token(client: TestClient, user: User) -> None:
    token, _ = create_refresh_token(user.id)  # valid JWT but never persisted
    assert client.post(f"{API}/refresh", json={"refresh_token": token}).status_code == 401


def test_refresh_garbage_token(client: TestClient) -> None:
    assert client.post(f"{API}/refresh", json={"refresh_token": "nope"}).status_code == 401


def test_refresh_rejects_access_token(client: TestClient, user: User) -> None:
    tokens = _login(client, user)
    resp = client.post(f"{API}/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


def test_refresh_expired_row(client: TestClient, db: Session, user: User) -> None:
    tokens = _login(client, user)
    row = db.scalars(
        select(RefreshToken).where(
            RefreshToken.token == hash_refresh_token(tokens["refresh_token"])
        )
    ).one()
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    resp = client.post(f"{API}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


def test_refresh_expired_jwt(
    client: TestClient, db: Session, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", -1)
    token, expires = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token=hash_refresh_token(token),
            expires_at=expires + timedelta(days=2),
        )
    )
    db.commit()
    assert client.post(f"{API}/refresh", json={"refresh_token": token}).status_code == 401


def test_refresh_inactive_user(client: TestClient, db: Session, user: User) -> None:
    tokens = _login(client, user)
    user.is_active = False
    db.commit()
    resp = client.post(f"{API}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


def test_logout_revokes_refresh_token(client: TestClient, user: User) -> None:
    tokens = _login(client, user)
    resp = client.post(f"{API}/logout", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 204
    assert resp.content == b""
    again = client.post(f"{API}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert again.status_code == 401


def test_logout_unknown_token_is_noop(client: TestClient) -> None:
    assert client.post(f"{API}/logout", json={"refresh_token": "x"}).status_code == 204


# --------------------------------------------------------------------------- /me


def test_me_returns_user(client: TestClient, user: User, auth_headers: AuthHeaders) -> None:
    resp = client.get(f"{API}/me", headers=auth_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == user.id
    assert body["email"] == user.email
    assert set(body) == {
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


def test_me_requires_token(client: TestClient) -> None:
    resp = client.get(f"{API}/me")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


def test_me_rejects_invalid_token(client: TestClient) -> None:
    resp = client.get(f"{API}/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


def test_me_rejects_refresh_token(client: TestClient, user: User) -> None:
    token, _ = create_refresh_token(user.id)
    resp = client.get(f"{API}/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_me_rejects_inactive_user(
    client: TestClient, user_factory: UserFactory, auth_headers: AuthHeaders
) -> None:
    u = user_factory(is_active=False)
    assert client.get(f"{API}/me", headers=auth_headers(u)).status_code == 401


def test_me_rejects_deleted_user(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {create_access_token(999_999)}"}
    assert client.get(f"{API}/me", headers=headers).status_code == 401


def test_update_me(client: TestClient, user: User, auth_headers: AuthHeaders) -> None:
    resp = client.put(f"{API}/me", json={"full_name": "Renamed"}, headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Renamed"
    assert client.get(f"{API}/me", headers=auth_headers(user)).json()["full_name"] == "Renamed"


def test_update_me_requires_auth(client: TestClient) -> None:
    assert client.put(f"{API}/me", json={"full_name": "x"}).status_code == 401


# --------------------------------------------------------------------------- admin guard


def _admin_app(db: Session) -> TestClient:
    mini = FastAPI()
    mini.add_exception_handler(AppError, app_error_handler)

    @mini.get("/admin-only")
    def admin_only(admin: User = Depends(get_current_admin)) -> dict[str, int]:
        return {"id": admin.id}

    def _db() -> Session:
        return db

    mini.dependency_overrides[get_db] = _db
    return TestClient(mini)


def test_get_current_admin_allows_admin(
    db: Session, admin_user: User, auth_headers: AuthHeaders
) -> None:
    resp = _admin_app(db).get("/admin-only", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    assert resp.json() == {"id": admin_user.id}


def test_get_current_admin_forbids_regular_user(
    db: Session, user: User, auth_headers: AuthHeaders
) -> None:
    resp = _admin_app(db).get("/admin-only", headers=auth_headers(user))
    assert resp.status_code == 403


# --------------------------------------------------------------------------- Google OAuth


@pytest.fixture
def google_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://frontend.test")


def _mock_google(
    monkeypatch: pytest.MonkeyPatch, info: GoogleUserInfo | None = None, fail: bool = False
) -> list[str]:
    """Patch the Google HTTP helpers; returns a list recording exchanged codes."""
    codes: list[str] = []

    def fake_exchange(code: str) -> str:
        codes.append(code)
        if fail:
            raise GoogleOAuthError("boom")
        return "google-access-token"

    def fake_userinfo(access_token: str) -> GoogleUserInfo:
        assert access_token == "google-access-token"
        assert info is not None
        return info

    monkeypatch.setattr(google, "exchange_code", fake_exchange)
    monkeypatch.setattr(google, "fetch_userinfo", fake_userinfo)
    return codes


def _start_flow(client: TestClient) -> str:
    resp = client.get(f"{API}/google", follow_redirects=False)
    assert resp.status_code == 302
    state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]
    return state


def test_google_not_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    resp = client.get(f"{API}/google", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"].endswith("/auth/callback#error=google_not_configured")
    assert "oauth_state" not in resp.cookies


@pytest.mark.usefixtures("google_configured")
def test_google_redirect_sets_state_cookie(client: TestClient) -> None:
    resp = client.get(f"{API}/google", follow_redirects=False)
    assert resp.status_code == 302
    location = urlparse(resp.headers["location"])
    assert location.netloc == "accounts.google.com"
    query = parse_qs(location.query)
    assert query["client_id"] == ["test-client-id"]
    assert query["scope"] == ["openid email profile"]
    assert query["redirect_uri"] == [settings.GOOGLE_REDIRECT_URI]
    assert query["response_type"] == ["code"]
    cookie = resp.headers["set-cookie"]
    assert f"oauth_state={query['state'][0]}" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=600" in cookie


@pytest.mark.usefixtures("google_configured")
def test_google_callback_creates_user(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = GoogleUserInfo(
        sub="google-123",
        email="gina@example.com",
        email_verified=True,
        name="Gina",
        picture="https://img.example/gina.png",
    )
    codes = _mock_google(monkeypatch, info)
    state = _start_flow(client)
    resp = client.get(
        f"{API}/google/callback", params={"code": "abc", "state": state}, follow_redirects=False
    )
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("http://frontend.test/auth/callback#")
    frag = _fragment(location)
    assert codes == ["abc"]
    user = db.scalars(select(User).where(User.email == "gina@example.com")).one()
    assert user.google_id == "google-123"
    assert user.oauth_provider == "google"
    assert user.is_verified is True
    assert user.avatar_url == "https://img.example/gina.png"
    assert user.hashed_password is None
    payload = decode_token(frag["access_token"], "access")
    assert payload is not None and payload["sub"] == str(user.id)
    assert db.scalars(
        select(RefreshToken).where(RefreshToken.token == hash_refresh_token(frag["refresh_token"]))
    ).one()
    assert 'oauth_state=""' in resp.headers["set-cookie"]  # cookie cleared
    # Tokens are usable.
    me = client.get(f"{API}/me", headers={"Authorization": f"Bearer {frag['access_token']}"})
    assert me.json()["oauth_provider"] == "google"


@pytest.mark.usefixtures("google_configured")
def test_google_callback_links_existing_account(
    client: TestClient, db: Session, user_factory: UserFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A *verified* account keeps its password when Google is linked (see
    # test_auth_security.py for the unverified / pre-hijack case).
    user = user_factory(is_verified=True)
    info = GoogleUserInfo(sub="g-link", email=user.email, email_verified=True, name="Other")
    _mock_google(monkeypatch, info)
    state = _start_flow(client)
    resp = client.get(
        f"{API}/google/callback", params={"code": "c", "state": state}, follow_redirects=False
    )
    assert "access_token" in _fragment(resp.headers["location"])
    db.refresh(user)
    assert user.google_id == "g-link"
    assert user.oauth_provider == "google"
    assert user.is_verified is True
    assert user.full_name == "Test User"  # existing name kept
    assert user.hashed_password is not None  # password login still works
    assert db.query(User).filter(User.email == user.email).count() == 1


@pytest.mark.usefixtures("google_configured")
def test_google_callback_matches_by_google_id(
    client: TestClient, db: Session, user_factory: UserFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = user_factory(email="old@example.com", password=None, google_id="g-same")
    info = GoogleUserInfo(sub="g-same", email="changed@example.com", email_verified=True)
    _mock_google(monkeypatch, info)
    state = _start_flow(client)
    resp = client.get(
        f"{API}/google/callback", params={"code": "c", "state": state}, follow_redirects=False
    )
    frag = _fragment(resp.headers["location"])
    payload = decode_token(frag["access_token"], "access")
    assert payload is not None and payload["sub"] == str(existing.id)


@pytest.mark.usefixtures("google_configured")
def test_google_callback_state_mismatch(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    codes = _mock_google(monkeypatch)
    _start_flow(client)
    resp = client.get(
        f"{API}/google/callback",
        params={"code": "abc", "state": "tampered"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "http://frontend.test/auth/callback#error=invalid_state"
    assert codes == []  # never exchanged the code


@pytest.mark.usefixtures("google_configured")
def test_google_callback_missing_cookie(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_google(monkeypatch)
    resp = client.get(
        f"{API}/google/callback", params={"code": "abc", "state": "s"}, follow_redirects=False
    )
    assert _fragment(resp.headers["location"]) == {"error": "invalid_state"}


@pytest.mark.usefixtures("google_configured")
def test_google_callback_unverified_email(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = GoogleUserInfo(sub="g-x", email="unverified@example.com", email_verified=False)
    _mock_google(monkeypatch, info)
    state = _start_flow(client)
    resp = client.get(
        f"{API}/google/callback", params={"code": "c", "state": state}, follow_redirects=False
    )
    assert _fragment(resp.headers["location"]) == {"error": "email_not_verified"}
    assert db.query(User).filter(User.email == "unverified@example.com").count() == 0


@pytest.mark.usefixtures("google_configured")
def test_google_callback_exchange_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_google(monkeypatch, fail=True)
    state = _start_flow(client)
    resp = client.get(
        f"{API}/google/callback", params={"code": "c", "state": state}, follow_redirects=False
    )
    assert _fragment(resp.headers["location"]) == {"error": "oauth_failed"}


@pytest.mark.usefixtures("google_configured")
def test_google_callback_user_denied(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    codes = _mock_google(monkeypatch)
    state = _start_flow(client)
    resp = client.get(
        f"{API}/google/callback",
        params={"error": "access_denied", "state": state},
        follow_redirects=False,
    )
    assert _fragment(resp.headers["location"]) == {"error": "access_denied"}
    assert codes == []


@pytest.mark.usefixtures("google_configured")
def test_google_callback_inactive_user(
    client: TestClient, user_factory: UserFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    u = user_factory(is_active=False)
    _mock_google(monkeypatch, GoogleUserInfo(sub="g-in", email=u.email, email_verified=True))
    state = _start_flow(client)
    resp = client.get(
        f"{API}/google/callback", params={"code": "c", "state": state}, follow_redirects=False
    )
    assert _fragment(resp.headers["location"]) == {"error": "account_disabled"}


# --------------------------------------------------------------------------- rate limiting


@pytest.mark.usefixtures("enable_rate_limit")
def test_login_rate_limited(client: TestClient, user: User) -> None:
    body = {"email": user.email, "password": "wrongpass1"}
    statuses = [client.post(f"{API}/login", json=body).status_code for _ in range(6)]
    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429
