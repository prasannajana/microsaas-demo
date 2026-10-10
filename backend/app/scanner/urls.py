"""GitHub URL / branch normalization and validation (shared by the API and the cloner)."""

import re
from urllib.parse import urlsplit, urlunsplit

# ASCII-only and used with fullmatch(): `\w` must not admit Unicode look-alikes and `$`
# must not accept a trailing newline.
GITHUB_URL_RE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+", re.ASCII)
BRANCH_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,99}", re.ASCII)
GITHUB_PREFIX = "https://github.com/"


class InvalidRepoUrlError(ValueError):
    """Raised when a repository URL is not a valid public GitHub URL."""


def is_valid_github_url(url: str) -> bool:
    """
    Return True if `url` is an already-normalized https://github.com/<owner>/<repo> URL.

    Args:
        url: Candidate URL

    Returns:
        True when the URL matches GITHUB_URL_RE and no path segment is made of dots only.
    """
    if not GITHUB_URL_RE.fullmatch(url):
        return False
    owner, repo = url.removeprefix(GITHUB_PREFIX).split("/")
    return not any(set(part) == {"."} for part in (owner, repo))


def split_github_url(url: str) -> tuple[str, str]:
    """
    Return (owner, repo) for a normalized GitHub URL.

    Raises:
        InvalidRepoUrlError: If `url` is not a valid normalized GitHub URL.
    """
    if not is_valid_github_url(url):
        raise InvalidRepoUrlError("Invalid repository URL")
    owner, repo = url.removeprefix(GITHUB_PREFIX).split("/")
    return owner, repo


def normalize_github_url(raw: str) -> str:
    """
    Normalize and validate a GitHub repository URL.

    Strips whitespace, trailing "/" and ".git", and lowercases the scheme and host.

    Args:
        raw: URL as entered by the user

    Returns:
        Normalized URL of the form https://github.com/<owner>/<repo>

    Raises:
        InvalidRepoUrlError: If the URL is not a GitHub repository URL.
    """
    url = (raw or "").strip()
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise InvalidRepoUrlError("Invalid repository URL") from exc
    if parts.query or parts.fragment or parts.username or parts.password or parts.port:
        raise InvalidRepoUrlError("Invalid repository URL")
    path = parts.path.rstrip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")].rstrip("/")
    normalized = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))
    if not is_valid_github_url(normalized):
        raise InvalidRepoUrlError("Invalid repository URL")
    return normalized


def is_valid_branch(branch: str) -> bool:
    """
    Return True if `branch` is a safe git branch name.

    Allows letters, digits, "_", ".", "/", "-"; must not start with "-" or "."
    and must not contain "..".
    """
    return bool(BRANCH_RE.fullmatch(branch)) and ".." not in branch and not branch.endswith("/")
