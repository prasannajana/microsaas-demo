"""Check: repository contains automated tests."""

import fnmatch
from pathlib import Path

from app.models.finding import FindingCategory, Severity
from app.scanner.fs import walk_dirs, walk_files
from app.scanner.types import CheckResult

CHECK_ID = "missing_tests"
TEST_DIR_NAMES = frozenset({"tests", "test", "__tests__"})
TEST_FILE_PATTERNS = (
    "test_*.py",
    "*_test.py",
    "*_test.go",
    "*.test.js",
    "*.test.jsx",
    "*.test.ts",
    "*.test.tsx",
    "*.spec.js",
    "*.spec.jsx",
    "*.spec.ts",
    "*.spec.tsx",
)


def _is_test_file(name: str) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in TEST_FILE_PATTERNS)


def check_missing_tests(repo_root: Path) -> CheckResult | None:
    """Return a CheckResult if no test directory or test file is found, else None."""
    root = repo_root.resolve()
    if any(d.name in TEST_DIR_NAMES for d in walk_dirs(root)):
        return None
    if any(_is_test_file(f.name) for f in walk_files(root)):
        return None
    return CheckResult(
        check_id=CHECK_ID,
        category=FindingCategory.testing,
        severity=Severity.critical,
        title="No automated tests found",
        recommendation=(
            "Add automated tests in a tests/ directory (e.g. pytest test_*.py files for Python, "
            "*.test.ts files with Vitest/Jest for JavaScript, *_test.go for Go) covering the "
            "core behaviour, and document how to run them in the README."
        ),
    )
