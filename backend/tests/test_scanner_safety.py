"""Security-relevant edge branches of the scanner: fs helpers and clone error mapping.

Covers the defensive paths in ``app/scanner/fs.py`` (resolution errors, OSError on
stat/iterdir, walk file cap, symlink handling) and ``app/scanner/cloner.py``
(network error mapping, process-group kill on timeout, streamed tree limits, a real
git clone of a local repository, lstat errors).
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import settings
from app.scanner import cloner, context, fs, github_api
from app.scanner.checks import manifests, missing_env_example
from tests.conftest import REAL_FETCH_REPO_METADATA

URL = "https://github.com/octocat/Hello-World"
SHA = "c" * 40


# --------------------------------------------------------------------------- fs.py


class _ExplodingPath:
    """Duck-typed path whose filesystem probes raise."""

    def __init__(self, exc: type[BaseException]) -> None:
        self.exc = exc

    def resolve(self, strict: bool = False) -> Path:
        raise self.exc("boom")

    def is_file(self) -> bool:
        raise OSError("boom")

    def is_dir(self) -> bool:
        raise OSError("boom")

    def is_symlink(self) -> bool:
        raise OSError("boom")


@pytest.mark.parametrize("exc", [OSError, RuntimeError])
def test_is_inside_resolution_error_is_outside(tmp_path: Path, exc: type[BaseException]) -> None:
    assert fs.is_inside(tmp_path.resolve(), _ExplodingPath(exc)) is False  # type: ignore[arg-type]


def test_is_inside_root_itself_and_children(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    (root / "a").mkdir()
    assert fs.is_inside(root, root) is True
    assert fs.is_inside(root, root / "a") is True
    assert fs.is_inside(root, root / ".." / "elsewhere") is False


def test_safe_is_file_oserror_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path.resolve()
    target = root / "f.txt"
    target.write_text("x")

    def _raise(self: Path) -> bool:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "is_file", _raise)
    assert fs.safe_is_file(root, target) is False


def test_safe_is_dir_oserror_returns_false(tmp_path: Path) -> None:
    assert fs.safe_is_dir(tmp_path.resolve(), _ExplodingPath(OSError)) is False  # type: ignore[arg-type]


def test_safe_is_dir_rejects_symlinked_directory(tmp_path: Path) -> None:
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    (root / "real").mkdir()
    (root / "link").symlink_to(root / "real", target_is_directory=True)
    assert fs.safe_is_dir(root, root / "real") is True
    assert fs.safe_is_dir(root, root / "link") is False  # even an in-repo dir symlink


def test_safe_is_file_rejects_symlink_escaping_root(tmp_path: Path) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_text("top secret")
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    (root / "leak").symlink_to(outside)
    assert fs.safe_is_file(root, root / "leak") is False
    assert fs.root_files(root) == []


def test_list_dir_iterdir_oserror_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path.resolve()
    (root / "x").write_text("x")

    def _raise(self: Path) -> Any:
        raise OSError("EACCES")

    monkeypatch.setattr(Path, "iterdir", _raise)
    assert fs.list_dir(root, root) == []


def test_list_dir_non_directory_returns_empty(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    (root / "file").write_text("x")
    assert fs.list_dir(root, root / "file") == []
    assert fs.list_dir(root, root / "missing") == []


def test_walk_files_respects_max_files(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    for i in range(10):
        (root / f"f{i}.txt").write_text("x")
    assert len(list(fs.walk_files(root, max_files=3))) == 3
    assert len(list(fs.walk_files(root))) == 10


def test_walk_files_skips_file_symlinks_even_inside_root(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    (root / "real.txt").write_text("x")
    (root / "alias.txt").symlink_to(root / "real.txt")
    assert [p.name for p in fs.walk_files(root)] == ["real.txt"]


def test_walk_dirs_skips_symlinks_and_skip_dirs(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    (outside / "deep").mkdir(parents=True)
    root = (tmp_path / "repo").resolve()
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "node_modules" / "x").mkdir(parents=True)
    (root / "escape").symlink_to(outside, target_is_directory=True)
    names = sorted(fs.rel(root, d) for d in fs.walk_dirs(root))
    assert names == ["src", "src/pkg"]


def test_top_level_dirs_excludes_skipped_and_symlinks(tmp_path: Path) -> None:
    root = (tmp_path / "repo").resolve()
    for d in ("src", ".git", "venv", "docs"):
        (root / d).mkdir(parents=True)
    (root / "lnk").symlink_to(root / "src", target_is_directory=True)
    assert [p.name for p in fs.top_level_dirs(root)] == ["docs", "src"]


# --------------------------------------------------------------- check read errors


def test_manifest_read_text_oserror_and_oversize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    big = tmp_path / "package.json"
    big.write_text("x" * 10)
    monkeypatch.setattr(manifests, "_MAX_MANIFEST_BYTES", 5)
    assert manifests._read_text(big) == ""
    assert manifests._read_text(tmp_path / "missing.json") == ""


def test_env_example_scan_survives_unreadable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path.resolve()
    (root / "app.py").write_text("import os\nos.environ['X']\n")
    real_read = Path.read_text

    def _read(self: Path, *args: Any, **kwargs: Any) -> str:
        if self.name == "app.py":
            raise OSError("EIO")
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _read)
    # File cannot be read -> no env usage detected -> no finding (and no crash).
    assert missing_env_example.check_missing_env_example(root) is None


# --------------------------------------------------------------------------- cloner


@pytest.mark.parametrize(
    "stderr",
    [
        "fatal: unable to access 'https://github.com/a/b/': Could not resolve host: github.com",
        "fatal: unable to access 'https://github.com/a/b/': Failed to connect",
    ],
)
def test_friendly_error_network(stderr: str) -> None:
    assert "Could not reach GitHub" in cloner._friendly_error(stderr, None)


@pytest.mark.parametrize(
    "stderr",
    [
        "remote: Repository not found.",
        "fatal: Authentication failed for 'https://github.com/a/b/'",
        "error: The requested URL returned error: 403",
        "fatal: The requested URL returned error: 404",
    ],
)
def test_friendly_error_private_or_missing(stderr: str) -> None:
    assert cloner._friendly_error(stderr, None) == "Repository not found or is private"


def test_friendly_error_never_leaks_stderr() -> None:
    msg = cloner._friendly_error("fatal: weird /internal/path/secret-token-123 happened", None)
    assert "secret-token-123" not in msg
    assert "/internal/path" not in msg


def test_git_env_never_contains_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "ghp_should_never_appear")
    env = cloner._git_env()
    assert not any(
        k.startswith("GIT_CONFIG_") and k != "GIT_CONFIG_NOSYSTEM" and k != "GIT_CONFIG_GLOBAL"
        for k in env
    )
    assert "ghp_should_never_appear" not in " ".join(env.values())
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull


def test_build_clone_command_hardening(tmp_path: Path) -> None:
    cmd = cloner.build_clone_command(URL, "dev", tmp_path / "d")
    for opt in (
        "core.hooksPath=/dev/null",
        "protocol.allow=never",
        "protocol.https.allow=always",
        "protocol.file.allow=never",
        "http.followRedirects=false",
        "transfer.fsckObjects=true",
        "core.fsmonitor=false",
        "core.symlinks=false",
        "credential.helper=",
    ):
        assert cmd[cmd.index(opt) - 1] == "-c"
        assert cmd.index(opt) < cmd.index("clone")  # global option, applies to the clone
    for flag in ("--no-checkout", "--no-recurse-submodules", "--no-tags", "--single-branch"):
        assert flag in cmd
    # `--` must precede the URL so it can never be parsed as an option.
    assert cmd.index("--") == cmd.index(URL) - 1


def test_build_git_command_is_hardened(tmp_path: Path) -> None:
    cmd = cloner.build_git_command(tmp_path, "checkout", "-f", "HEAD")
    assert cmd[0] == "git"
    assert "core.symlinks=false" in cmd and "core.hooksPath=/dev/null" in cmd
    assert cmd[-5:] == ["-C", str(tmp_path), "checkout", "-f", "HEAD"]


# ---- process handling (real subprocesses, no git needed)


def test_run_git_returns_completed_process() -> None:
    proc = cloner._run_git(
        [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)"],
        10,
        dict(os.environ),
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "out"
    assert proc.stderr.strip() == "err"


def _wait_dead(pid: int, seconds: float = 5.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def test_run_git_timeout_kills_process_group(tmp_path: Path) -> None:
    """L3: on timeout the whole group dies, including grandchildren (git-remote-https...)."""
    pidfile = tmp_path / "child.pid"
    script = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(pidfile)!r}, 'w').write(str(child.pid))\n"
        "time.sleep(60)\n"
    )
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        cloner._run_git([sys.executable, "-c", script], 1.5, dict(os.environ))
    assert time.monotonic() - started < 15
    grandchild = int(pidfile.read_text())
    assert _wait_dead(grandchild), "grandchild survived the timeout"


def test_kill_group_ignores_finished_process() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)  # noqa: S603
    proc.wait()
    cloner._kill_group(proc)  # must not raise


def test_blob_size_parsing() -> None:
    assert cloner._blob_size(b"100644 blob " + b"a" * 40 + b"     123\tpath/x") == 123
    assert cloner._blob_size(b"160000 commit " + b"a" * 40 + b"       -\tsub") == 0
    assert cloner._blob_size(b"garbage") == 0


# ---- tree_stats against real git


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    )


@pytest.fixture
def local_repo(tmp_path: Path) -> Path:
    """A real git repo: 3 files (10 + 20 + 30 bytes) and a symlink escaping the repo."""
    repo = tmp_path / "origin"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    (repo / "README.md").write_bytes(b"r" * 10)
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_bytes(b"a" * 20)
    (repo / "src" / "b.py").write_bytes(b"b" * 30)
    (repo / "passwd").symlink_to("/etc/passwd")
    hooks = repo / ".githooks"
    hooks.mkdir()
    (hooks / "post-checkout").write_text("#!/bin/sh\ntouch HOOK_RAN\n")
    _git("add", "-A", cwd=repo)
    _git("commit", "-q", "-m", "init", cwd=repo)
    return repo


def test_tree_stats_counts_entries_and_bytes(local_repo: Path) -> None:
    entries, total = cloner.tree_stats(local_repo, cloner._git_env(), 30)
    # README, src/a.py, src/b.py, passwd (symlink blob = 11 bytes), .githooks/post-checkout
    assert entries == 5
    assert total == 10 + 20 + 30 + len("/etc/passwd") + len("#!/bin/sh\ntouch HOOK_RAN\n")


def test_tree_stats_too_many_files(local_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SCAN_MAX_FILES", 2)
    with pytest.raises(cloner.CloneError, match="too many files"):
        cloner.tree_stats(local_repo, cloner._git_env(), 30)


def test_tree_stats_too_large(local_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SCAN_MAX_REPO_SIZE_MB", 0)
    with pytest.raises(cloner.CloneError, match="exceeds size limit"):
        cloner.tree_stats(local_repo, cloner._git_env(), 30)


def test_tree_stats_git_failure(tmp_path: Path) -> None:
    with pytest.raises(cloner.CloneError, match="Failed to read the repository contents"):
        cloner.tree_stats(tmp_path, cloner._git_env(), 30)  # not a git repository


def test_tree_stats_timeout_kills_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cloner,
        "build_git_command",
        lambda *_a: [sys.executable, "-c", "import time; time.sleep(60)"],
    )
    started = time.monotonic()
    with pytest.raises(cloner.CloneError, match="timed out"):
        cloner.tree_stats(tmp_path, dict(os.environ), 0.5)
    assert time.monotonic() - started < 15


def test_tree_stats_rejects_unterminated_huge_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cloner,
        "build_git_command",
        lambda *_a: [sys.executable, "-c", "import sys; sys.stdout.write('x' * 200000)"],
    )
    with pytest.raises(cloner.CloneError, match="Failed to read the repository contents"):
        cloner.tree_stats(tmp_path, dict(os.environ), 30)


def test_tree_stats_git_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cloner, "build_git_command", lambda *_a: ["/nonexistent/git-binary"])
    with pytest.raises(cloner.CloneError, match="Git is not available"):
        cloner.tree_stats(tmp_path, dict(os.environ), 30)


# ---- full clone_repo with real git (clone source swapped for a local file:// repo)


@pytest.fixture
def real_git_clone(local_repo: Path, monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Run the real pipeline; only the clone's network URL is replaced by the local repo."""
    real_run_git = cloner._run_git
    seen: list[list[str]] = []

    def _run(args: list[str], timeout: float, env: dict[str, str]) -> Any:
        seen.append(args)
        if "clone" in args:
            assert URL in args
            at = args.index("clone")
            args = [
                *args[:at],
                "-c",
                "protocol.file.allow=always",
                *[f"file://{local_repo}" if a == URL else a for a in args[at:]],
            ]
        return real_run_git(args, timeout, env)

    monkeypatch.setattr(cloner, "_run_git", _run)
    return seen


