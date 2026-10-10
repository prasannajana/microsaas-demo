"""Per-scan context: an overall deadline and a single shared walk of the repository.

`run_scan` opens a `scan_context(deadline=...)` around the clone and the checks. Inside it:
- `remaining()` / `check_deadline()` enforce SCAN_TOTAL_TIMEOUT_SECONDS across every step
  (git subprocess timeouts are clamped to the remaining budget);
- `fs.walk_files` / `fs.walk_dirs` walk the tree once and serve every later call from the
  cached lists, so N checks cost one walk instead of N.

The context lives in a ContextVar, so concurrent scans on different threads never share it.
Outside a context (unit tests calling a check directly) there is no deadline and no cache.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path


class ScanTimeoutError(Exception):
    """The scan exceeded its overall time budget (message is user-readable)."""


@dataclass
class ScanContext:
    """Mutable per-scan state (deadline is a time.monotonic() value)."""

    deadline: float | None = None
    walk_cache: dict[Path, tuple[list[Path], list[Path]]] = field(default_factory=dict)


_current: ContextVar[ScanContext | None] = ContextVar("scan_context", default=None)


def current() -> ScanContext | None:
    """Return the active scan context, or None outside a scan."""
    return _current.get()


@contextmanager
def scan_context(timeout_seconds: float | None = None) -> Iterator[ScanContext]:
    """
    Activate a fresh scan context for the duration of the block.

    Args:
        timeout_seconds: Overall budget; None means no deadline.
    """
    deadline = time.monotonic() + timeout_seconds if timeout_seconds is not None else None
    ctx = ScanContext(deadline=deadline)
    token = _current.set(ctx)
    try:
        yield ctx
    finally:
        _current.reset(token)


def remaining() -> float | None:
    """Seconds left before the scan deadline (may be <= 0), or None without a deadline."""
    ctx = _current.get()
    if ctx is None or ctx.deadline is None:
        return None
    return ctx.deadline - time.monotonic()


def clamp_timeout(timeout: float) -> float:
    """
    Return `timeout` clamped to the remaining scan budget.

    Raises:
        ScanTimeoutError: If the budget is already exhausted.
    """
    left = remaining()
    if left is None:
        return timeout
    if left <= 0:
        raise ScanTimeoutError("Scan timed out, the repository is too large to analyse")
    return min(timeout, left)


def check_deadline() -> None:
    """
    Raise if the active scan has exceeded its deadline (no-op outside a scan).

    Raises:
        ScanTimeoutError: If the deadline has passed.
    """
    left = remaining()
    if left is not None and left <= 0:
        raise ScanTimeoutError("Scan timed out, the repository is too large to analyse")
