"""Scanner engine unit tests: checks, scoring, language detection, path guards, cloner.

No database and no network: checks run against fixture repos (copied into tmp_path
when a test needs to mutate them) and the cloner runs with git (``cloner._run_git`` /
``cloner.tree_stats``) and the GitHub metadata API mocked.
"""

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.config import settings
from app.models.finding import FindingCategory, Severity
from app.scanner import cloner, github_api
from app.scanner.checks.committed_env_file import check_committed_env_file
from app.scanner.checks.missing_ci import check_missing_ci
from app.scanner.checks.missing_dependency_manifest import check_missing_dependency_manifest
from app.scanner.checks.missing_dockerfile import check_missing_dockerfile
from app.scanner.checks.missing_env_example import (
    MAX_SOURCE_BYTES,
    check_missing_env_example,
)
from app.scanner.checks.missing_gitignore import check_missing_gitignore
from app.scanner.checks.missing_license import check_missing_license
from app.scanner.checks.missing_lockfile import check_missing_lockfile
from app.scanner.checks.missing_readme import check_missing_readme
from app.scanner.checks.missing_tests import check_missing_tests
from app.scanner.fs import is_inside, walk_files
from app.scanner.language import detect_primary_language
from app.scanner.registry import CHECKS, run_all_checks
from app.scanner.scoring import compute_score
from app.scanner.types import CheckResult
from app.scanner.urls import (
    InvalidRepoUrlError,
    is_valid_branch,
    is_valid_github_url,
    normalize_github_url,
    split_github_url,
)
from tests.conftest import fake_metadata

FIXTURES = Path(__file__).parent / "fixtures" / "repos"

ALL_CHECK_IDS = {
    "missing_readme",
    "missing_license",
    "missing_gitignore",
    "missing_dependency_manifest",
    "missing_lockfile",
    "missing_tests",
    "missing_ci",
    "missing_dockerfile",
    "missing_env_example",
    "committed_env_file",
}


@pytest.fixture
def complete_copy(tmp_path: Path) -> Path:
    """A mutable copy of the `complete` fixture repo."""
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURES / "complete", dest)
    return dest


def _ids(results: list[CheckResult]) -> set[str]:
    return {r.check_id for r in results}


# --------------------------------------------------------------------------- registry


def test_registry_has_all_ten_checks() -> None:
    assert len(CHECKS) == 10


def test_complete_fixture_passes_every_check() -> None:
    results = run_all_checks(FIXTURES / "complete")
    assert results == []
    assert compute_score(results) == 100


def test_empty_fixture_findings_and_score() -> None:
    results = run_all_checks(FIXTURES / "empty")
    assert _ids(results) == {
        "missing_readme",
        "missing_license",
        "missing_gitignore",
        "missing_dependency_manifest",
        "missing_tests",
        "missing_ci",
        "missing_dockerfile",
    }
    # 15 + 8 + 8 + 25 + 25 + 15 + 3 = 99
    assert compute_score(results) == 1


def test_committed_env_fixture() -> None:
    result = check_committed_env_file(FIXTURES / "committed_env")
    assert result is not None
    assert result.check_id == "committed_env_file"
    assert result.severity is Severity.critical
    assert result.category is FindingCategory.configuration
    assert result.file_path == "app/.env"


def test_every_finding_has_metadata() -> None:
    # Most checks fire across these two fixtures.
    results = run_all_checks(FIXTURES / "empty") + run_all_checks(FIXTURES / "committed_env")
    for r in results:
        assert r.check_id in ALL_CHECK_IDS
        assert isinstance(r.category, FindingCategory)
        assert isinstance(r.severity, Severity)
        assert r.title
        assert len(r.recommendation) > 40


# --------------------------------------------------------------------------- per check

EXPECTED_META: dict[str, tuple[FindingCategory, Severity]] = {
    "missing_readme": (FindingCategory.documentation, Severity.high),
    "missing_license": (FindingCategory.documentation, Severity.medium),
    "missing_gitignore": (FindingCategory.configuration, Severity.medium),
    "missing_dependency_manifest": (FindingCategory.dependencies, Severity.critical),
    "missing_lockfile": (FindingCategory.dependencies, Severity.low),
    "missing_tests": (FindingCategory.testing, Severity.critical),
    "missing_ci": (FindingCategory.ci_cd, Severity.high),
    "missing_dockerfile": (FindingCategory.deployment, Severity.low),
    "missing_env_example": (FindingCategory.configuration, Severity.medium),
    "committed_env_file": (FindingCategory.configuration, Severity.critical),
}


