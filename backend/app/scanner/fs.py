"""Safe, symlink-aware filesystem helpers for checks.

Every helper keeps resolution inside the repository root and never follows
symlinks out of it. Directory symlinks are never descended into.
"""

import os
from collections.abc import Iterator
from pathlib import Path

from app.scanner import context

SKIP_DIRS = frozenset({".git", "node_modules", "venv", ".venv", "dist", "build", "__pycache__"})

# Hard cap on the number of files a single walk will yield (pathological repos).
MAX_WALK_FILES = 50_000
# Hard cap on the number of directories collected by a walk.
MAX_WALK_DIRS = 50_000


def is_inside(root: Path, path: Path) -> bool:
    """
    Return True if `path`, fully resolved, stays inside `root`.

    Args:
        root: Resolved repository root
        path: Path to check (may be a symlink)
    """
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError):
        return False
    return resolved == root or resolved.is_relative_to(root)


def safe_is_file(root: Path, path: Path) -> bool:
    """Return True if `path` is a regular file whose resolved location is inside `root`."""
    try:
        return is_inside(root, path) and path.is_file()
    except OSError:
        return False


def safe_is_dir(root: Path, path: Path) -> bool:
    """Return True if `path` is a real directory (not a symlink) inside `root`."""
    try:
        return not path.is_symlink() and is_inside(root, path) and path.is_dir()
    except OSError:
        return False


def list_dir(root: Path, directory: Path) -> list[Path]:
    """
    List the direct children of `directory` (sorted), or [] if it is not a safe directory.

    Args:
        root: Resolved repository root
        directory: Directory inside the repo
    """
    if not safe_is_dir(root, directory):
        return []
    try:
        return sorted(directory.iterdir())
    except OSError:
        return []


def root_files(root: Path) -> list[Path]:
    """Return regular files directly under the repo root (symlinks resolved and guarded)."""
    return [p for p in list_dir(root, root) if safe_is_file(root, p)]


def top_level_dirs(root: Path) -> list[Path]:
    """Return non-skipped, non-symlink directories directly under the repo root."""
    return [p for p in list_dir(root, root) if p.name not in SKIP_DIRS and safe_is_dir(root, p)]


def _walk(root: Path, max_files: int, max_dirs: int) -> tuple[list[Path], list[Path]]:
    """
    Walk `root` once, returning (files, dirs) in deterministic (sorted, top-down) order.

    Skips SKIP_DIRS and symlinked directories, never follows symlinks, skips symlinked
    files, and stops once either cap is reached. Checks the scan deadline per directory.
    """
    files: list[Path] = []
    dirs: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        context.check_deadline()
        current = Path(dirpath)
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIP_DIRS and not (current / d).is_symlink()
        )
        for d in dirnames:
            if len(dirs) >= max_dirs:
                return files, dirs
            dirs.append(current / d)
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink() or not is_inside(root, path):
                continue
            files.append(path)
            if len(files) >= max_files:
                return files, dirs
    return files, dirs


def _tree(root: Path) -> tuple[list[Path], list[Path]]:
    """Return (files, dirs) for `root`, served from the scan context cache when active."""
    ctx = context.current()
    if ctx is None:
        return _walk(root, MAX_WALK_FILES, MAX_WALK_DIRS)
    cached = ctx.walk_cache.get(root)
    if cached is None:
        cached = _walk(root, MAX_WALK_FILES, MAX_WALK_DIRS)
        ctx.walk_cache[root] = cached
    return cached


def walk_files(root: Path, max_files: int = MAX_WALK_FILES) -> Iterator[Path]:
    """
    Yield regular files under `root`, skipping SKIP_DIRS and never following symlinks.

    Symlinked files are skipped entirely (they are not real repository content we
    can safely read). Iteration order is deterministic (sorted). Within a scan the
    tree is walked once and shared by every check (see scanner.context).

    Args:
        root: Resolved repository root
        max_files: Stop after yielding this many files
    """
    files, _dirs = _tree(root)
    yield from files[:max_files]


def walk_dirs(root: Path) -> Iterator[Path]:
    """Yield directories under `root`, skipping SKIP_DIRS and symlinked directories."""
    _files, dirs = _tree(root)
    yield from dirs


def rel(root: Path, path: Path) -> str:
    """Return `path` relative to `root` as a POSIX string."""
    return path.relative_to(root).as_posix()
