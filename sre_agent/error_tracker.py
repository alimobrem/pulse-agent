"""In-memory error tracker with thread-safe ring buffer.

Provides aggregated error counts and recent error history for the
/health endpoint and operational visibility.
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque

from .errors import ToolError


class ErrorTracker:
    """Thread-safe ring buffer for tracking tool errors."""

    def __init__(self, max_entries: int = 500):
        self._errors: deque[ToolError] = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._counts: dict[str, int] = defaultdict(int)
        self._tool_counts: dict[str, int] = defaultdict(int)

    def record(self, error: ToolError) -> None:
        with self._lock:
            self._errors.append(error)
            self._counts[error.category] += 1
            if error.operation:
                self._tool_counts[error.operation] += 1

    def get_recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            items = list(self._errors)[-limit:]
        return [e.to_dict() for e in reversed(items)]

    def get_summary(self) -> dict:
        with self._lock:
            return {
                "total": sum(self._counts.values()),
                "by_category": dict(self._counts),
                "top_tools": dict(
                    sorted(
                        self._tool_counts.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:10]
                ),
            }

    def clear(self) -> None:
        with self._lock:
            self._errors.clear()
            self._counts.clear()
            self._tool_counts.clear()


_tracker = ErrorTracker()


def get_tracker() -> ErrorTracker:
    return _tracker
