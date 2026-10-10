"""Primary-language detection by file-extension counts."""

from collections import Counter
from pathlib import Path

from app.scanner.fs import walk_files

EXTENSION_LANGUAGES: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".fs": "F#",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hs": "Haskell",
    ".clj": "Clojure",
    ".lua": "Lua",
    ".r": "R",
    ".jl": "Julia",
    ".pl": "Perl",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "PowerShell",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".zig": "Zig",
}


def detect_primary_language(repo_root: Path) -> str | None:
    """
    Return the most common programming language in the repo by file count, or None.

    Ties are broken alphabetically for determinism.
    """
    root = repo_root.resolve()
    counts: Counter[str] = Counter()
    for path in walk_files(root):
        language = EXTENSION_LANGUAGES.get(path.suffix.lower())
        if language:
            counts[language] += 1
    if not counts:
        return None
    return min(counts.items(), key=lambda item: (-item[1], item[0]))[0]