def test_real_clone_checks_tree_then_checks_out(
    tmp_path: Path, real_git_clone: list[list[str]]
) -> None:
    dest = tmp_path / "clone"
    result = cloner.clone_repo(URL, "main", dest)
    assert len(result.commit_sha) == 40
    assert (dest / "README.md").read_bytes() == b"r" * 10
    assert (dest / "src" / "b.py").is_file()
    # core.symlinks=false: the escaping symlink is a plain text file, not a link.
    assert not (dest / "passwd").is_symlink()
    assert (dest / "passwd").read_text() == "/etc/passwd"
    assert not (dest / "HOOK_RAN").exists()
    verbs = [next(v for v in ("clone", "checkout", "rev-parse") if v in a) for a in real_git_clone]
    assert verbs == ["clone", "checkout", "rev-parse"]


def test_real_clone_oversized_tree_never_checked_out(
    tmp_path: Path, real_git_clone: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """H1(b): a checkout bomb is rejected after the --no-checkout clone, before checkout."""
    monkeypatch.setattr(settings, "SCAN_MAX_FILES", 3)
    dest = tmp_path / "clone"
    with pytest.raises(cloner.CloneError, match="too many files"):
        cloner.clone_repo(URL, "main", dest)
    assert not (dest / "README.md").exists()  # working tree never written
    assert not any("checkout" in a for a in real_git_clone)


def test_real_clone_respects_scan_deadline(tmp_path: Path, real_git_clone: list[list[str]]) -> None:
    """L5: an exhausted scan budget stops the clone before git even starts."""
    with context.scan_context(0), pytest.raises(context.ScanTimeoutError):
        cloner.clone_repo(URL, "main", tmp_path / "clone")
    assert real_git_clone == []


def test_directory_size_ignores_lstat_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a").write_bytes(b"12345")
    (tmp_path / "b").write_bytes(b"123")
    real_lstat = os.lstat

    def _lstat(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        if str(path).endswith("b"):
            raise OSError("vanished")
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(cloner.os, "lstat", _lstat)
    assert cloner.directory_size(tmp_path) == 5


def test_directory_size_does_not_follow_symlinks(tmp_path: Path) -> None:
    big = tmp_path / "outside"
    big.mkdir()
    (big / "huge").write_bytes(b"x" * 10_000)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "small").write_bytes(b"x" * 10)
    (repo / "link").symlink_to(big, target_is_directory=True)
    # Only the 10-byte file plus the size of the symlink entry itself.
    assert cloner.directory_size(repo) < 10_000


# --------------------------------------------------------------------------- github_api

API_URL = "https://api.github.com/repos/octocat/Hello-World"
REPO_JSON: dict[str, Any] = {
    "full_name": "octocat/Hello-World",
    "private": False,
    "size": 1234,
    "default_branch": "master",
}


def _transport(*responses: httpx.Response, seen: list[httpx.Request] | None = None) -> Any:
    queue = list(responses)

    def _handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return queue.pop(0)

    return httpx.MockTransport(_handler)


def _fetch(*responses: httpx.Response, seen: list[httpx.Request] | None = None) -> Any:
    return REAL_FETCH_REPO_METADATA(
        "octocat", "Hello-World", transport=_transport(*responses, seen=seen)
    )


def test_fetch_metadata_success_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "")
    seen: list[httpx.Request] = []
    meta = _fetch(httpx.Response(200, json=REPO_JSON), seen=seen)
    assert meta == github_api.RepoMetadata(
        full_name="octocat/Hello-World", private=False, size_kb=1234, default_branch="master"
    )
    assert meta.clone_url == "https://github.com/octocat/Hello-World"
    assert str(seen[0].url) == API_URL
    assert "authorization" not in seen[0].headers


