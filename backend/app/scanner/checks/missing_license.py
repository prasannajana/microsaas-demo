"""Check: repository has a LICENSE / COPYING file at its root."""

from pathlib import Path

from app.models.finding import FindingCategory, Severity
from app.scanner.fs import root_files
from app.scanner.types import CheckResult

CHECK_ID = "missing_license"
_PREFIXES = ("LICENSE", "LICENCE", "COPYING")


def check_missing_license(repo_root: Path) -> CheckResult | None:
    """Return a CheckResult if there is no LICENSE*/COPYING* file at the repo root, else None."""
    root = repo_root.resolve()
    if any(p.name.upper().startswith(_PREFIXES) for p in root_files(root)):
        return None
    return CheckResult(
        check_id=CHECK_ID,
        category=FindingCategory.documentation,
        severity=Severity.medium,
        title="No license file found",
        recommendation=(
            "Add a LICENSE file at the repository root (for example MIT or Apache-2.0; "
            "see https://choosealicense.com) so others know how they may use the code."
        ),
    )
