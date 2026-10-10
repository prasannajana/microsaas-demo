"""Check: no real .env file with secrets is committed to the repository."""

from pathlib import Path

from app.models.finding import FindingCategory, Severity
from app.scanner.fs import rel, walk_files
from app.scanner.types import CheckResult

CHECK_ID = "committed_env_file"
ENV_FILE_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".env.production.local",
        ".env.development.local",
        ".env.prod",
    }
)


def check_committed_env_file(repo_root: Path) -> CheckResult | None:
    """Return a CheckResult for the first committed .env-style file found, else None."""
    root = repo_root.resolve()
    for path in walk_files(root):
        if path.name in ENV_FILE_NAMES:
            location = rel(root, path)
            return CheckResult(
                check_id=CHECK_ID,
                category=FindingCategory.configuration,
                severity=Severity.critical,
                title=f"Environment file committed: {location}",
                recommendation=(
                    f"Remove {location} from the repository (git rm --cached {location}), add "
                    "it to .gitignore, commit a .env.example with placeholder values instead, "
                    "and rotate any credentials it contained — they remain in git history."
                ),
                file_path=location,
            )
    return None
