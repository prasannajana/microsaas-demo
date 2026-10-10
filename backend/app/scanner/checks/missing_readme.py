"""Check: repository has a README at its root."""

from pathlib import Path

from app.models.finding import FindingCategory, Severity
from app.scanner.fs import root_files
from app.scanner.types import CheckResult

CHECK_ID = "missing_readme"


def check_missing_readme(repo_root: Path) -> CheckResult | None:
    """Return a CheckResult if there is no README* file at the repo root, else None."""
    root = repo_root.resolve()
    if any(p.name.upper().startswith("README") for p in root_files(root)):
        return None
    return CheckResult(
        check_id=CHECK_ID,
        category=FindingCategory.documentation,
        severity=Severity.high,
        title="No README found",
        recommendation=(
            "Add a README.md at the repository root describing what the project does, "
            "how to install it, how to run it, and how to run its tests."
        ),
    )
