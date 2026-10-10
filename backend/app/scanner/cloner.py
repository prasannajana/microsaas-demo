"""Safe, size-bounded shallow git clone of a validated public GitHub repository.

Pipeline (each step bounded by SCAN_CLONE_TIMEOUT_SECONDS and the scan deadline):
1. Re-validate URL and branch (even though the API layer already did).
2. `github_api.fetch_repo_metadata`: reject missing/private repos and repos whose reported
   size exceeds SCAN_MAX_REPO_SIZE_MB; learn the canonical name and default branch.
3. `git clone --no-checkout --depth 1` (no working tree is written yet).
4. `git ls-tree -r -l -z HEAD` streamed: reject if the blobs total more than
   SCAN_MAX_REPO_SIZE_MB or there are more than SCAN_MAX_FILES entries (checkout bombs).
5. `git checkout`, then `git rev-parse HEAD`.

Security rules:
- argument list only (never a shell), `--` before the URL
- only https is allowed (protocol.allow=never), no redirects, fsck on transfer, no hooks,
  no fsmonitor, no submodules, no symlink checkout, no LFS smudge, no terminal prompts,
  user/system git config ignored (no credential helpers)
- no credentials are ever sent to git (GITHUB_TOKEN is only used for the metadata API)
- every git process runs in its own session; on timeout the whole process group is killed
"""

import logging
import os
import re
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.scanner import context, github_api
from app.scanner.urls import is_valid_branch, is_valid_github_url, split_github_url

logger = logging.getLogger(__name__)

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_MB = 1024 * 1024
_READ_CHUNK = 64 * 1024
# A single ls-tree record is "<mode> <type> <sha> <size>\t<path>"; paths are bounded by git.
_MAX_TREE_RECORD_BYTES = 64 * 1024

# Applied to every git invocation (clone, ls-tree, checkout, rev-parse).
GIT_HARDENING: tuple[str, ...] = (
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "protocol.allow=never",
    "-c",
    "protocol.https.allow=always",
    "-c",
    "protocol.file.allow=never",
    "-c",
    "http.followRedirects=false",
    "-c",
    "transfer.fsckObjects=true",
    "-c",
    "core.fsmonitor=false",
    "-c",
    "submodule.recurse=false",
    "-c",
    "core.symlinks=false",
    "-c",
    "credential.helper=",
)


class CloneError(Exception):
    """Clone failed; the message is user-readable and safe to show in the UI."""


@dataclass(frozen=True)
class CloneResult:
    """Outcome of a successful clone."""

    commit_sha: str
    size_bytes: int


def _git_env() -> dict[str, str]:
    """Minimal environment for git: no prompts, no LFS, no user/system config, no token."""
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "LC_ALL": "C",
        "LANG": "C",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_ASKPASS": "",
        "SSH_ASKPASS": "",
    }


def build_clone_command(repo_url: str, branch: str | None, dest: Path) -> list[str]:
    """
    Build the git clone argument list (no secrets are ever included).

    Args:
        repo_url: Validated GitHub URL
        branch: Optional validated branch name
        dest: Destination directory

    Returns:
        Argument list for a subprocess (no working tree is checked out).
    """
    return [
        "git",
        *GIT_HARDENING,
        "clone",
        "--no-checkout",
        "--depth",
        "1",
        "--single-branch",
        "--no-tags",
        "--no-recurse-submodules",
        *(["--branch", branch] if branch else []),
        "--",
        repo_url,
        str(dest),
    ]


def build_git_command(repo_dir: Path, *args: str) -> list[str]:
    """Build a hardened `git -C <repo_dir> <args...>` argument list."""
    return ["git", *GIT_HARDENING, "-C", str(repo_dir), *args]