def _remove(repo: Path, *names: str) -> None:
    for name in names:
        target = repo / name
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()


@pytest.mark.parametrize(
    ("removed", "check", "check_id"),
    [
        (("README.md",), check_missing_readme, "missing_readme"),
        (("LICENSE",), check_missing_license, "missing_license"),
        ((".gitignore",), check_missing_gitignore, "missing_gitignore"),
        (
            ("requirements.txt", "package.json", "package-lock.json"),
            check_missing_dependency_manifest,
            "missing_dependency_manifest",
        ),
        (("package-lock.json",), check_missing_lockfile, "missing_lockfile"),
        (("tests",), check_missing_tests, "missing_tests"),
        ((".github",), check_missing_ci, "missing_ci"),
        (("Dockerfile",), check_missing_dockerfile, "missing_dockerfile"),
        ((".env.example",), check_missing_env_example, "missing_env_example"),
    ],
)
def test_check_fires_when_item_removed(
    complete_copy: Path,
    removed: tuple[str, ...],
    check: Callable[[Path], CheckResult | None],
    check_id: str,
) -> None:
    assert check(complete_copy) is None
    _remove(complete_copy, *removed)
    result = check(complete_copy)
    assert result is not None
    assert result.check_id == check_id
    assert (result.category, result.severity) == EXPECTED_META[check_id]
    # Exactly this one check fails across the whole registry.
    assert _ids(run_all_checks(complete_copy)) == {check_id}


def test_readme_and_license_variants(tmp_path: Path) -> None:
    (tmp_path / "readme.rst").write_text("x")
    (tmp_path / "COPYING").write_text("x")
    assert check_missing_readme(tmp_path) is None
    assert check_missing_license(tmp_path) is None


def test_readme_directory_does_not_count(tmp_path: Path) -> None:
    (tmp_path / "README").mkdir()
    assert check_missing_readme(tmp_path) is not None


def test_manifest_one_level_deep_counts(tmp_path: Path) -> None:
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "go.mod").write_text("module x\n")
    assert check_missing_dependency_manifest(tmp_path) is None
    # go.mod without requirements needs no go.sum
    assert check_missing_lockfile(tmp_path) is None


def test_manifest_two_levels_deep_does_not_count(tmp_path: Path) -> None:
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "package.json").write_text("{}")
    assert check_missing_dependency_manifest(tmp_path) is not None


def test_manifest_in_skipped_dir_does_not_count(tmp_path: Path) -> None:
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "package.json").write_text("{}")
    assert check_missing_dependency_manifest(tmp_path) is not None


def test_lockfile_skipped_for_requirements_only(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("requests\n")
    assert check_missing_lockfile(tmp_path) is None


def test_lockfile_skipped_without_manifest(tmp_path: Path) -> None:
    assert check_missing_lockfile(tmp_path) is None


def test_lockfile_reports_manifest_path(tmp_path: Path) -> None:
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "package.json").write_text("{}")
    result = check_missing_lockfile(tmp_path)
    assert result is not None
    assert result.file_path == "web/package.json"
    (tmp_path / "web" / "yarn.lock").write_text("")
    assert check_missing_lockfile(tmp_path) is None


def test_lockfile_poetry_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    assert check_missing_lockfile(tmp_path) is None  # plain PEP 621: no lock expected
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname='x'\n")
    assert check_missing_lockfile(tmp_path) is not None
    (tmp_path / "poetry.lock").write_text("")
    assert check_missing_lockfile(tmp_path) is None


@pytest.mark.parametrize(
    "relpath",
    [
        "test/x.txt",
        "src/__tests__/x.js",
        "pkg/test_mod.py",
        "pkg/mod_test.py",
        "cmd/main_test.go",
        "web/App.test.tsx",
        "web/util.spec.js",
    ],
)
def test_tests_detected(tmp_path: Path, relpath: str) -> None:
    target = tmp_path / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x")
    assert check_missing_tests(tmp_path) is None


def test_tests_in_node_modules_ignored(tmp_path: Path) -> None:
    (tmp_path / "node_modules" / "lib" / "tests").mkdir(parents=True)
    (tmp_path / "node_modules" / "lib" / "a.test.js").write_text("x")
    assert check_missing_tests(tmp_path) is not None


