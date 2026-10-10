"""Check: repository declares its dependencies in a manifest file."""

from pathlib import Path

from app.models.finding import FindingCategory, Severity
from app.scanner.checks.manifests import find_manifests
from app.scanner.types import CheckResult

CHECK_ID = "missing_dependency_manifest"


def check_missing_dependency_manifest(repo_root: Path) -> CheckResult | None:
    """Return a CheckResult if no dependency manifest exists at root or one level deep."""
    root = repo_root.resolve()
    if find_manifests(root):
        return None
    return CheckResult(
        check_id=CHECK_ID,
        category=FindingCategory.dependencies,
        severity=Severity.critical,
        title="No dependency manifest found",
        recommendation=(
            "Declare the project's dependencies in a manifest for its ecosystem, e.g. "
            "requirements.txt or pyproject.toml (Python), package.json (Node.js), go.mod (Go), "
            "Cargo.toml (Rust), pom.xml / build.gradle (Java), Gemfile (Ruby) or composer.json "
            "(PHP), with pinned versions so the project can be installed reproducibly."
        ),
    )