def test_fetch_metadata_uses_token_only_on_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "ghp_x")
    seen: list[httpx.Request] = []
    _fetch(httpx.Response(200, json=REPO_JSON), seen=seen)
    assert seen[0].headers["authorization"] == "Bearer ghp_x"


def test_fetch_metadata_reports_private_flag() -> None:
    """With a token GitHub may return a private repo: the flag is surfaced for rejection."""
    meta = _fetch(httpx.Response(200, json={**REPO_JSON, "private": True}))
    assert meta.private is True


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (404, github_api.NOT_FOUND_MESSAGE),
        (451, github_api.NOT_FOUND_MESSAGE),
        (403, github_api.RATE_LIMITED_MESSAGE),
        (429, github_api.RATE_LIMITED_MESSAGE),
        (500, github_api.UNREACHABLE_MESSAGE),
    ],
)
def test_fetch_metadata_error_statuses(status: int, message: str) -> None:
    with pytest.raises(github_api.GitHubApiError, match=message):
        _fetch(httpx.Response(status, json={"message": "x"}))


def test_fetch_metadata_follows_api_rename_once() -> None:
    seen: list[httpx.Request] = []
    meta = _fetch(
        httpx.Response(301, headers={"location": "https://api.github.com/repositories/42"}),
        httpx.Response(200, json={**REPO_JSON, "full_name": "new-owner/new-name"}),
        seen=seen,
    )
    assert meta.full_name == "new-owner/new-name"
    assert [str(r.url) for r in seen] == [API_URL, "https://api.github.com/repositories/42"]