@pytest.mark.parametrize(
    "relpath",
    [
        ".github/workflows/build.yaml",
        ".gitlab-ci.yml",
        ".circleci/config.yml",
        "azure-pipelines.yml",
        "Jenkinsfile",
    ],
)
def test_ci_variants(tmp_path: Path, relpath: str) -> None:
    target = tmp_path / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x")
    assert check_missing_ci(tmp_path) is None


def test_ci_workflows_dir_without_yaml(tmp_path: Path) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "README.md").write_text("x")
    assert check_missing_ci(tmp_path) is not None


@pytest.mark.parametrize(
    "relpath",
    ["Dockerfile.prod", "docker-compose.yml", "compose.yaml", "backend/Dockerfile"],
)
def test_docker_variants(tmp_path: Path, relpath: str) -> None:
    target = tmp_path / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x")
    assert check_missing_dockerfile(tmp_path) is None


def test_env_example_not_needed_without_env_usage(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hi')\n")
    assert check_missing_env_example(tmp_path) is None


@pytest.mark.parametrize(
    "source",
    [
        ("a.py", "import os\nos.environ['X']\n"),
        ("a.js", "const x = process.env.X\n"),
        ("a.ts", "const x = import.meta.env.VITE_X\n"),
    ],
)
def test_env_example_needed_with_env_usage(tmp_path: Path, source: tuple[str, str]) -> None:
    name, text = source
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / name).write_text(text)
    result = check_missing_env_example(tmp_path)
    assert result is not None
    assert result.file_path == f"src/{name}"
    (tmp_path / ".env.sample").write_text("X=\n")
    assert check_missing_env_example(tmp_path) is None


def test_env_scan_ignores_large_and_binary_files(tmp_path: Path) -> None:
    (tmp_path / "big.py").write_text("os.getenv('X')\n" + "#" * MAX_SOURCE_BYTES)
    (tmp_path / "bin.py").write_bytes(b"\xff\xfe\x00\x81 nothing here")
    assert check_missing_env_example(tmp_path) is None


def test_env_scan_limited_to_max_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.scanner.checks import missing_env_example

    monkeypatch.setattr(missing_env_example, "MAX_SOURCE_FILES", 3)
    for i in range(3):
        (tmp_path / f"a{i}.py").write_text("x = 1\n")
    (tmp_path / "z.py").write_text("os.getenv('X')\n")  # sorted last, beyond the cap
    assert check_missing_env_example(tmp_path) is None


@pytest.mark.parametrize("name", [".env.example", ".env.sample", ".env.template"])
def test_env_templates_are_not_committed_env(tmp_path: Path, name: str) -> None:
    (tmp_path / name).write_text("X=\n")
    assert check_committed_env_file(tmp_path) is None


@pytest.mark.parametrize("name", [".env", ".env.local", ".env.production"])
def test_committed_env_variants(tmp_path: Path, name: str) -> None:
    (tmp_path / name).write_text("X=1\n")
    result = check_committed_env_file(tmp_path)
    assert result is not None
    assert result.file_path == name


def test_env_inside_git_dir_ignored(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / ".env").write_text("X=1\n")
    assert check_committed_env_file(tmp_path) is None


# --------------------------------------------------------------------------- symlink guard


def test_symlinked_readme_outside_repo_is_ignored(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "README.md").write_text("secret")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").symlink_to(outside / "README.md")
    assert not is_inside(repo.resolve(), repo / "README.md")
    assert check_missing_readme(repo) is not None


def test_symlinked_readme_inside_repo_counts(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "intro.md").write_text("x")
    (tmp_path / "README.md").symlink_to(tmp_path / "docs" / "intro.md")
    assert check_missing_readme(tmp_path) is None


