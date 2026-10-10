"""Registry of all scanner checks."""

import logging
from pathlib import Path

from app.scanner import context
from app.scanner.checks.committed_env_file import check_committed_env_file
from app.scanner.checks.missing_ci import check_missing_ci
from app.scanner.checks.missing_dependency_manifest import check_missing_dependency_manifest
from app.scanner.checks.missing_dockerfile import check_missing_dockerfile
from app.scanner.checks.missing_env_example import check_missing_env_example
from app.scanner.checks.missing_gitignore import check_missing_gitignore
from app.scanner.checks.missing_license import check_missing_license
from app.scanner.checks.missing_lockfile import check_missing_lockfile
from app.scanner.checks.missing_readme import check_missing_readme
from app.scanner.checks.missing_tests import check_missing_tests
from app.scanner.types import Check, CheckResult

logger = logging.getLogger(__name__)

CHECKS: tuple[Check, ...] = (
    check_missing_readme,
    check_missing_license,
    check_missing_gitignore,
    check_missing_dependency_manifest,
    check_missing_lockfile,
    check_missing_tests,
    check_missing_ci,
    check_missing_dockerfile,
    check_missing_env_example,
    check_committed_env_file,
)


def run_all_checks(repo_root: Path) -> list[CheckResult]:
    """
    Run every registered check against a repository checkout.

    Args:
        repo_root: Path to the cloned repository

    Returns:
        One CheckResult per failed check, in registry order.

    Raises:
        ScanTimeoutError: If the active scan context's deadline passes.
    """
    root = repo_root.resolve()
    results: list[CheckResult] = []
    for check in CHECKS:
        context.check_deadline()
        result = check(root)
        if result is not None:
            results.append(result)
    logger.info("Scanner ran %d checks, %d finding(s)", len(CHECKS), len(results))
    return results