def test_fetch_metadata_refuses_offsite_redirect() -> None:
    with pytest.raises(github_api.GitHubApiError, match="not found or is private"):
        _fetch(httpx.Response(301, headers={"location": "https://evil.example/repos/x"}))


def test_fetch_metadata_redirect_chain_not_followed() -> None:
    loc = {"location": "https://api.github.com/repositories/42"}
    with pytest.raises(github_api.GitHubApiError, match="not found or is private"):
        _fetch(httpx.Response(301, headers=loc), httpx.Response(301, headers=loc))


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {**REPO_JSON, "full_name": "../../etc"},
        {**REPO_JSON, "full_name": 5},
        {**REPO_JSON, "size": "big"},
        {**REPO_JSON, "size": True},
        {**REPO_JSON, "size": -1},
        {**REPO_JSON, "private": "no"},
    ],
)
def test_fetch_metadata_rejects_malformed_payload(payload: Any) -> None:
    with pytest.raises(github_api.GitHubApiError, match="Could not reach GitHub"):
        _fetch(httpx.Response(200, json=payload))


def test_fetch_metadata_invalid_json() -> None:
    with pytest.raises(github_api.GitHubApiError, match="Could not reach GitHub"):
        _fetch(httpx.Response(200, content=b"not json"))


@pytest.mark.parametrize("branch", [None, "--upload-pack=x", 7])
def test_fetch_metadata_unsafe_default_branch_dropped(branch: Any) -> None:
    meta = _fetch(httpx.Response(200, json={**REPO_JSON, "default_branch": branch}))
    assert meta.default_branch is None


def test_fetch_metadata_network_error() -> None:
    def _boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    with pytest.raises(github_api.GitHubApiError, match="Could not reach GitHub"):
        REAL_FETCH_REPO_METADATA("o", "r", transport=httpx.MockTransport(_boom))