def test_symlinked_dir_escape_not_walked(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    (outside / "tests").mkdir(parents=True)
    (outside / ".env").write_text("SECRET=1\n")
    (outside / "app.py").write_text("os.getenv('X')\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "link").symlink_to(outside, target_is_directory=True)
    (repo / "env_link.py").symlink_to(outside / "app.py")

    walked = list(walk_files(repo.resolve()))
    assert walked == []
    assert check_committed_env_file(repo) is None
    assert check_missing_tests(repo) is not None
    assert check_missing_env_example(repo) is None
    # A symlinked directory is not treated as a CI directory either.
    (outside / "workflows").mkdir()
    (outside / "workflows" / "ci.yml").write_text("x")
    (repo / ".github").symlink_to(outside, target_is_directory=True)
    assert check_missing_ci(repo) is not None


def test_symlink_loop_does_not_hang(tmp_path: Path) -> None:
    (tmp_path / "loop").symlink_to(tmp_path, target_is_directory=True)
    assert detect_primary_language(tmp_path) is None
    assert check_missing_tests(tmp_path) is not None


# --------------------------------------------------------------------------- scoring


def _result(severity: Severity) -> CheckResult:
    return CheckResult("x", FindingCategory.testing, severity, "t", "r")


def test_score_weights() -> None:
    assert compute_score([]) == 100
    assert compute_score([_result(Severity.critical)]) == 75
    assert compute_score([_result(Severity.high)]) == 85
    assert compute_score([_result(Severity.medium)]) == 92
    assert compute_score([_result(Severity.low)]) == 97
    assert compute_score([_result(Severity.critical), _result(Severity.low)]) == 72


def test_score_floored_at_zero() -> None:
    assert compute_score([_result(Severity.critical)] * 5) == 0


# --------------------------------------------------------------------------- language


def test_detect_language_complete_fixture() -> None:
    assert detect_primary_language(FIXTURES / "complete") == "Python"


def test_detect_language_majority(tmp_path: Path) -> None:
    for i in range(3):
        (tmp_path / f"a{i}.ts").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "node_modules").mkdir()
    for i in range(10):
        (tmp_path / "node_modules" / f"c{i}.js").write_text("")
    assert detect_primary_language(tmp_path) == "TypeScript"


def test_detect_language_none(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("")
    assert detect_primary_language(tmp_path) is None


# --------------------------------------------------------------------------- URL validation


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://github.com/octocat/Hello-World", "https://github.com/octocat/Hello-World"),
        ("  https://GitHub.com/octocat/Hello-World/  ", "https://github.com/octocat/Hello-World"),
        ("https://github.com/octocat/Hello-World.git", "https://github.com/octocat/Hello-World"),
        ("https://github.com/a.b/c_d-e.git/", "https://github.com/a.b/c_d-e"),
    ],
)
def test_normalize_github_url_valid(raw: str, expected: str) -> None:
    assert normalize_github_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "http://github.com/a/b",
        "https://gitlab.com/a/b",
        "https://github.com/a",
        "https://github.com/a/b/c",
        "https://github.com/a/b?x=1",
        "https://github.com/a/b#frag",
        "https://user:pw@github.com/a/b",
        "https://github.com:443/a/b",
        "https://github.com/../..",
        "https://github.com/a/b;rm -rf",
        "git@github.com:a/b.git",
        "file:///etc/passwd",
        "https://github.com.evil.com/a/b",
        "--upload-pack=x",
    ],
)
def test_normalize_github_url_invalid(raw: str) -> None:
    with pytest.raises(InvalidRepoUrlError):
        normalize_github_url(raw)


@pytest.mark.parametrize("branch", ["main", "release/1.2", "feat_x-y"])
def test_valid_branch(branch: str) -> None:
    assert is_valid_branch(branch)


@pytest.mark.parametrize(
    "branch", ["-x", "--upload-pack=x", "a..b", "a b", ".hidden", "a/", "main\n", "caf\u00e9"]
)
def test_invalid_branch(branch: str) -> None:
    assert not is_valid_branch(branch)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/a/b\n",  # `$` alone would accept a trailing newline
        "https://github.com/a/b\n/x",
        "https://github.com/\u0430/b",  # Cyrillic "a": \\w is ASCII-only
        "https://github.com/a/b\u0661",  # Arabic-Indic digit
        " https://github.com/a/b",
    ],
)
def test_is_valid_github_url_ascii_fullmatch(url: str) -> None:
    assert not is_valid_github_url(url)


@pytest.mark.parametrize("raw", ["https://github.com/a/b\n\n/x", "https://github.com/\u00e9/b"])
def test_normalize_rejects_non_ascii_and_embedded_newline(raw: str) -> None:
    with pytest.raises(InvalidRepoUrlError):
        normalize_github_url(raw)


