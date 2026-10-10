"""Shared helpers for dependency-manifest based checks."""

from pathlib import Path

from app.scanner.fs import root_files, safe_is_file, top_level_dirs

MANIFEST_NAMES = frozenset(
    {
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "package.json",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "Cargo.toml",
        "Gemfile",
        "composer.json",
    }
)

# Lockfiles conventionally produced next to each manifest. Manifests absent from this
# map (requirements.txt, pom.xml, build.gradle*) have no lockfile expectation.
LOCKFILES: dict[str, tuple[str, ...]] = {
    "package.json": (
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "bun.lockb",
        "bun.lock",
    ),
    "Pipfile": ("Pipfile.lock",),
    "pyproject.toml": ("poetry.lock", "uv.lock", "pdm.lock"),
    "go.mod": ("go.sum",),
    "Cargo.toml": ("Cargo.lock",),
    "Gemfile": ("Gemfile.lock",),
    "composer.json": ("composer.lock",),
}

_MAX_MANIFEST_BYTES = 1024 * 1024


def find_manifests(root: Path) -> list[Path]:
    """
    Return dependency manifests at the repo root or one directory level deep.

    Args:
        root: Resolved repository root

    Returns:
        Manifest paths, root-level first, sorted.
    """
    found = [p for p in root_files(root) if p.name in MANIFEST_NAMES]
    for directory in top_level_dirs(root):
        found.extend(
            directory / name
            for name in sorted(MANIFEST_NAMES)
            if safe_is_file(root, directory / name)
        )
    return found


def _read_text(path: Path) -> str:
    try:
        if path.stat().st_size > _MAX_MANIFEST_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def expects_lockfile(manifest: Path) -> bool:
    """
    Return True if the ecosystem of `manifest` conventionally commits a lockfile.

    pyproject.toml only counts when it is managed by Poetry, PDM or uv; go.mod only
    when it declares dependencies (a module with no requirements has no go.sum).
    """
    name = manifest.name
    if name not in LOCKFILES:
        return False
    if name == "pyproject.toml":
        text = _read_text(manifest)
        return any(marker in text for marker in ("[tool.poetry", "[tool.pdm", "[tool.uv"))
    if name == "go.mod":
        return "require" in _read_text(manifest)
    return True
