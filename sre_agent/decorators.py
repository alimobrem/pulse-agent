"""Typed decorators for Pulse Agent tools.

Wraps anthropic.beta_tool with a relaxed return type so tools can return
either str or tuple[str, dict] (text + component spec) without mypy errors.
Includes optional timing instrumentation for performance tracking.
"""

from __future__ import annotations

import functools
import logging
import time
from collections import deque
from collections.abc import Callable
from typing import Any, TypeVar, Union

from anthropic import beta_tool as _anthropic_beta_tool

F = TypeVar("F", bound=Callable[..., Any])

#: Return type for tool functions — plain text or text + optional component spec.
ToolReturn = Union[str, "tuple[str, dict[str, Any] | None]"]

_logger = logging.getLogger("pulse_agent.tools")

#: Collected timing data — tool_name → deque of recent execution times (seconds).
#: Capped at 1000 entries per tool to prevent unbounded growth.
_MAX_TIMING_ENTRIES = 1000
tool_timings: dict[str, deque[float]] = {}

_PERF_TRACE = False


def enable_perf_trace() -> None:
    """Enable per-tool timing collection."""
    global _PERF_TRACE
    _PERF_TRACE = True


def get_tool_timings() -> dict[str, list[float]]:
    """Return collected timing data."""
    return {k: list(v) for k, v in tool_timings.items()}


def reset_tool_timings() -> None:
    """Clear collected timing data."""
    tool_timings.clear()


def beta_tool(fn: F) -> F:
    """Typed wrapper around anthropic.beta_tool.

    Allows tool functions to return str | tuple[str, dict] for component specs
    without mypy return-value errors. The single type: ignore here replaces
    30+ ignores across tool files.
    """

    @functools.wraps(fn)
    def _timed(*args: Any, **kwargs: Any) -> Any:
        if not _PERF_TRACE:
            return fn(*args, **kwargs)
        start = time.monotonic()
        try:
            return fn(*args, **kwargs)
        finally:
            elapsed = time.monotonic() - start
            tool_timings.setdefault(fn.__name__, deque(maxlen=_MAX_TIMING_ENTRIES)).append(elapsed)
            if elapsed > 2.0:
                _logger.warning("Slow tool %s: %.2fs", fn.__name__, elapsed)

    return _anthropic_beta_tool(_timed)  # type: ignore[return-value]