def _kill_group(proc: "subprocess.Popen[str] | subprocess.Popen[bytes]") -> None:
    """SIGKILL the process group led by `proc` (git and its helpers)."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _run_git(
    args: list[str], timeout: float, env: dict[str, str]
) -> "subprocess.CompletedProcess[str]":
    """
    Run git in a new session; on timeout kill the whole process group.

    Raises:
        subprocess.TimeoutExpired: After the process group has been killed.
        FileNotFoundError: If git is not installed.
    """
    with subprocess.Popen(  # noqa: S603 - fixed argument list, validated inputs
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        start_new_session=True,
    ) as proc:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except BaseException:
            _kill_group(proc)
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - pipes held by a stray child
                pass
            raise
    return subprocess.CompletedProcess(args, proc.returncode, stdout, stderr)


def _blob_size(record: bytes) -> int:
    """Size of one `ls-tree -l` record, 0 for non-blobs (submodules) or unparsable lines."""
    meta, _, _path = record.partition(b"\t")
    parts = meta.split()
    if len(parts) == 4 and parts[1] == b"blob" and parts[3].isdigit():
        return int(parts[3])
    return 0


def tree_stats(repo_dir: Path, env: dict[str, str], timeout: float) -> tuple[int, int]:
    """
    Stream `git ls-tree -r -l -z HEAD` and enforce entry-count and total-size limits.

    Stops reading (and kills git) as soon as a limit is exceeded, so a tree with millions
    of entries is never fully buffered.

    Returns:
        (entries, total_blob_bytes)

    Raises:
        CloneError: Too many files, too large, timed out, or git failed.
    """
    max_files = settings.SCAN_MAX_FILES
    max_bytes = settings.SCAN_MAX_REPO_SIZE_MB * _MB
    cmd = build_git_command(repo_dir, "ls-tree", "-r", "-l", "-z", "--full-tree", "HEAD")
    try:
        proc = subprocess.Popen(  # noqa: S603 - fixed argument list
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise CloneError("Git is not available on the server") from exc

    timed_out = threading.Event()

    def _expire() -> None:
        timed_out.set()
        _kill_group(proc)

    timer = threading.Timer(timeout, _expire)
    timer.daemon = True
    timer.start()
    entries = 0
    total = 0
    try:
        assert proc.stdout is not None  # noqa: S101 - stdout=PIPE
        pending = b""
        while chunk := proc.stdout.read(_READ_CHUNK):
            records = (pending + chunk).split(b"\0")
            pending = records.pop()
            for record in records:
                entries += 1
                total += _blob_size(record)
                if entries > max_files:
                    raise CloneError(f"Repository has too many files (limit {max_files:,})")
                if total > max_bytes:
                    raise CloneError(
                        f"Repository exceeds size limit ({settings.SCAN_MAX_REPO_SIZE_MB} MB)"
                    )
            if len(pending) > _MAX_TREE_RECORD_BYTES:
                raise CloneError("Failed to read the repository contents")
        returncode = proc.wait()
    finally:
        timer.cancel()
        if proc.poll() is None:
            _kill_group(proc)
            proc.wait()
        if proc.stdout is not None:
            proc.stdout.close()
    if timed_out.is_set():
        raise CloneError("Repository clone timed out while listing files")
    if returncode != 0:
        raise CloneError("Failed to read the repository contents")
    return entries, total


def directory_size(path: Path) -> int:
    """Return the total size in bytes of files under `path`, never following symlinks."""
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path, followlinks=False):
        for name in filenames:
            try:
                total += os.lstat(os.path.join(dirpath, name)).st_size
            except OSError:
                continue
    return total


EMPTY_REPO_MESSAGE = (
    "This repository is empty (no commits yet). Push some code to GitHub, then scan again."
)


def _friendly_error(stderr: str, branch: str | None) -> str:
    text = stderr.lower()
    if branch and ("remote branch" in text and "not found" in text):
        return f"Branch '{branch}' was not found in the repository"
    if any(
        marker in text
        for marker in (
            "repository not found",
            "could not read username",
            "authentication failed",
            "terminal prompts disabled",
            "error: 403",
            "returned error: 404",
            "not found",
        )
    ):
        return github_api.NOT_FOUND_MESSAGE
    if "could not resolve host" in text or "unable to access" in text:
        return "Could not reach GitHub, please try again later"
    return "Failed to clone repository"


def _fetch_metadata(repo_url: str) -> github_api.RepoMetadata:
    owner, repo = split_github_url(repo_url)
    try:
        meta = github_api.fetch_repo_metadata(owner, repo)
    except github_api.GitHubApiError as exc:
        raise CloneError(str(exc)) from exc
    if meta.private:
        raise CloneError(github_api.NOT_FOUND_MESSAGE)
    if meta.size_kb > settings.SCAN_MAX_REPO_SIZE_MB * 1024:
        raise CloneError(f"Repository exceeds size limit ({settings.SCAN_MAX_REPO_SIZE_MB} MB)")
    return meta


def clone_repo(repo_url: str, branch: str | None, dest: Path) -> CloneResult:
    """
    Check, shallow-clone and (only if within limits) check out a GitHub repository.

    Args:
        repo_url: Normalized https://github.com/<owner>/<repo> URL
        branch: Branch to clone, or None for the repository's default branch
        dest: Destination directory (must not exist or be empty)

    Returns:
        CloneResult with the checked-out commit SHA and on-disk size.

    Raises:
        CloneError: With a user-readable message on any failure.
        ScanTimeoutError: If the surrounding scan context's deadline is exhausted.
    """
    if not is_valid_github_url(repo_url):
        raise CloneError("Invalid repository URL")
    if branch is not None and not is_valid_branch(branch):
        raise CloneError("Invalid branch name")

    meta = _fetch_metadata(repo_url)
    clone_url = meta.clone_url
    requested_branch = branch
    branch = branch or meta.default_branch

    env = _git_env()
    limit = settings.SCAN_CLONE_TIMEOUT_SECONDS
    clone_deadline = time.monotonic() + limit
    timeout_message = f"Repository clone timed out after {limit} seconds"

    def budget() -> float:
        left = clone_deadline - time.monotonic()
        if left <= 0:
            raise CloneError(timeout_message)
        return context.clamp_timeout(left)

    logger.info("Cloning %s (branch=%s)", clone_url, branch or "<default>")
    try:
        proc = _run_git(build_clone_command(clone_url, branch, dest), budget(), env)
    except subprocess.TimeoutExpired as exc:
        raise CloneError(timeout_message) from exc
    except FileNotFoundError as exc:
        logger.error("git executable not found")
        raise CloneError("Git is not available on the server") from exc
    if proc.returncode != 0:
        logger.warning(
            "git clone failed (exit %s): %s", proc.returncode, (proc.stderr or "")[-500:]
        )
        message = _friendly_error(proc.stderr or "", branch)
        # GitHub reports a default branch even for repos with no commits; a missing default
        # branch (or any missing branch in a 0 KB repo) means there is nothing to scan yet.
        if message.startswith("Branch ") and (requested_branch is None or meta.size_kb == 0):
            message = EMPTY_REPO_MESSAGE
        raise CloneError(message)

    entries, tree_bytes = tree_stats(dest, env, budget())

    try:
        checkout = _run_git(
            build_git_command(dest, "checkout", "--no-recurse-submodules", "-q", "-f", "HEAD"),
            budget(),
            env,
        )
        if checkout.returncode != 0:
            logger.warning("git checkout failed: %s", (checkout.stderr or "")[-500:])
            raise CloneError("Failed to check out the repository")
        rev = _run_git(build_git_command(dest, "rev-parse", "HEAD"), budget(), env)
    except subprocess.TimeoutExpired as exc:
        raise CloneError(timeout_message) from exc
    except FileNotFoundError as exc:
        raise CloneError("Git is not available on the server") from exc
    sha = (rev.stdout or "").strip()
    if rev.returncode != 0 or not _SHA_RE.fullmatch(sha):
        raise CloneError("Failed to read the repository commit")

    size = directory_size(dest)
    logger.info(
        "Cloned %s at %s (%d entries, %d tree bytes, %d on disk)",
        clone_url,
        sha,
        entries,
        tree_bytes,
        size,
    )
    return CloneResult(commit_sha=sha, size_bytes=size)