def test_split_github_url() -> None:
    assert split_github_url("https://github.com/octo/repo") == ("octo", "repo")
    with pytest.raises(InvalidRepoUrlError):
        split_github_url("https://github.com/octo/repo\n")


# --------------------------------------------------------------------------- cloner

SHA = "a" * 40
URL = "https://github.com/octocat/Hello-World"


class FakeGit:
    """Replaces cloner._run_git: records argv and fakes clone / checkout / rev-parse."""

    def __init__(
        self,
        clone_rc: int = 0,
        clone_stderr: str = "",
        timeout_on: str | None = None,
        missing_on: str | None = None,
        checkout_rc: int = 0,
        rev_rc: int = 0,
        rev_stdout: str = SHA + "\n",
    ) -> None:
        self.clone_rc = clone_rc
        self.clone_stderr = clone_stderr
        self.timeout_on = timeout_on
        self.missing_on = missing_on
        self.checkout_rc = checkout_rc
        self.rev_rc = rev_rc
        self.rev_stdout = rev_stdout
        self.calls: list[tuple[list[str], float, dict[str, str]]] = []

    @staticmethod
    def _verb(args: list[str]) -> str:
        for verb in ("clone", "checkout", "rev-parse"):
            if verb in args:
                return verb
        raise AssertionError(f"unexpected command {args}")

    def __call__(
        self, args: list[str], timeout: float, env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        assert isinstance(args, list)
        self.calls.append((args, timeout, env))
        verb = self._verb(args)
        if verb == self.timeout_on:
            raise subprocess.TimeoutExpired(args, timeout)
        if verb == self.missing_on:
            raise FileNotFoundError("git")
        if verb == "clone":
            if self.clone_rc == 0:
                dest = Path(args[-1])
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "README.md").write_bytes(b"x" * 10)
            return subprocess.CompletedProcess(args, self.clone_rc, "", self.clone_stderr)
        if verb == "checkout":
            return subprocess.CompletedProcess(args, self.checkout_rc, "", "error: boom")
        return subprocess.CompletedProcess(args, self.rev_rc, self.rev_stdout, "")

    def argv(self, verb: str) -> list[str]:
        return next(a for a, _t, _e in self.calls if self._verb(a) == verb)


