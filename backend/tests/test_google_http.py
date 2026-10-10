"""Google OAuth HTTP helpers (``exchange_code`` / ``fetch_userinfo``) via httpx.MockTransport.

The helpers are synchronous (``httpx.Client``) so the callback can run in the threadpool.
"""

import inspect
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.auth import google

Handler = Callable[[httpx.Request], httpx.Response]


def _mock(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []
    real_client = httpx.Client

    def _wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    def _factory(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(_wrapped)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(google.httpx, "Client", _factory)
    return seen


def test_exchange_code_success(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _mock(monkeypatch, lambda r: httpx.Response(200, json={"access_token": "goog-at"}))
    assert google.exchange_code("the-code") == "goog-at"
    assert str(seen[0].url) == google.GOOGLE_TOKEN_URL
    body = seen[0].content.decode()
    assert "code=the-code" in body and "grant_type=authorization_code" in body


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(400, json={"error": "invalid_grant"}),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"access_token": ""}),
        httpx.Response(200, json={"access_token": 123}),
    ],
)
def test_exchange_code_rejected(monkeypatch: pytest.MonkeyPatch, response: httpx.Response) -> None:
    _mock(monkeypatch, lambda r: response)
    with pytest.raises(google.GoogleOAuthError):
        google.exchange_code("c")


def test_exchange_code_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    _mock(monkeypatch, _fail)
    with pytest.raises(google.GoogleOAuthError, match="request failed"):
        google.exchange_code("c")


def test_fetch_userinfo_success(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "sub": "123",
        "email": "  Person@Example.COM ",
        "email_verified": True,
        "name": "Person",
        "picture": "https://p/x.png",
    }
    seen = _mock(monkeypatch, lambda r: httpx.Response(200, json=payload))
    info = google.fetch_userinfo("tok")
    assert seen[0].headers["Authorization"] == "Bearer tok"
    assert info == google.GoogleUserInfo(
        sub="123",
        email="person@example.com",
        email_verified=True,
        name="Person",
        picture="https://p/x.png",
    )


@pytest.mark.parametrize(
    ("verified", "expected"), [(True, True), ("true", True), (False, False), ("yes", False)]
)
def test_fetch_userinfo_verified_parsing(
    monkeypatch: pytest.MonkeyPatch, verified: Any, expected: bool
) -> None:
    payload = {"sub": "1", "email": "a@b.co", "email_verified": verified, "name": 5}
    _mock(monkeypatch, lambda r: httpx.Response(200, json=payload))
    info = google.fetch_userinfo("t")
    assert info.email_verified is expected
    assert info.name is None and info.picture is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, json={}),
        httpx.Response(200, json={"email": "a@b.co"}),
        httpx.Response(200, json={"sub": "1"}),
        httpx.Response(200, json={"sub": 1, "email": "a@b.co"}),
    ],
)
def test_fetch_userinfo_rejected(monkeypatch: pytest.MonkeyPatch, response: httpx.Response) -> None:
    _mock(monkeypatch, lambda r: response)
    with pytest.raises(google.GoogleOAuthError):
        google.fetch_userinfo("t")


def test_fetch_userinfo_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    _mock(monkeypatch, _fail)
    with pytest.raises(google.GoogleOAuthError, match="request failed"):
        google.fetch_userinfo("t")


def test_helpers_are_synchronous() -> None:
    """The callback runs in the threadpool; async helpers would never be awaited there."""
    assert not inspect.iscoroutinefunction(google.exchange_code)
    assert not inspect.iscoroutinefunction(google.fetch_userinfo)
