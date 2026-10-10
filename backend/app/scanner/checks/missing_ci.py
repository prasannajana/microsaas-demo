"""Check: repository has a continuous-integration configuration."""

from pathlib import Path

from app.models.finding import FindingCategory, Severity
from app.scanner.fs import list_dir, safe_is_file
from app.scanner.types import CheckResult

CHECK_ID = "missing_ci"
_ROOT_CI_FILES = (".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile")


def check_missing_ci(repo_root: Path) -> CheckResult | None:
    """Return a CheckResult if no CI configuration is found, else None."""
    root = repo_root.resolve()
    workflows = list_dir(root, root / ".github" / "workflows")
    if any(p.suffix in (".yml", ".yaml") and safe_is_file(root, p) for p in workflows):
        return None
    if any(safe_is_file(root, root / name) for name in _ROOT_CI_FILES):
        return None
    if safe_is_file(root, root / ".circleci" / "config.yml"):
        return None
    return CheckResult(
        check_id=CHECK_ID,
        category=FindingCategory.ci_cd,
        severity=Severity.high,
        title="No CI pipeline configured",
        recommendation=(
            "Add a continuous-integration workflow, e.g. .github/workflows/ci.yml for GitHub "
            "Actions, that installs dependencies, runs the linter and runs the test suite on "
            "every push and pull request."
        ),
    )