@pytest.fixture
def tree_calls(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Fake tree_stats (the real one is exercised against real git in test_scanner_safety)."""
    calls: list[Path] = []

    def _stats(repo_dir: Path, env: dict[str, str], timeout: float) -> tuple[int, int]:
        calls.append(repo_dir)
        return 1, 10

    monkeypatch.setattr(cloner, "tree_stats", _stats)
    return calls


def _patch(monkeypatch: pytest.MonkeyPatch, fake: FakeGit) -> FakeGit:
    monkeypatch.setattr(cloner, "_run_git", fake)
    return fake


def _metadata(monkeypatch: pytest.MonkeyPatch, **kw: Any) -> None:
    monkeypatch.setattr(
        github_api,
        "fetch_repo_metadata",
        lambda owner, repo, **_k: fake_metadata(owner, repo, **kw),
    )


def test_clone_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tree_calls: list[Path],
    github_metadata: list[tuple[str, str]],
) -> None:
    fake = _patch(monkeypatch, FakeGit())
    dest = tmp_path / "repo"
    result = cloner.clone_repo(URL, "dev", dest)
    assert result.commit_sha == SHA
    assert result.size_bytes == 10
    assert github_metadata == [("octocat", "Hello-World")]
    assert tree_calls == [dest]

    # clone -> (tree check) -> checkout -> rev-parse, in that order
    assert [fake._verb(a) for a, _t, _e in fake.calls] == ["clone", "checkout", "rev-parse"]
    args = fake.argv("clone")
    assert args[0] == "git"
    assert args[-3:] == ["--", URL, str(dest)]
    for flag in ("--no-checkout", "--depth", "1", "--single-branch", "--no-tags"):
        assert flag in args
    assert args[args.index("--branch") + 1] == "dev"
    for _args, timeout, env in fake.calls:
        assert 0 < timeout <= settings.SCAN_CLONE_TIMEOUT_SECONDS
        assert env["GIT_TERMINAL_PROMPT"] == "0"
        assert env["GIT_LFS_SKIP_SMUDGE"] == "1"


def test_clone_uses_api_default_branch_when_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tree_calls: list[Path]
) -> None:
    _metadata(monkeypatch, default_branch="trunk")
    fake = _patch(monkeypatch, FakeGit())
    cloner.clone_repo(URL, None, tmp_path / "repo")
    args = fake.argv("clone")
    assert args[args.index("--branch") + 1] == "trunk"


def test_clone_without_any_branch_omits_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tree_calls: list[Path]
) -> None:
    _metadata(monkeypatch, default_branch=None)
    fake = _patch(monkeypatch, FakeGit())
    cloner.clone_repo(URL, None, tmp_path / "repo")
    assert "--branch" not in fake.argv("clone")


def test_clone_uses_canonical_name_from_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tree_calls: list[Path]
) -> None:
    """A renamed repo is cloned under its canonical name (git never follows redirects)."""
    monkeypatch.setattr(
        github_api, "fetch_repo_metadata", lambda o, r, **_k: fake_metadata("new-owner", "new-name")
    )
    fake = _patch(monkeypatch, FakeGit())
    cloner.clone_repo(URL, None, tmp_path / "repo")
    assert "https://github.com/new-owner/new-name" in fake.argv("clone")


def test_clone_never_sends_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tree_calls: list[Path]
) -> None:
    """H2: GITHUB_TOKEN is never passed to git (argv or environment)."""
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "ghp_secret_token_value")
    fake = _patch(monkeypatch, FakeGit())
    cloner.clone_repo(URL, None, tmp_path / "repo")
    for args, _timeout, env in fake.calls:
        assert not any("ghp_secret_token_value" in a for a in args)
        assert not any("ghp_secret_token_value" in v for v in env.values())
        assert not any(k.startswith("GIT_CONFIG_KEY") for k in env)


def test_clone_rejects_private_repo_before_cloning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tree_calls: list[Path]
) -> None:
    _metadata(monkeypatch, private=True)
    fake = _patch(monkeypatch, FakeGit())
    with pytest.raises(cloner.CloneError, match="not found or is private"):
        cloner.clone_repo(URL, None, tmp_path / "repo")
    assert fake.calls == []


def test_clone_rejects_oversized_repo_before_cloning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tree_calls: list[Path]
) -> None:
    monkeypatch.setattr(settings, "SCAN_MAX_REPO_SIZE_MB", 1)
    _metadata(monkeypatch, size_kb=1025)
    fake = _patch(monkeypatch, FakeGit())
    with pytest.raises(cloner.CloneError, match=r"exceeds size limit \(1 MB\)"):
        cloner.clone_repo(URL, None, tmp_path / "repo")
    assert fake.calls == []


@pytest.mark.parametrize("message", [github_api.NOT_FOUND_MESSAGE, github_api.RATE_LIMITED_MESSAGE])
def test_clone_maps_api_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, message: str
) -> None:
    def _raise(owner: str, repo: str, **_k: Any) -> github_api.RepoMetadata:
        raise github_api.GitHubApiError(message)

    monkeypatch.setattr(github_api, "fetch_repo_metadata", _raise)
    fake = _patch(monkeypatch, FakeGit())
    with pytest.raises(cloner.CloneError, match=message):
        cloner.clone_repo(URL, None, tmp_path / "repo")
    assert fake.calls == []


def test_clone_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        FakeGit(clone_rc=128, clone_stderr="remote: Repository not found.\nfatal: ..."),
    )
    with pytest.raises(cloner.CloneError, match="not found or is private"):
        cloner.clone_repo(URL, None, tmp_path / "repo")


def test_clone_private_prompt_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        FakeGit(
            clone_rc=128,
            clone_stderr="fatal: could not read Username for 'https://github.com': "
            "terminal prompts disabled",
        ),
    )
    with pytest.raises(cloner.CloneError, match="not found or is private"):
        cloner.clone_repo(URL, None, tmp_path / "repo")


def test_clone_branch_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        FakeGit(clone_rc=128, clone_stderr="fatal: Remote branch nope not found in upstream"),
    )
    with pytest.raises(cloner.CloneError, match="Branch 'nope' was not found"):
        cloner.clone_repo(URL, "nope", tmp_path / "repo")


def test_clone_empty_repo_default_branch_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GitHub reports `main` for a repo with no commits; say it's empty, not 'branch missing'."""
    _metadata(monkeypatch, default_branch="main", size_kb=0)
    _patch(
        monkeypatch,
        FakeGit(clone_rc=128, clone_stderr="fatal: Remote branch main not found in upstream"),
    )
    with pytest.raises(cloner.CloneError, match="repository is empty"):
        cloner.clone_repo(URL, None, tmp_path / "repo")


def test_clone_empty_repo_with_explicit_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _metadata(monkeypatch, size_kb=0)
    _patch(
        monkeypatch,
        FakeGit(clone_rc=128, clone_stderr="fatal: Remote branch dev not found in upstream origin"),
    )
    with pytest.raises(cloner.CloneError, match="repository is empty"):
        cloner.clone_repo(URL, "dev", tmp_path / "repo")


@pytest.mark.parametrize("verb", ["clone", "checkout", "rev-parse"])
def test_clone_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tree_calls: list[Path], verb: str
) -> None:
    _patch(monkeypatch, FakeGit(timeout_on=verb))
    with pytest.raises(cloner.CloneError, match="timed out"):
        cloner.clone_repo(URL, None, tmp_path / "repo")


