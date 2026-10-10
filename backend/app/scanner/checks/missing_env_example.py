"""Check: projects that read environment variables ship an env template."""

from pathlib import Path

from app.models.finding import FindingCategory, Severity
from app.scanner.fs import rel, safe_is_file, top_level_dirs, walk_files
from app.scanner.types import CheckResult

CHECK_ID = "missing_env_example"
TEMPLATE_NAMES = (".env.example", ".env.sample", ".env.template")
SOURCE_EXTENSIONS = frozenset(
    {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".vue", ".svelte"}
)
ENV_PATTERNS = ("os.environ", "os.getenv", "process.env", "import.meta.env")
MAX_SOURCE_FILES = 2_000
MAX_SOURCE_BYTES = 1024 * 1024


def _has_template(root: Path) -> bool:
    for directory in (root, *top_level_dirs(root)):
        if any(safe_is_file(root, directory / name) for name in TEMPLATE_NAMES):
            return True
    return False


def find_env_reference(root: Path) -> Path | None:
    """
    Return the first source file that references environment variables, or None.

    Scans at most MAX_SOURCE_FILES source files of at most MAX_SOURCE_BYTES each;
    undecodable bytes are ignored.
    """
    scanned = 0
    for path in walk_files(root):
        if path.suffix not in SOURCE_EXTENSIONS:
            continue
        if scanned >= MAX_SOURCE_FILES:
            break
        scanned += 1
        try:
            if path.stat().st_size > MAX_SOURCE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(pattern in text for pattern in ENV_PATTERNS):
            return path
    return None


def check_missing_env_example(repo_root: Path) -> CheckResult | None:
    """Return a CheckResult if code reads env vars but no .env template exists, else None."""
    root = repo_root.resolve()
    if _has_template(root):
        return None
    reference = find_env_reference(root)
    if reference is None:
        return None
    return CheckResult(
        check_id=CHECK_ID,
        category=FindingCategory.configuration,
        severity=Severity.medium,
        title="No .env.example for required environment variables",
        recommendation=(
            "The code reads environment variables but there is no template. Add a "
            ".env.example listing every variable the app needs, with placeholder values "
            "and a short comment each, so new developers know what to configure."
        ),
        file_path=rel(root, reference),
    )
