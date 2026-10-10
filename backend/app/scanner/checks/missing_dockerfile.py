"""Check: repository has container/deployment configuration."""

import fnmatch
from pathlib import Path

from app.models.finding import FindingCategory, Severity
from app.scanner.fs import list_dir, safe_is_file, top_level_dirs
from app.scanner.types import CheckResult

CHECK_ID = "missing_dockerfile"
_PATTERNS = (
    "Dockerfile*",
    "docker-compose*.yml",
    "docker-compose*.yaml",
    "compose*.yml",
    "compose*.yaml",
)


def _is_container_file(name: str) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in _PATTERNS)


def check_missing_dockerfile(repo_root: Path) -> CheckResult | None:
    """Return a CheckResult if no Dockerfile/compose file exists at root or one level deep."""
    root = repo_root.resolve()
    for directory in (root, *top_level_dirs(root)):
        if any(
            _is_container_file(p.name) and safe_is_file(root, p) for p in list_dir(root, directory)
        ):
            return None
    return CheckResult(
        check_id=CHECK_ID,
        category=FindingCategory.deployment,
        severity=Severity.low,
        title="No Dockerfile or Compose file found",
        recommendation=(
            "Add a Dockerfile (and optionally a docker-compose.yml for local services such as "
            "the database) so the application can be built and run the same way in every "
            "environment."
        ),
    )
