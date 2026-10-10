"""Check: repository has a .gitignore at its root."""

from pathlib import Path

from app.models.finding import FindingCategory, Severity
from app.scanner.fs import safe_is_file
from app.scanner.types import CheckResult

CHECK_ID = "missing_gitignore"


def check_missing_gitignore(repo_root: Path) -> CheckResult | None:
    """Return a CheckResult if there is no .gitignore at the repo root, else None."""
    root = repo_root.resolve()
    if safe_is_file(root, root / ".gitignore"):
        return None
    return CheckResult(
        check_id=CHECK_ID,
        category=FindingCategory.configuration,
        severity=Severity.medium,
        title="No .gitignore found",
        recommendation=(
            "Add a .gitignore at the repository root that excludes build output, "
            "dependency folders (node_modules, .venv), editor files and secrets such as .env. "
            "Templates are available at https://github.com/github/gitignore."
        ),
    )