def test_clone_budget_exhausted_between_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The clone timeout covers clone + tree check + checkout, not each step separately."""
    monkeypatch.setattr(settings, "SCAN_CLONE_TIMEOUT_SECONDS", 0)
    fake = _patch(monkeypatch, FakeGit())
    with pytest.raises(cloner.CloneError, match="timed out after 0 seconds"):
        cloner.clone_repo(URL, None, tmp_path / "repo")
    assert fake.calls == []


def test_clone_oversize_tree_blocks_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the tree check fails, checkout never runs."""

    def _too_big(repo_dir: Path, env: dict[str, str], timeout: float) -> tuple[int, int]:
        raise cloner.CloneError("Repository exceeds size limit (200 MB)")

    monkeypatch.setattr(cloner, "tree_stats", _too_big)
    fake = _patch(monkeypatch, FakeGit())
    with pytest.raises(cloner.CloneError, match="exceeds size limit"):
        cloner.clone_repo(URL, None, tmp_path / "repo")
    assert [fake._verb(a) for a, _t, _e in fake.calls] == ["clone"]


def test_clone_checkout_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tree_calls: list[Path]
) -> None:
    _patch(monkeypatch, FakeGit(checkout_rc=1))
    with pytest.raises(cloner.CloneError, match="Failed to check out"):
        cloner.clone_repo(URL, None, tmp_path / "repo")


def test_clone_generic_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, FakeGit(clone_rc=1, clone_stderr="fatal: something odd"))
    with pytest.raises(cloner.CloneError, match="Failed to clone repository"):
        cloner.clone_repo(URL, None, tmp_path / "repo")


@pytest.mark.parametrize(
    ("url", "branch"),
    [
        ("https://gitlab.com/a/b", None),
        ("file:///etc", None),
        (URL + "\n", None),
        (URL, "--upload-pack=touch /tmp/x"),
    ],
)
def test_clone_revalidates_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    github_metadata: list[tuple[str, str]],
    url: str,
    branch: str | None,
) -> None:
    fake = _patch(monkeypatch, FakeGit())
    with pytest.raises(cloner.CloneError, match="Invalid"):
        cloner.clone_repo(url, branch, tmp_path / "repo")
    assert fake.calls == []
    assert github_metadata == []


@pytest.mark.parametrize("verb", ["clone", "checkout", "rev-parse"])
def test_clone_git_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tree_calls: list[Path], verb: str
) -> None:
    _patch(monkeypatch, FakeGit(missing_on=verb))
    with pytest.raises(cloner.CloneError, match="Git is not available"):
        cloner.clone_repo(URL, None, tmp_path / "repo")


@pytest.mark.parametrize(
    ("rev_rc", "rev_stdout"),
    [(128, ""), (0, "not-a-sha\n"), (0, "A" * 40), (0, "a" * 39), (0, "a" * 40 + "\nx")],
)
def test_clone_rev_parse_bad_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tree_calls: list[Path],
    rev_rc: int,
    rev_stdout: str,
) -> None:
    _patch(monkeypatch, FakeGit(rev_rc=rev_rc, rev_stdout=rev_stdout))
    with pytest.raises(cloner.CloneError, match="Failed to read the repository commit"):
        cloner.clone_repo(URL, None, tmp_path / "repo")
