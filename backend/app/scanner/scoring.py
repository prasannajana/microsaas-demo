"""Readiness score computation."""

from collections.abc import Iterable

from app.models.finding import Severity
from app.scanner.types import CheckResult

SEVERITY_WEIGHTS: dict[Severity, int] = {
    Severity.critical: 25,
    Severity.high: 15,
    Severity.medium: 8,
    Severity.low: 3,
}


def compute_score(results: Iterable[CheckResult]) -> int:
    """
    Compute the 0-100 readiness score.

    Args:
        results: Findings produced by the checks

    Returns:
        max(0, 100 - sum of severity weights)
    """
    return max(0, 100 - sum(SEVERITY_WEIGHTS[r.severity] for r in results))
