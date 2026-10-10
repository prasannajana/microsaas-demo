"""Shared scanner types."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.models.finding import FindingCategory, Severity


@dataclass(frozen=True)
class CheckResult:
    """A single gap detected by a check (returned only when something is missing)."""

    check_id: str
    category: FindingCategory
    severity: Severity
    title: str
    recommendation: str
    file_path: str | None = None


Check = Callable[[Path], CheckResult | None]
