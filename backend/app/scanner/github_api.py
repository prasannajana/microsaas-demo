"""Pre-clone repository metadata lookup via the GitHub REST API.

`fetch_repo_metadata` is called before any clone so we can reject private, missing or
oversized repositories without downloading anything, and learn the default branch.

Rules:
- `GET https://api.github.com/repos/{owner}/{repo}`, 10 s timeout, redirects NOT followed
  automatically.
- A 301 (renamed/transferred repository) is followed exactly once, and only to another
  https://api.github.com/ URL; the canonical `full_name` from that response is then used
  for the clone (git itself runs with http.followRedirects=false).
- GITHUB_TOKEN, when configured, is sent only on this API call (for higher rate limits).
  It is never sent to git. `private: true` is rejected even when the token can see it.
- Tests must monkeypatch this function (or pass `transport=`); tests never hit the network.
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.scanner.urls import GITHUB_PREFIX, is_valid_branch, is_valid_github_url

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"
API_TIMEOUT_SECONDS = 10.0

NOT_FOUND_MESSAGE = "Repository not found or is private"
RATE_LIMITED_MESSAGE = "GitHub is rate-limiting requests, please try again later"
UNREACHABLE_MESSAGE = "Could not reach GitHub, please try again later"


class GitHubApiError(Exception):
    """Metadata lookup failed; the message is user-readable and safe to show in the UI."""


@dataclass(frozen=True)
class RepoMetadata:
    """The subset of the GitHub repository resource the scanner needs."""

    full_name: str
    private: bool
    size_kb: int
    default_branch: str | None

    @property
    def clone_url(self) -> str:
        """Canonical https://github.com/<owner>/<repo> URL for this repository."""
        return f"{GITHUB_PREFIX}{self.full_name}"


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "project-verification-scanner",
    }
    token = settings.GITHUB_TOKEN.strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse(payload: Any) -> RepoMetadata:
    if not isinstance(payload, dict):
        raise GitHubApiError(UNREACHABLE_MESSAGE)
    full_name = payload.get("full_name")
    size = payload.get("size")
    private = payload.get("private")
    branch = payload.get("default_branch")
    if (
        not isinstance(full_name, str)
        or not is_valid_github_url(f"{GITHUB_PREFIX}{full_name}")
        or not isinstance(size, int)
        or isinstance(size, bool)
        or size < 0
        or not isinstance(private, bool)
    ):
        raise GitHubApiError(UNREACHABLE_MESSAGE)
    if not isinstance(branch, str) or not is_valid_branch(branch):
        branch = None
    return RepoMetadata(full_name=full_name, private=private, size_kb=size, default_branch=branch)


def fetch_repo_metadata(
    owner: str, repo: str, *, transport: httpx.BaseTransport | None = None
) -> RepoMetadata:
    """
    Look up a public GitHub repository.

    Args:
        owner: Repository owner (already validated)
        repo: Repository name (already validated)
        transport: Optional httpx transport (tests only)

    Returns:
        RepoMetadata for the repository (may be private — callers must reject that).

    Raises:
        GitHubApiError: Not found (404/451), rate limited (403/429), or any other failure.
    """
    url = f"{API_BASE}/repos/{owner}/{repo}"
    try:
        with httpx.Client(
            timeout=API_TIMEOUT_SECONDS,
            follow_redirects=False,
            headers=_headers(),
            transport=transport,
        ) as client:
            resp = client.get(url)
            if resp.status_code in (301, 302, 307, 308):
                location = resp.headers.get("location", "")
                if not location.startswith(f"{API_BASE}/"):
                    raise GitHubApiError(NOT_FOUND_MESSAGE)
                logger.info("GitHub API redirected %s/%s (renamed repository)", owner, repo)
                resp = client.get(location)
            status = resp.status_code
            if status in (403, 429):
                logger.warning("GitHub API rate limit / forbidden (%s) for %s", status, url)
                raise GitHubApiError(RATE_LIMITED_MESSAGE)
            if status in (301, 302, 307, 308, 404, 410, 451):
                raise GitHubApiError(NOT_FOUND_MESSAGE)
            if status != 200:
                logger.warning("GitHub API returned %s for %s", status, url)
                raise GitHubApiError(UNREACHABLE_MESSAGE)
            try:
                payload = resp.json()
            except ValueError as exc:
                raise GitHubApiError(UNREACHABLE_MESSAGE) from exc
    except httpx.HTTPError as exc:
        logger.warning("GitHub API request failed for %s: %s", url, type(exc).__name__)
        raise GitHubApiError(UNREACHABLE_MESSAGE) from exc
    return _parse(payload)
